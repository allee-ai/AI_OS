"""Contact form server.

Routes per-site contact submissions through the local Proton Bridge.

  Site                          To
  ─────────────────────────     ──────────────────────
  vre-construction.com          allee@allee-ai.com
  vanguardrelocations.com       assistant@allee-ai.com
  allee-ai.com                  allee@allee-ai.com  (default)

Architecture:
  Form on droplet → Caddy reverse-proxies /contact-submit
                  → SSH reverse tunnel (:8042 on droplet → :8042 on Mac)
                  → this server
                  → Proton Bridge SMTP (127.0.0.1:1025) on Mac
                  → email lands in destination inbox

Run:
  python infra/form_server.py
"""
from __future__ import annotations

import os
import logging
import smtplib
import subprocess
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from infra.bid_render import render_bid_pdf, classify_track, PROPERTY_LABELS


# ── Config ─────────────────────────────────────────────────────────
PROTON_SERVICE = "AIOS-Proton-Bridge"
PROTON_ACCOUNT = "alleeroden@pm.me"
SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025

# Where each site's form submissions go.
ROUTES: dict[str, str] = {
    "vre-construction.com":        "allee@allee-ai.com",
    "vanguardrelocations.com":     "assistant@allee-ai.com",
    "allee-ai.com":                "allee@allee-ai.com",
    # localhost preview targets
    "127.0.0.1":                   "allee@allee-ai.com",
    "localhost":                   "allee@allee-ai.com",
}

# Origins permitted to POST. Add scheme variants explicitly.
ALLOWED_ORIGINS = [
    "https://vre-construction.com",
    "https://www.vre-construction.com",
    "https://vanguardrelocations.com",
    "https://www.vanguardrelocations.com",
    "https://allee-ai.com",
    "https://www.allee-ai.com",
    "http://127.0.0.1:9090",
    "http://127.0.0.1:8000",
    "http://localhost:9090",
    "http://localhost:8000",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("form-server")


def _keychain_password() -> str:
    out = subprocess.check_output(
        ["security", "find-generic-password",
         "-s", PROTON_SERVICE, "-a", PROTON_ACCOUNT, "-w"],
        stderr=subprocess.DEVNULL,
    )
    return out.decode().strip()


def _resolve_destination(site: str) -> str | None:
    """Map a hostname (with or without `www.` and `:port`) to a To address."""
    host = (site or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return ROUTES.get(host)


def _send_email(to_addr: str, subject: str, body: str, reply_to: str,
                attachments: list[tuple[str, bytes, str]] | None = None) -> None:
    """Send an email. attachments = [(filename, bytes, mime_subtype)]."""
    msg = MIMEMultipart()
    msg["From"] = PROTON_ACCOUNT
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body, "plain"))
    for fname, data, subtype in attachments or []:
        part = MIMEApplication(data, _subtype=subtype)
        part.add_header("Content-Disposition", "attachment", filename=fname)
        msg.attach(part)

    password = _keychain_password()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as srv:
        srv.starttls()
        srv.login(PROTON_ACCOUNT, password)
        srv.send_message(msg)


# ── App ─────────────────────────────────────────────────────────────
app = FastAPI(docs_url=None, redoc_url=None, title="form-server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    try:
        pw_len = len(_keychain_password())
        return {"status": "ok", "keychain": f"{pw_len} chars", "routes": list(ROUTES.keys())}
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.post("/contact-submit")
async def contact_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    message: str = Form(...),
    topic: str = Form("General"),
    site: str = Form(""),  # form supplies the apex domain
):
    """Receive a contact form, route by site, send email, redirect home."""
    # Resolve destination: prefer explicit `site` field, else Origin/Referer host
    target_site = site or ""
    if not target_site:
        ref = request.headers.get("origin") or request.headers.get("referer") or ""
        if ref:
            from urllib.parse import urlparse
            target_site = urlparse(ref).hostname or ""

    to_addr = _resolve_destination(target_site)
    if not to_addr:
        raise HTTPException(400, f"unknown site: {target_site!r}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"[{target_site}] {topic} - from {name}"
    body = (
        f"New message from the {target_site} contact form\n\n"
        f"From:    {name} <{email}>\n"
        f"Topic:   {topic}\n"
        f"Time:    {timestamp}\n"
        f"Site:    {target_site}\n\n"
        f"{message}\n"
    )

    try:
        _send_email(to_addr, subject, body, reply_to=email)
        log.info(f"sent {target_site} -> {to_addr}: {topic} from {name}")
    except Exception as e:
        log.error(f"send failed for {target_site}: {e}")
        raise HTTPException(502, f"mail relay failed: {type(e).__name__}")

    # Redirect back to the page where the form was submitted.
    origin = request.headers.get("origin")
    referer = request.headers.get("referer", "")
    if origin and origin in ALLOWED_ORIGINS:
        return RedirectResponse(f"{origin}/?sent=1", status_code=303)
    if referer:
        sep = "&" if "?" in referer else "?"
        return RedirectResponse(f"{referer}{sep}sent=1", status_code=303)
    return RedirectResponse(f"https://{target_site}/?sent=1", status_code=303)


# ── Instant-quote submit ────────────────────────────────────────────

# Auto-reply email bodies, segmented by track. Plain text — keeps it readable
# in every client and avoids the "this looks like marketing" trigger.

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

Next step: I'll text you within one business day to schedule the walkthrough.
If you'd rather, you can text us first at {phone} — same number, faster.

— Jordan
   Field manager · Vanguard Reconstruction
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

Next step: I'll text you within one business day. If you have a closing
or draw deadline, reply with it and we'll move the walkthrough up.

— Cade
   Owner · Vanguard Reconstruction
   {phone} · {email_brand}
   vre-construction.com
"""


@app.post("/instant-quote-submit")
async def instant_quote_submit(request: Request):
    """Receive a structured quote payload, render PDF, send two emails:
       1) lead notification to the site's destination address
       2) auto-reply to the customer with the PDF attached
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "expected JSON body")

    target_site = (payload.get("site") or "").lower()
    if not target_site:
        ref = request.headers.get("origin") or request.headers.get("referer") or ""
        if ref:
            from urllib.parse import urlparse
            target_site = (urlparse(ref).hostname or "").lower()

    to_addr = _resolve_destination(target_site)
    if not to_addr:
        raise HTTPException(400, f"unknown site: {target_site!r}")

    contact = payload.get("contact") or {}
    customer_email = (contact.get("email") or "").strip()
    customer_name = (contact.get("name") or "there").strip()
    property_type = payload.get("property") or "home"
    track = classify_track(property_type)
    prop_label = PROPERTY_LABELS.get(property_type, property_type)

    # Render the PDF first; if this fails we don't want to send half the emails.
    try:
        pdf_bytes, bid_id, _track2 = render_bid_pdf(payload)
    except Exception as e:
        log.error(f"bid render failed: {e}")
        raise HTTPException(500, f"bid render failed: {type(e).__name__}: {e}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_low = int(payload.get("total_low") or 0)
    total_high = int(payload.get("total_high") or 0)
    items = payload.get("items") or []
    mods = payload.get("mods") or []

    # ── 1) lead notification to the business inbox ────────────────
    item_lines = "\n".join(
        f"  × {it.get('qty')} · {it.get('label')}  (${it.get('low'):,}–${it.get('high'):,} ea)"
        for it in items
    )
    mod_lines = "\n".join(
        f"  + {m.get('label')}" + (f"  ({m.get('pct')}%)" if m.get('pct') else "")
        for m in mods
    ) or "  (none)"

    lead_subject = f"[{target_site}] INSTANT QUOTE [{track.upper()}] {bid_id} — {customer_name}"
    lead_body = (
        f"New instant-quote submission — {bid_id}\n"
        f"Track: {track}\n"
        f"Time:  {timestamp}\n\n"
        f"From:    {customer_name} <{customer_email}>\n"
        f"Phone:   {contact.get('phone', '—')}\n"
        f"Address: {contact.get('address', '—')}\n"
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
            reply_to=customer_email or PROTON_ACCOUNT,
            attachments=[(f"{bid_id}.pdf", pdf_bytes, "pdf")],
        )
    except Exception as e:
        log.error(f"lead notify failed for {target_site}: {e}")
        raise HTTPException(502, f"lead notify failed: {type(e).__name__}")

    # ── 2) auto-reply to the customer with PDF attached ───────────
    if customer_email:
        body_tmpl = _INVESTOR_BODY if track == "investor" else _HOMEOWNER_BODY
        site_phone = "(513) 555-0118"
        site_email = "hello@vre-construction.com"
        reply_subject = f"Your estimate from Vanguard Reconstruction — {bid_id}"
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
            )
        except Exception as e:
            # Don't fail the whole request — the lead notification already landed.
            log.error(f"auto-reply failed for {customer_email}: {e}")

    log.info(f"instant-quote {bid_id} ({track}) {target_site} -> {to_addr}; reply -> {customer_email}")
    return JSONResponse({"ok": True, "bid_id": bid_id, "track": track})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8042"))
    log.info(f"form-server starting on 127.0.0.1:{port}")
    log.info(f"routes: {ROUTES}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
