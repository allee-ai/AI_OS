"""
infra/form_server_droplet.py — droplet-side form-server.

Differences from infra/form_server.py:
  - No macOS keychain. Reads SMTP password from env PROTON_SMTP_PASS
    (loaded from /etc/aios/form-server.env by systemd).
  - Talks to Proton submission SMTP at smtp.protonmail.ch:587 (STARTTLS).
  - Same routes, same /contact-submit handler, same /health endpoint.

Runs on droplet under systemd. Listens on 127.0.0.1:8042 — Caddy reverse-proxies
/contact-submit to it from each site block.
"""

from __future__ import annotations

import logging
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

# ── routing ──────────────────────────────────────────────────────────────────

ROUTES = {
    "vanguard-reconstruction.com": "allee@allee-ai.com",
    "vanguard-relocations.com":    "assistant@allee-ai.com",
    "allee-ai.com":                "allee@allee-ai.com",
    "127.0.0.1":                   "allee@allee-ai.com",
    "localhost":                   "allee@allee-ai.com",
}

# ── SMTP via Proton submission ───────────────────────────────────────────────

SMTP_HOST = os.environ.get("PROTON_SMTP_HOST", "smtp.protonmail.ch")
SMTP_PORT = int(os.environ.get("PROTON_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("PROTON_SMTP_USER", "alleeroden@pm.me")
SMTP_PASS = os.environ.get("PROTON_SMTP_PASS", "")
SMTP_FROM = os.environ.get("PROTON_SMTP_FROM", SMTP_USER)

ALLOW_ORIGINS = [
    "https://allee-ai.com",
    "https://www.allee-ai.com",
    "https://allee-ai.github.io",
    "https://vanguard-reconstruction.com",
    "https://www.vanguard-reconstruction.com",
    "https://vanguard-relocations.com",
    "https://www.vanguard-relocations.com",
]

# ── logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("form-server")

# ── helpers ──────────────────────────────────────────────────────────────────


def _resolve_destination(site: str) -> Optional[str]:
    if not site:
        return None
    s = site.strip().lower()
    if s.startswith("www."):
        s = s[4:]
    s = s.split(":", 1)[0]
    return ROUTES.get(s)


def _send_email(to_addr: str, subject: str, body: str, reply_to: str = "") -> None:
    if not SMTP_PASS:
        raise RuntimeError("PROTON_SMTP_PASS not set in environment")
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = to_addr
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


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
        "smtp_host": SMTP_HOST,
        "smtp_user": SMTP_USER,
        "smtp_pass_present": bool(SMTP_PASS),
        "routes": list(ROUTES.keys()),
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
        _send_email(target, subject, body, reply_to=email)
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


if __name__ == "__main__":
    import uvicorn
    log.info("form-server (droplet) starting on 127.0.0.1:8042")
    log.info("smtp: %s:%s as %s (pass=%s)", SMTP_HOST, SMTP_PORT, SMTP_USER, "set" if SMTP_PASS else "MISSING")
    log.info("routes: %s", ROUTES)
    uvicorn.run(app, host="127.0.0.1", port=8042, log_level="info")
