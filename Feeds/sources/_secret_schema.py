"""
Per-Feed Secret Schemas
========================

Single source of truth for which credential fields each feed needs.
The frontend fetches this via `GET /api/feeds/{feed}/secret-schema`
and renders a form.  The form POSTs back via
`POST /api/feeds/{feed}/secrets/bulk`, which writes through
`agent.core.secrets.store_secret()` (Fernet-encrypted on disk).

Fields are NEVER returned to the frontend with their values.  The only
readable signal is `has_value: bool` (computed from the secrets table).

Each field is a dict:
    key:       str   — stored in the secrets table
    label:     str   — human label in the UI
    type:      str   — "password" | "text" | "number" | "select"
    required:  bool  — if true, `configured=False` until present
    hint:      str   — tooltip / help text
    default:   str   — prefilled (for non-secret fields like host/port)
    options:   list  — only for type=select
"""

from __future__ import annotations

from typing import Dict, List, Any


SECRET_SCHEMAS: Dict[str, List[Dict[str, Any]]] = {
    # ─────────────── Discord ───────────────
    # Paste-only: bot token from https://discord.com/developers/applications
    "discord": [
        {
            "key": "bot_token",
            "label": "Bot Token",
            "type": "password",
            "required": True,
            "hint": "Discord Developer Portal → your app → Bot → Reset Token. Starts with 'MTE...' or 'MT...'.",
        },
        {
            "key": "application_id",
            "label": "Application ID",
            "type": "text",
            "required": False,
            "hint": "Optional. Needed for slash commands.",
        },
        {
            "key": "watch_user_id",
            "label": "Watch User ID (DMs)",
            "type": "text",
            "required": False,
            "hint": "Your Discord user ID. When set, DMs to the bot from this user are high-priority.",
        },
    ],

    # ─────────────── GitHub ───────────────
    # Paste-only: Personal Access Token, classic or fine-grained.
    "github": [
        {
            "key": "pat",
            "label": "Personal Access Token",
            "type": "password",
            "required": True,
            "hint": "github.com/settings/tokens → classic or fine-grained. Scopes: notifications, repo (read), user.",
        },
        {
            "key": "username",
            "label": "GitHub Username",
            "type": "text",
            "required": False,
            "hint": "Optional. Used to scope 'mentions' to you only.",
        },
    ],

    # ─────────────── Email / Proton (IMAP Bridge) ───────────────
    # Proton has no public OAuth.  Users run Proton Bridge locally,
    # which exposes IMAP/SMTP on localhost with a generated password.
    "email": [
        {
            "key": "provider",
            "label": "Provider",
            "type": "select",
            "required": True,
            "options": ["proton-bridge", "gmail-app-password", "generic-imap"],
            "default": "proton-bridge",
            "hint": "Proton requires the local Bridge app. Gmail needs an App Password (2FA).",
        },
        {
            "key": "imap_host",
            "label": "IMAP Host",
            "type": "text",
            "required": True,
            "default": "127.0.0.1",
            "hint": "Proton Bridge: 127.0.0.1.  Gmail: imap.gmail.com.",
        },
        {
            "key": "imap_port",
            "label": "IMAP Port",
            "type": "number",
            "required": True,
            "default": "1143",
            "hint": "Proton Bridge default: 1143 (STARTTLS).  Gmail: 993 (SSL).",
        },
        {
            "key": "imap_user",
            "label": "Email Address",
            "type": "text",
            "required": True,
            "hint": "The address you log in with.",
        },
        {
            "key": "imap_pass",
            "label": "IMAP Password",
            "type": "password",
            "required": True,
            "hint": "Proton: bridge-generated password.  Gmail: 16-char app password.",
        },
        {
            "key": "smtp_host",
            "label": "SMTP Host (optional, for sending)",
            "type": "text",
            "required": False,
            "default": "127.0.0.1",
            "hint": "Proton Bridge: 127.0.0.1.  Gmail: smtp.gmail.com.",
        },
        {
            "key": "smtp_port",
            "label": "SMTP Port",
            "type": "number",
            "required": False,
            "default": "1025",
            "hint": "Proton Bridge: 1025 (STARTTLS).  Gmail: 587 (STARTTLS) or 465 (SSL).",
        },
        {
            "key": "poll_folder",
            "label": "Folder to poll",
            "type": "text",
            "required": False,
            "default": "INBOX",
            "hint": "Which IMAP folder to watch for new mail.",
        },
    ],

    # ─────────────── Calendar (CalDAV) ───────────────
    "calendar": [
        {
            "key": "provider",
            "label": "Provider",
            "type": "select",
            "required": True,
            "options": ["caldav", "google-ics"],
            "default": "caldav",
            "hint": "CalDAV works with Proton, Fastmail, iCloud (app password).",
        },
        {
            "key": "caldav_url",
            "label": "CalDAV URL",
            "type": "text",
            "required": True,
            "hint": "Full URL to your principal, e.g. https://caldav.icloud.com/.",
        },
        {
            "key": "caldav_user",
            "label": "Username",
            "type": "text",
            "required": True,
            "hint": "Your account email.",
        },
        {
            "key": "caldav_pass",
            "label": "Password",
            "type": "password",
            "required": True,
            "hint": "iCloud/Fastmail require an app-specific password.",
        },
    ],

    # ─────────────── Website / RSS ───────────────
    # No auth, just a list of URLs.
    "website": [
        {
            "key": "urls",
            "label": "Feed URLs (one per line)",
            "type": "textarea",
            "required": True,
            "hint": "Each line is a distinct RSS/Atom URL or a sitemap to scrape.",
        },
        {
            "key": "user_agent",
            "label": "User-Agent",
            "type": "text",
            "required": False,
            "default": "AIOS-Feeds/1.0",
            "hint": "Some sites block default UAs.",
        },
    ],
}


def get_schema(feed_name: str) -> List[Dict[str, Any]]:
    return SECRET_SCHEMAS.get(feed_name, [])


def required_keys(feed_name: str) -> List[str]:
    return [f["key"] for f in get_schema(feed_name) if f.get("required")]


__all__ = ["SECRET_SCHEMAS", "get_schema", "required_keys"]
