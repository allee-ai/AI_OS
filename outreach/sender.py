"""
outreach/sender.py — actually deliver approved messages via SMTP.

Reuses the Proton Bridge credentials stored under feed_name='email_proton'
in the secrets table (same source as Feeds/sources/email).  No new config.

The send-gate is enforced here: this module *refuses* to send anything
that isn't in 'approved' status.  Drafts can never leak.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Optional, Tuple

from outreach.schema import get_item, mark_failed, mark_sent


# ── Credential resolution ─────────────────────────────────────────────

def _get_smtp_creds() -> Tuple[str, int, str, str]:
    """
    Resolve (host, smtp_port, user, password).

    Priority:
        1. agent.core.secrets.get_secret('...', 'email_proton')   — same as inbound
        2. env vars PROTON_SMTP_HOST / PROTON_SMTP_PORT / PROTON_SMTP_USER /
           PROTON_BRIDGE_PASS (handy for VM / headless setups)
        3. localhost defaults (host=127.0.0.1, smtp_port=1025)
    """
    host = port = user = password = ""
    try:
        from agent.core.secrets import get_secret
        host = get_secret("smtp_host", "email_proton") or get_secret("imap_host", "email_proton") or ""
        port_s = get_secret("smtp_port", "email_proton") or ""
        user = get_secret("imap_user", "email_proton") or ""
        password = get_secret("imap_password", "email_proton") or ""
        port = int(port_s) if port_s else 0
    except Exception:
        pass

    host = host or os.environ.get("PROTON_SMTP_HOST", "") or "127.0.0.1"
    port = port or int(os.environ.get("PROTON_SMTP_PORT", "0") or "1025")
    user = user or os.environ.get("PROTON_SMTP_USER", "") or os.environ.get("PROTON_IMAP_USER", "")
    password = password or os.environ.get("PROTON_BRIDGE_PASS", "")

    return host, port, user, password


# ── Sender ────────────────────────────────────────────────────────────

class SendGateError(RuntimeError):
    """Raised when something tries to bypass the send-gate."""


def send_one(item_id: int, *, dry_run: bool = False,
             from_name: str = "Nola (allee-ai)") -> dict:
    """Send a single approved outreach item.

    Returns a dict: {ok: bool, item_id, message_id, error}
    """
    item = get_item(item_id)
    if not item:
        return {"ok": False, "item_id": item_id, "error": "not found"}
    if item["status"] != "approved":
        raise SendGateError(
            f"refusing to send #{item_id}: status='{item['status']}' (need 'approved')"
        )

    host, port, user, password = _get_smtp_creds()
    if not user or not password:
        err = ("Proton Bridge credentials missing — set them in Settings → Feeds → Proton, "
               "or export PROTON_SMTP_USER + PROTON_BRIDGE_PASS.")
        if dry_run:
            # Dry-run still useful without creds: caller wants to preview the message.
            user = user or "unknown@allee-ai.com"
        else:
            mark_failed(item_id, error=err)
            return {"ok": False, "item_id": item_id, "error": err}

    msg = EmailMessage()
    msg["From"] = formataddr((from_name, user))
    if item.get("to_name"):
        msg["To"] = formataddr((item["to_name"], item["to_email"]))
    else:
        msg["To"] = item["to_email"]
    msg["Subject"] = item["subject"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=user.split("@", 1)[-1] if "@" in user else "allee-ai.com")
    if item.get("thread_ref"):
        msg["In-Reply-To"] = item["thread_ref"]
        msg["References"] = item["thread_ref"]
    msg.set_content(item["body"])

    if dry_run:
        return {
            "ok": True,
            "item_id": item_id,
            "message_id": msg["Message-ID"],
            "dry_run": True,
            "preview": {
                "from": msg["From"],
                "to": msg["To"],
                "subject": msg["Subject"],
                "body_chars": len(item["body"]),
            },
        }

    try:
        # Proton Bridge listens on plain SMTP+STARTTLS on localhost.
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            try:
                ctx = ssl.create_default_context()
                # Bridge uses a self-signed cert for localhost; relax verify.
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                smtp.starttls(context=ctx)
                smtp.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass  # plaintext localhost
            smtp.login(user, password)
            smtp.send_message(msg)
        mark_sent(item_id, message_id=msg["Message-ID"])
        return {"ok": True, "item_id": item_id, "message_id": msg["Message-ID"]}
    except Exception as e:
        err_text = f"{type(e).__name__}: {e}"
        mark_failed(item_id, error=err_text)
        return {"ok": False, "item_id": item_id, "error": err_text}


def send_all_approved(*, dry_run: bool = False, max_items: int = 50,
                      pause_seconds: float = 2.0) -> list:
    """Send every approved item whose send_after has passed.

    Pauses between sends to avoid spam-flag patterns.
    """
    from datetime import datetime, timezone
    from outreach.schema import list_queue

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    queue = list_queue(status="approved", limit=max_items)
    results = []
    for item in queue:
        sa = item.get("send_after")
        if sa and sa > now:
            continue
        r = send_one(item["id"], dry_run=dry_run)
        results.append(r)
        if not dry_run and pause_seconds:
            time.sleep(pause_seconds)
    return results
