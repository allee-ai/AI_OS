"""
infra/form_server_droplet.py — droplet-side form-server (full parity).

Differences from infra/form_server.py:
  - No macOS keychain. Reads SMTP password from env PROTON_SMTP_PASS
    (loaded from /etc/aios/form-server.env by systemd).
  - Talks to Proton submission SMTP at smtp.protonmail.ch:587 (STARTTLS).
  - Same routes, same /contact-submit handler, same /health endpoint.
  - Full parity with the Mac variant:
      • /instant-quote-submit  → PDF render + dual email + jake-app webhook
      • /contact-submit         → plain email
  - Jake-app token comes from env JAKE_SERVICE_TOKEN (also in
    /etc/aios/form-server.env), not keychain.

Runs on droplet under systemd. Listens on 127.0.0.1:8042 — Caddy reverse-proxies
/contact-submit and /instant-quote-submit to it from each site block.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import certifi
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from bid_render import render_bid_pdf, classify_track, PROPERTY_LABELS


# ── routing ──────────────────────────────────────────────────────────────────

# Where lead notifications LAND (the shared pool inbox).
ROUTES = {
    "vre-construction.com":        "allee@allee-ai.com",
    "vanguardrelocations.com":     "allee@allee-ai.com",
    "allee-ai.com":                "allee@allee-ai.com",
    "127.0.0.1":                   "allee@allee-ai.com",
    "localhost":                   "allee@allee-ai.com",
}

# What FROM address each site sends as. Per-site so customer replies
# land on the right brand inbox and the From matches the verified Resend
# domain.
FROM_ROUTES = {
    "vre-construction.com":    "cade@vre-construction.com",
    "vanguardrelocations.com": "layton@vanguardrelocations.com",
    "allee-ai.com":            "allee@allee-ai.com",
    "127.0.0.1":               "allee@allee-ai.com",
    "localhost":               "allee@allee-ai.com",
}

# ── mail backend selection ───────────────────────────────────────────────

# "resend" -> HTTP API (works behind cloud-provider SMTP blocks).
# "smtp"   -> Proton submission SMTP (legacy path, requires egress port 587).
MAIL_BACKEND = os.environ.get("MAIL_BACKEND", "smtp").lower()

# ── Resend HTTP API ────────────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_URL = "https://api.resend.com/emails"

# ── SMTP via Proton submission (fallback / legacy) ───────────────────────────

SMTP_HOST = os.environ.get("PROTON_SMTP_HOST", "smtp.protonmail.ch")
SMTP_PORT = int(os.environ.get("PROTON_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("PROTON_SMTP_USER", "allee@allee-ai.com")
SMTP_PASS = os.environ.get("PROTON_SMTP_PASS", "")
SMTP_FROM = os.environ.get("PROTON_SMTP_FROM", SMTP_USER)

# ── Jake-app CRM webhook (cross-droplet HTTPS) ───────────────────────────────

JAKE_URL = os.environ.get("JAKE_URL", "https://bycade.com/api/sales/leads")
JAKE_TOKEN = os.environ.get("JAKE_SERVICE_TOKEN", "")
JAKE_TIMEOUT_S = 4

# ── CORS ─────────────────────────────────────────────────────────────────────

ALLOW_ORIGINS = [
    "https://allee-ai.com",
    "https://www.allee-ai.com",
    "https://allee-ai.github.io",
    "https://vre-construction.com",
    "https://www.vre-construction.com",
    "https://vanguardrelocations.com",
    "https://www.vanguardrelocations.com",
]

# ── logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("form-server")

# ── helpers ──────────────────────────────────────────────────────────────────


def _normalize_site(site: str) -> str:
    s = (site or "").strip().lower()
    if s.startswith("www."):
        s = s[4:]
    return s.split(":", 1)[0]


def _resolve_destination(site: str) -> Optional[str]:
    if not site:
        return None
    return ROUTES.get(_normalize_site(site))


def _resolve_from(site: str) -> str:
    """Per-site From address. Falls back to SMTP_FROM / allee@."""
    if site:
        addr = FROM_ROUTES.get(_normalize_site(site))
        if addr:
            return addr
    return SMTP_FROM or "allee@allee-ai.com"


def _send_email_resend(
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    reply_to: str = "",
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    if not RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not set in environment")
    payload: dict = {
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "text": body,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if attachments:
        payload["attachments"] = [
            {
                "filename": filename,
                "content": base64.b64encode(data).decode("ascii"),
            }
            for (filename, data, _subtype) in attachments
        ]
    req = urllib.request.Request(
        RESEND_URL,
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
            body_text = resp.read().decode(errors="replace")[:200]
            log.info("resend: %s %s", resp.status, body_text)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400] if e.fp else ""
        raise RuntimeError(f"resend HTTP {e.code}: {detail}") from e


def _send_email_smtp(
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    reply_to: str = "",
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    if not SMTP_PASS:
        raise RuntimeError("PROTON_SMTP_PASS not set in environment")
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body, "plain"))

    for filename, data, subtype in attachments or []:
        part = MIMEApplication(data, _subtype=subtype)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


def _send_email(
    to_addr: str,
    subject: str,
    body: str,
    reply_to: str = "",
    attachments: list[tuple[str, bytes, str]] | None = None,
    from_addr: str = "",
) -> None:
    """Dispatcher: routes to Resend HTTP API or Proton SMTP per MAIL_BACKEND."""
    sender = from_addr or SMTP_FROM or "allee@allee-ai.com"
    if MAIL_BACKEND == "resend":
        _send_email_resend(sender, to_addr, subject, body, reply_to, attachments)
    else:
        _send_email_smtp(sender, to_addr, subject, body, reply_to, attachments)


def _push_lead_to_jake(lead: dict) -> None:
    """Fire-and-forget POST into jake-app CRM. Never raises."""
    if not JAKE_TOKEN:
        log.warning("jake: no JAKE_SERVICE_TOKEN env, skipping push")
        return
    try:
        req = urllib.request.Request(
            JAKE_URL,
            data=json.dumps(lead, default=str).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {JAKE_TOKEN}",
                "Content-Type": "application/json",
            },
        )
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(req, timeout=JAKE_TIMEOUT_S, context=ctx) as resp:
            body = resp.read().decode(errors="replace")[:200]
            log.info("jake: lead pushed (%s) %s", resp.status, body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200] if e.fp else ""
        log.error("jake: HTTP %s pushing lead: %s", e.code, detail)
    except Exception as e:
        log.error("jake: push failed: %s: %s", type(e).__name__, e)


# ── auto-reply bodies ────────────────────────────────────────────────────────

_HOMEOWNER_BODY = """\
Hi {name},

Thanks for using our instant-quote tool. Your itemized estimate is attached
as a PDF — bid {bid_id}.

A few honest notes:

  • This is an *estimate*, not a final invoice. The range reflects access
    conditions and the kind of surprises older Cincinnati homes hand us.
  • We confirm a single firm number on a free 15-minute walkthrough before
    any work starts. We won't change the price after that without your
    written sign-off.
  • The estimate is good for 30 days.

Next step: we'll text you within one business day to schedule the walkthrough.
If you'd rather, you can text us first at {phone} — same number, faster.

— The VRE Construction team
   {phone} · {email_brand}
   vre-construction.com
"""

_INVESTOR_BODY = """\
Hi {name},

Thanks for using our instant-quote tool. Your itemized estimate is attached
as a PDF — bid {bid_id}.

Property type tells me you're working a {prop_label_lower}, so a few things
that won't be on the homeowner version of this email:

  • The estimate is structured so you can hand it straight to a lender or
    drop it into a draw schedule. Line items match the public price page
    so there's nothing to defend.
  • We carry $2M general liability and pull permits in our name. Inspection
    coordination is included on permitted work — you don't chase it.
  • After your third booked job we apply a quiet 8–12% rebate on labor as
    a credit on the next bid. We don't publish that. Just mention this
    estimate when you book.
  • If your scope includes anything we don't list (drywall patches, low
    voltage, generator gas-side, solar tie-in), tell us and we'll bring
    the trade or tell you which one to call.

Next step: we'll text you within one business day. If you have a closing
or draw deadline, reply with it and we'll move the walkthrough up.

— The VRE Construction team
   {phone} · {email_brand}
   vre-construction.com
"""


# ── app ──────────────────────────────────────────────────────────────────────

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({
        "status": "ok",
        "mail_backend": MAIL_BACKEND,
        "resend_key_present": bool(RESEND_API_KEY),
        "smtp_host": SMTP_HOST,
        "smtp_user": SMTP_USER,
        "smtp_pass_present": bool(SMTP_PASS),
        "jake_token_present": bool(JAKE_TOKEN),
        "routes": list(ROUTES.keys()),
        "from_routes": FROM_ROUTES,
    })


@app.post("/contact-submit")
async def contact_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    topic: str = Form("General"),
    site: str = Form(""),
):
    # Resolve site from form value, falling back to Origin / Referer host.
    target = _resolve_destination(site)
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    if not target and origin:
        host = origin.split("://", 1)[-1].split("/", 1)[0]
        target = _resolve_destination(host)
        site = site or host
    if not target and referer:
        host = referer.split("://", 1)[-1].split("/", 1)[0]
        target = _resolve_destination(host)
        site = site or host
    if not target:
        log.warning("rejected submit: site=%r origin=%r referer=%r", site, origin, referer)
        raise HTTPException(status_code=400, detail=f"unknown site '{site}'")

    subject = f"[{site}] {topic} — from {name}"
    body = (
        f"From: {name} <{email}>\n"
        f"Site: {site}\n"
        f"Topic: {topic}\n\n"
        f"{message}\n"
    )
    try:
        _send_email(target, subject, body, reply_to=email, from_addr=_resolve_from(site))
        log.info("sent %s -> %s: %s from %s", site, target, topic, name)
    except Exception as e:  # noqa: BLE001
        log.exception("smtp send failed: %s", e)
        raise HTTPException(status_code=502, detail="email send failed") from e

    # Redirect back to origin or referer.
    redirect_to = ""
    if origin:
        redirect_to = f"{origin}/?sent=1"
    elif referer:
        sep = "&" if "?" in referer else "?"
        redirect_to = f"{referer}{sep}sent=1"
    else:
        redirect_to = f"https://{site}/?sent=1"
    return RedirectResponse(redirect_to, status_code=303)


@app.post("/instant-quote-submit")
async def instant_quote_submit(request: Request):
    """Render itemized bid PDF, send two emails, push lead into jake-app CRM."""
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(400, f"bad json: {e}")

    # Resolve destination from payload.site or Origin/Referer.
    site_in = (payload.get("site") or "").lower()
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    target_site = site_in or ""
    to_addr = _resolve_destination(target_site)
    if not to_addr and origin:
        host = origin.split("://", 1)[-1].split("/", 1)[0]
        to_addr = _resolve_destination(host)
        target_site = target_site or host
    if not to_addr and referer:
        host = referer.split("://", 1)[-1].split("/", 1)[0]
        to_addr = _resolve_destination(host)
        target_site = target_site or host
    if not to_addr:
        raise HTTPException(400, f"unknown site '{site_in}'")

    contact = payload.get("contact") or {}
    customer_name = (contact.get("name") or "").strip()
    customer_email = (contact.get("email") or "").strip()

    # ── 1) render PDF first (fail-fast) ───────────────────────────
    try:
        pdf_bytes, bid_id, track = render_bid_pdf(payload)
    except Exception as e:
        log.exception("pdf render failed: %s", e)
        raise HTTPException(500, f"pdf render failed: {type(e).__name__}: {e}")

    prop_label = PROPERTY_LABELS.get(payload.get("property") or "", "—")
    items = payload.get("items") or []
    mods = payload.get("mods") or []
    total_low = int(payload.get("total_low") or 0)
    total_high = int(payload.get("total_high") or 0)

    item_lines = "\n".join(
        f"  • {it.get('label','?')} ×{it.get('qty',1)}  "
        f"${int(it.get('low',0)):,}–${int(it.get('high',0)):,}"
        for it in items
    )
    mod_lines = "\n".join(
        f"  • {m.get('label','?')}  ({int(m.get('pct',0)):+d}%)"
        for m in mods
    ) or "  (none)"

    lead_subject = (
        f"[{target_site}] INSTANT QUOTE [{track.upper()}] "
        f"{bid_id} — {customer_name or '(no name)'}"
    )
    lead_body = (
        f"NEW INSTANT QUOTE\n\n"
        f"Bid ID: {bid_id}\n"
        f"Track:  {track}\n"
        f"Site:   {target_site}\n\n"
        f"Customer:\n"
        f"  Name:    {customer_name or '(none)'}\n"
        f"  Email:   {customer_email or '(none)'}\n"
        f"  Phone:   {contact.get('phone') or '(none)'}\n"
        f"  Address: {contact.get('address') or '(none)'}\n\n"
        f"Property: {prop_label}\n\n"
        f"Total range: ${total_low:,} – ${total_high:,}\n\n"
        f"Items:\n{item_lines or '  (none)'}\n\n"
        f"Adjustments:\n{mod_lines}\n\n"
        f"Customer notes:\n{contact.get('notes') or '  (none)'}\n\n"
        f"PDF attached.\n"
    )
    try:
        _send_email(
            to_addr,
            lead_subject,
            lead_body,
            reply_to=customer_email or SMTP_USER,
            attachments=[(f"{bid_id}.pdf", pdf_bytes, "pdf")],
            from_addr=_resolve_from(target_site),
        )
    except Exception as e:
        log.error("lead notify failed for %s: %s", target_site, e)
        raise HTTPException(502, f"lead notify failed: {type(e).__name__}")

    # ── 2) auto-reply to the customer with PDF attached ───────────
    if customer_email:
        body_tmpl = _INVESTOR_BODY if track == "investor" else _HOMEOWNER_BODY
        site_phone = "(513) 555-0118"
        site_email = "hello@vre-construction.com"
        reply_subject = f"Your estimate from VRE Construction — {bid_id}"
        reply_body = body_tmpl.format(
            name=customer_name.split()[0] if customer_name else "there",
            bid_id=bid_id,
            prop_label_lower=prop_label.lower(),
            phone=site_phone,
            email_brand=site_email,
        )
        try:
            _send_email(
                customer_email,
                reply_subject,
                reply_body,
                reply_to=to_addr,
                attachments=[(f"{bid_id}.pdf", pdf_bytes, "pdf")],
                from_addr=_resolve_from(target_site),
            )
        except Exception as e:
            log.error("auto-reply failed for %s: %s", customer_email, e)

    log.info(
        "instant-quote %s (%s) %s -> %s; reply -> %s",
        bid_id, track, target_site, to_addr, customer_email,
    )

    # ── 3) fire-and-forget push into jake-app CRM ─────────────────
    try:
        site_tag = (target_site or "vre").split(".")[0].replace("-", "")
        notes_block = (
            f"bid_id: {bid_id}\n"
            f"track: {track}\n"
            f"property: {prop_label}\n"
            f"total: ${total_low:,}–${total_high:,}\n"
            f"items: {len(items)}\n"
            f"site: {target_site}\n"
            f"\ncustomer notes:\n{contact.get('notes') or '(none)'}"
        )
        lead = {
            "contact_name": customer_name or "(no name)",
            "phone": contact.get("phone") or None,
            "email": customer_email or None,
            "address": contact.get("address") or None,
            "contact_role": "investor" if track == "investor" else "owner",
            "source": f"instant-quote-{site_tag}",
            "notes": notes_block,
            "next_action": "Text within 1 business day",
            "next_action_date": date.today().isoformat(),
        }
        _push_lead_to_jake(lead)
    except Exception as e:
        log.error("jake: lead-build failed: %s: %s", type(e).__name__, e)

    return JSONResponse({"ok": True, "bid_id": bid_id, "track": track})


if __name__ == "__main__":
    import uvicorn
    log.info("form-server (droplet) starting on 127.0.0.1:8042")
    log.info("mail backend: %s", MAIL_BACKEND)
    if MAIL_BACKEND == "resend":
        log.info("resend api key: %s", "set" if RESEND_API_KEY else "MISSING")
    else:
        log.info("smtp: %s:%s as %s (pass=%s)", SMTP_HOST, SMTP_PORT, SMTP_USER, "set" if SMTP_PASS else "MISSING")
    log.info("jake: %s (token=%s)", JAKE_URL, "set" if JAKE_TOKEN else "MISSING")
    log.info("routes (TO): %s", ROUTES)
    log.info("from_routes: %s", FROM_ROUTES)
    uvicorn.run(app, host="127.0.0.1", port=8042, log_level="info")
