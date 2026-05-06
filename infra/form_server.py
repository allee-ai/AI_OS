"""Contact form server.

Routes per-site contact submissions through the local Proton Bridge.

  Site                          To
  ─────────────────────────     ──────────────────────
  vanguard-reconstruction.com   allee@allee-ai.com
  vanguard-relocations.com      assistant@allee-ai.com
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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


# ── Config ─────────────────────────────────────────────────────────
PROTON_SERVICE = "AIOS-Proton-Bridge"
PROTON_ACCOUNT = "alleeroden@pm.me"
SMTP_HOST = "127.0.0.1"
SMTP_PORT = 1025

# Where each site's form submissions go.
ROUTES: dict[str, str] = {
    "vanguard-reconstruction.com": "allee@allee-ai.com",
    "vanguard-relocations.com":    "assistant@allee-ai.com",
    "allee-ai.com":                "allee@allee-ai.com",
    # localhost preview targets
    "127.0.0.1":                   "allee@allee-ai.com",
    "localhost":                   "allee@allee-ai.com",
}

# Origins permitted to POST. Add scheme variants explicitly.
ALLOWED_ORIGINS = [
    "https://vanguard-reconstruction.com",
    "https://www.vanguard-reconstruction.com",
    "https://vanguard-relocations.com",
    "https://www.vanguard-relocations.com",
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


def _send_email(to_addr: str, subject: str, body: str, reply_to: str) -> None:
    msg = MIMEMultipart()
    msg["From"] = PROTON_ACCOUNT
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body, "plain"))

    password = _keychain_password()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as srv:
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8042"))
    log.info(f"form-server starting on 127.0.0.1:{port}")
    log.info(f"routes: {ROUTES}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
