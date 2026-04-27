"""Proton Mail (or generic IMAP) feed worker.

Polls one feed via IMAP and writes new messages to `sensory_events` as
(source='email', kind='inbound'). Designed for Proton Bridge running on
localhost (127.0.0.1:1143, STARTTLS, self-signed cert) but works against
any IMAP server with `use_ssl` and `starttls` config knobs.

Config schema (stored as JSON in sensory_feeds.config_json):
    {
        "host":              "127.0.0.1",         # required
        "port":              1143,                  # required
        "username":          "you@proton.me",       # required (Bridge wants full address)

        # Credential lookup — use ONE of these (keychain preferred on macOS):
        "password_keychain": {                       # macOS: `security` CLI
            "service":  "AIOS-Proton-Bridge",         # -s
            "account":  "you@proton.me"               # -a (defaults to username if omitted)
        },
        "password_env":      "PROTON_BRIDGE_PASS",   # fallback: env var name

        "mailbox":           "INBOX",                # optional, default INBOX
        "max_per_poll":      20,                     # optional, default 20
        "initial_fetch":     5,                      # optional, default 5 (only first run)
        "use_ssl":           false,                  # default false (Bridge uses STARTTLS)
        "starttls":          true,                   # default true
        "verify_cert":       false                   # default false (Bridge cert is self-signed)
    }

Cursor is the highest UID seen so far (string, monotonic per mailbox).
"""
from __future__ import annotations

import email
import imaplib
import os
import ssl
import subprocess
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from typing import Any, Dict, Optional

from sensory.schema import record_event


_SNIPPET_CHARS = 500
_TEXT_HARD_CAP = 1200  # text column truncated to 4000 in record_event but we keep it small

# Set by _resolve_password to convey a specific failure to the caller.
_last_password_error: Optional[str] = None


# ────────────────────────────────────────────────────────────────────
# Credential resolution
# ────────────────────────────────────────────────────────────────────

def _resolve_password(cfg: Dict[str, Any]) -> Optional[str]:
    """Return the IMAP password from the configured source, or None on failure.

    Prefers macOS Keychain (`password_keychain`); falls back to env var
    (`password_env`). On failure, sets the module-level `_last_password_error`
    so the caller can surface the precise reason.
    """
    global _last_password_error
    _last_password_error = None

    kc = cfg.get("password_keychain")
    if kc:
        service = (kc.get("service") if isinstance(kc, dict) else None) or ""
        account = (kc.get("account") if isinstance(kc, dict) else None) or cfg.get("username", "")
        if not service:
            _last_password_error = "password_keychain.service is required"
            return None
        if not account:
            _last_password_error = "password_keychain.account missing (and no username fallback)"
            return None
        try:
            r = subprocess.run(
                ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
                capture_output=True, text=True, timeout=5,
            )
        except FileNotFoundError:
            _last_password_error = "`security` CLI not found (Keychain lookup is macOS-only)"
            return None
        except Exception as e:
            _last_password_error = f"keychain lookup failed: {e}"
            return None
        if r.returncode != 0:
            _last_password_error = (
                f"keychain entry not found for service='{service}' account='{account}' "
                f"(security exit {r.returncode}: {r.stderr.strip()})"
            )
            return None
        pw = r.stdout.rstrip("\n")
        if not pw:
            _last_password_error = "keychain entry empty"
            return None
        return pw

    env_var = cfg.get("password_env")
    if env_var:
        pw = os.environ.get(env_var)
        if not pw:
            _last_password_error = f"env var {env_var} not set"
            return None
        return pw

    _last_password_error = "no credential source configured"
    return None


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _decode(s: Optional[str]) -> str:
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s))).strip()
    except Exception:
        return s.strip()


def _extract_plaintext(msg: email.message.Message) -> str:
    """Return first plaintext body, decoded; fall back to HTML stripped."""
    if msg.is_multipart():
        # prefer text/plain
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = (part.get("Content-Disposition") or "").lower()
            if ctype == "text/plain" and "attachment" not in disp:
                return _payload_to_str(part)
        # fallback: text/html stripped
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return _strip_html(_payload_to_str(part))
        return ""
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            return _payload_to_str(msg)
        if ctype == "text/html":
            return _strip_html(_payload_to_str(msg))
        return ""


def _payload_to_str(part: email.message.Message) -> str:
    try:
        raw = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")
    except Exception:
        return ""


def _strip_html(html_text: str) -> str:
    # ultra-light HTML strip; we don't need fidelity, just a snippet
    import re
    no_tags = re.sub(r"<[^>]+>", " ", html_text)
    no_ws = re.sub(r"\s+", " ", no_tags)
    return no_ws.strip()


def _format_summary(from_name: str, from_addr: str, subject: str, snippet: str) -> str:
    sender = from_name or from_addr or "unknown"
    if from_name and from_addr and from_name != from_addr:
        sender = f"{from_name} <{from_addr}>"
    subj = subject or "(no subject)"
    snip = (snippet or "").strip().replace("\r", " ").replace("\n", " ")
    if len(snip) > _SNIPPET_CHARS:
        snip = snip[:_SNIPPET_CHARS].rstrip() + "…"
    text = f"From: {sender} | Subject: {subj}"
    if snip:
        text += f" | {snip}"
    return text[:_TEXT_HARD_CAP]


# ────────────────────────────────────────────────────────────────────
# IMAP connect
# ────────────────────────────────────────────────────────────────────

def _connect(cfg: Dict[str, Any]) -> imaplib.IMAP4:
    host = cfg["host"]
    port = int(cfg["port"])
    use_ssl = bool(cfg.get("use_ssl", False))
    starttls = bool(cfg.get("starttls", True))
    verify_cert = bool(cfg.get("verify_cert", False))

    if use_ssl:
        ctx = ssl.create_default_context()
        if not verify_cert:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return imaplib.IMAP4_SSL(host, port, ssl_context=ctx, timeout=30)

    conn = imaplib.IMAP4(host, port, timeout=30)
    if starttls:
        ctx = ssl.create_default_context()
        if not verify_cert:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        conn.starttls(ssl_context=ctx)
    return conn


# ────────────────────────────────────────────────────────────────────
# Public entry point
# ────────────────────────────────────────────────────────────────────

def poll_once(feed: Dict[str, Any]) -> Dict[str, Any]:
    """Poll one IMAP feed. Pure function — no side effects on sensory_feeds row.

    The CLI is responsible for calling mark_feed_run / mark_feed_error.

    Args:
        feed: row dict from get_feeds(); must have 'config' parsed dict.

    Returns:
        {polled, recorded, skipped, errors, cursor (new high-water UID), error_msg}
    """
    cfg = feed.get("config") or {}
    out: Dict[str, Any] = {
        "polled": 0,
        "recorded": 0,
        "skipped": 0,
        "errors": 0,
        "cursor": feed.get("last_cursor"),
        "error_msg": None,
    }

    # Validate required config
    for key in ("host", "port", "username"):
        if not cfg.get(key):
            out["error_msg"] = f"missing config key: {key}"
            return out
    if not cfg.get("password_keychain") and not cfg.get("password_env"):
        out["error_msg"] = "missing credential: set either password_keychain or password_env"
        return out

    password = _resolve_password(cfg)
    if not password:
        # _resolve_password sets a specific message
        out["error_msg"] = _last_password_error or "credential not available"
        return out

    mailbox = cfg.get("mailbox", "INBOX")
    max_per_poll = int(cfg.get("max_per_poll", 20))
    initial_fetch = int(cfg.get("initial_fetch", 5))
    last_uid_str = (feed.get("last_cursor") or "").strip()
    is_initial = not last_uid_str

    try:
        conn = _connect(cfg)
    except Exception as e:
        out["error_msg"] = f"connect failed: {e}"
        return out

    try:
        try:
            conn.login(cfg["username"], password)
        except imaplib.IMAP4.error as e:
            out["error_msg"] = f"login failed: {e}"
            return out

        try:
            typ, _ = conn.select(mailbox, readonly=True)
            if typ != "OK":
                out["error_msg"] = f"select {mailbox} failed: {typ}"
                return out
        except Exception as e:
            out["error_msg"] = f"select failed: {e}"
            return out

        # Build UID range: everything strictly greater than last_uid
        if is_initial:
            # First run: just grab last N to avoid flooding the bus on enable.
            typ, data = conn.uid("SEARCH", None, "ALL")
            if typ != "OK":
                out["error_msg"] = f"uid search failed: {typ}"
                return out
            all_uids = (data[0] or b"").split()
            target_uids = all_uids[-initial_fetch:] if all_uids else []
        else:
            try:
                last_uid = int(last_uid_str)
            except ValueError:
                last_uid = 0
            typ, data = conn.uid("SEARCH", None, f"UID {last_uid + 1}:*")
            if typ != "OK":
                out["error_msg"] = f"uid search failed: {typ}"
                return out
            target_uids = (data[0] or b"").split()
            # IMAP returns the highest UID even if no new messages; filter strict gt
            target_uids = [u for u in target_uids if int(u) > last_uid]

        # Cap per-poll
        target_uids = target_uids[:max_per_poll]
        out["polled"] = len(target_uids)

        new_high_uid = last_uid_str  # may stay unchanged if 0 messages
        for uid_b in target_uids:
            uid = uid_b.decode() if isinstance(uid_b, bytes) else str(uid_b)
            try:
                typ, msg_data = conn.uid("FETCH", uid_b, "(RFC822)")
                if typ != "OK" or not msg_data or not msg_data[0]:
                    out["errors"] += 1
                    continue
                # msg_data[0] is a tuple (header_bytes, raw_bytes)
                raw = msg_data[0][1] if isinstance(msg_data[0], tuple) else msg_data[0]
                if not isinstance(raw, (bytes, bytearray)):
                    out["errors"] += 1
                    continue
                msg = email.message_from_bytes(bytes(raw))

                from_raw = msg.get("From", "")
                from_name, from_addr = parseaddr(from_raw)
                from_name = _decode(from_name)
                subject = _decode(msg.get("Subject", ""))
                message_id = (msg.get("Message-ID") or "").strip()
                date_hdr = msg.get("Date", "")
                try:
                    date_iso = parsedate_to_datetime(date_hdr).isoformat() if date_hdr else None
                except Exception:
                    date_iso = None

                body = _extract_plaintext(msg)
                summary = _format_summary(from_name, from_addr, subject, body)

                rec_id = record_event(
                    source="email",
                    text=summary,
                    kind="inbound",
                    confidence=1.0,
                    meta={
                        "from_name": from_name,
                        "from_addr": from_addr,
                        "subject": subject,
                        "message_id": message_id,
                        "date": date_iso,
                        "mailbox": mailbox,
                        "uid": uid,
                        "feed_id": feed.get("id"),
                        "feed_name": feed.get("display_name"),
                    },
                )
                if rec_id:
                    out["recorded"] += 1
                else:
                    out["skipped"] += 1  # consent block or salience drop
                # Track high water regardless — we successfully observed it
                if not new_high_uid or int(uid) > int(new_high_uid or 0):
                    new_high_uid = uid
            except Exception as e:
                out["errors"] += 1
                # Continue with next message
                if not out["error_msg"]:
                    out["error_msg"] = f"per-message error on uid {uid}: {e}"

        out["cursor"] = new_high_uid
        return out

    finally:
        try:
            conn.logout()
        except Exception:
            pass
