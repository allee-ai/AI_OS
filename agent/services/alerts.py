"""
agent/services/alerts.py — One place for "wake the user up" alerts.

Both scripts/ping.py (CLI) and agent/threads/form/tools/executables/notify.py
(tool) call this so the mac + phone alert behaviour stays in sync.

Layers, in order of reliability:
  1. dashboard — already handled by the notifications table (caller's job)
  2. macOS banner via osascript — best-effort, may be silenced by Focus/perms
  3. macOS sound via afplay — not permission-gated, reliable
  4. macOS spoken fallback (say) — urgent priority only
  5. phone via ntfy.sh — opt-in via AIOS_NTFY_TOPIC env var

Everything is non-blocking and silent on failure.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path


_SOUND_MAP = {
    "urgent": "Sosumi",
    "high": "Glass",
}

_SOUND_FILE_MAP = {
    "urgent": "/System/Library/Sounds/Sosumi.aiff",
    "high": "/System/Library/Sounds/Glass.aiff",
}

_NTFY_PRIO_MAP = {"urgent": "5", "high": "4", "normal": "3", "low": "2"}


def _load_env_file_once() -> None:
    """Idempotent .env loader — only runs first time, only fills missing keys."""
    if getattr(_load_env_file_once, "_loaded", False):
        return
    _load_env_file_once._loaded = True  # type: ignore[attr-defined]
    # scripts/ and agent/services/ both sit under AI_OS root.
    root = Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass


def fire_alerts(
    message: str,
    priority: str,
    nid: int | str | None = None,
    source: str = "aios",
) -> None:
    """Fire all opted-in alert channels. Non-blocking, never raises."""
    _load_env_file_once()
    _fire_mac(message, priority, nid, source)
    _fire_phone(message, priority, nid, source)


def _fire_mac(message: str, priority: str, nid, source: str) -> None:
    try:
        if platform.system() != "Darwin":
            return
        # Banner (best-effort).
        try:
            title = f"AIOS {priority.upper()}" if priority in ("high", "urgent") else "AIOS"
            subtitle = f"#{nid} — {source}" if nid is not None else source
            safe_msg = message.replace("\\", "\\\\").replace('"', '\\"')
            parts = [
                f'display notification "{safe_msg}"',
                f'with title "{title}"',
                f'subtitle "{subtitle}"',
            ]
            sound = _SOUND_MAP.get(priority, "")
            if sound:
                parts.append(f'sound name "{sound}"')
            subprocess.Popen(
                ["osascript", "-e", " ".join(parts)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
        # Audio — reliable even with Focus on / notifications denied.
        sound_file = _SOUND_FILE_MAP.get(priority)
        if sound_file:
            try:
                subprocess.Popen(
                    ["afplay", sound_file],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        # Spoken fallback on urgent only.
        if priority == "urgent":
            try:
                safe_say = message[:120].replace('"', "'")
                subprocess.Popen(
                    ["say", "-r", "200", safe_say],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
        # Terminal bell — flashes the terminal tab if one is live.
        if priority in ("high", "urgent"):
            try:
                sys.stderr.write("\a")
                sys.stderr.flush()
            except Exception:
                pass
    except Exception:
        pass


def _fire_phone(message: str, priority: str, nid, source: str) -> None:
    """Push via ntfy.sh if AIOS_NTFY_TOPIC is configured. High/urgent only."""
    try:
        topic = os.environ.get("AIOS_NTFY_TOPIC", "").strip()
        if not topic:
            return
        if priority not in ("high", "urgent"):
            return
        server = os.environ.get("AIOS_NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        url = f"{server}/{topic}"
        headers = {
            "Title": f"AIOS {priority.upper()}",
            "Priority": _NTFY_PRIO_MAP.get(priority, "3"),
            "Tags": "warning" if priority == "urgent" else "bell",
        }
        if nid is not None:
            headers["X-Nid"] = str(nid)

        # Primary path: urllib with certifi CA bundle. Python.org macOS
        # Python ships without system CAs, so default urllib fails SSL
        # handshake to ntfy.sh silently. certifi is in requirements.
        try:
            import ssl
            import urllib.request as _urlreq
            try:
                import certifi
                ctx = ssl.create_default_context(cafile=certifi.where())
            except Exception:
                ctx = ssl.create_default_context()
            req = _urlreq.Request(
                url, data=message.encode("utf-8"),
                method="POST", headers=headers,
            )
            _urlreq.urlopen(req, timeout=4, context=ctx).read()
            return
        except Exception:
            pass

        # Fallback: shell out to curl which uses macOS system CAs.
        try:
            curl_args = ["curl", "-sS", "--max-time", "4", "-X", "POST"]
            for k, v in headers.items():
                curl_args += ["-H", f"{k}: {v}"]
            curl_args += ["--data-binary", message, url]
            subprocess.Popen(
                curl_args,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    except Exception:
        pass
