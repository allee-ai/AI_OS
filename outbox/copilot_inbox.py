"""
copilot_inbox — phone → Copilot bridge.

Pattern: you write a request on the AIOS mobile dashboard. It lands in
the outbox table with motor='copilot_request' and is mirrored as a
markdown file in workspace/_copilot_inbox/ so it's impossible to miss
when VS Code opens. ``scripts/turn_start.py`` reads pending requests
both from the local DB and (best-effort) from the droplet API and prints
them at the top of the banner. After Copilot finishes the work, run
``scripts/copilot_inbox_done.py <id>`` (or call ``mark_done`` here)
which closes the outbox row and removes the mirror file.

This module deliberately stays in `outbox/` because copilot_inbox is
just a specific motor flowing through the same table — direction
inverted. The outbox already supports user→AIOS approvals; this is the
mirrored AIOS-user → Copilot-VSCode lane.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional

from data.db import get_connection

from .schema import create_card, get_card, resolve_card

ROOT = Path(__file__).resolve().parent.parent
MIRROR_DIR = ROOT / "workspace" / "_copilot_inbox"
MOTOR = "copilot_request"


def _slug(s: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return (s or "request")[:n]


def _mirror_path(card_id: int, title: str) -> Path:
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    return MIRROR_DIR / f"{card_id:04d}-{_slug(title)}.md"


def _write_mirror(card: Dict[str, Any]) -> Optional[str]:
    """Drop a markdown mirror so VS Code shows it in the explorer.

    Best-effort. Returns the path string if written. Never raises.
    """
    try:
        path = _mirror_path(int(card["id"]), card.get("title") or "")
        body = card.get("body") or ""
        ctx = card.get("context") or {}
        prio = card.get("priority") or 0.5
        created = card.get("created_at") or ""
        text = (
            f"# {card.get('title') or '(untitled)'}\n\n"
            f"**from phone** • priority {prio:.2f} • {created}\n"
            f"**outbox id**: {card['id']}\n\n"
            f"---\n\n"
            f"{body}\n\n"
        )
        if ctx:
            text += "## context\n\n```json\n" + json.dumps(ctx, indent=2) + "\n```\n\n"
        text += (
            "---\n"
            f"_To mark done after acting:_ `python scripts/copilot_inbox_done.py {card['id']}`\n"
        )
        path.write_text(text)
        return str(path.relative_to(ROOT))
    except Exception:
        return None


def _remove_mirror(card_id: int) -> bool:
    """Delete the mirror file for a card. Returns True if a file was removed."""
    if not MIRROR_DIR.exists():
        return False
    removed = False
    prefix = f"{int(card_id):04d}-"
    for p in MIRROR_DIR.glob(f"{prefix}*.md"):
        try:
            p.unlink()
            removed = True
        except Exception:
            pass
    return removed


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def submit(
    title: str,
    body: str = "",
    priority: float = 0.6,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a copilot_request outbox card + write the workspace mirror."""
    card_id = create_card(
        motor=MOTOR,
        title=title,
        body=body,
        context=context or {},
        priority=priority,
    )
    card = get_card(card_id) or {"id": card_id}
    mirror = _write_mirror(card)
    if mirror:
        card["mirror_path"] = mirror
    return card


def pending(limit: int = 20) -> List[Dict[str, Any]]:
    """Return pending copilot_request cards, highest priority first."""
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT id, title, body, priority, created_at "
            "FROM outbox WHERE motor=? AND status='pending' "
            "ORDER BY priority DESC, created_at ASC LIMIT ?",
            (MOTOR, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_done(
    card_id: int,
    note: Optional[str] = None,
    commit_sha: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Close a copilot_request: outbox status=approved + remove mirror file.

    `commit_sha`, if provided, is folded into the resolution_note so the
    record points at exactly which commit fulfilled the request.
    """
    if commit_sha:
        suffix = f" [commit {commit_sha[:12]}]"
        note = (note or "done") + suffix
    card = resolve_card(int(card_id), status="approved", note=note)
    if card is None:
        return None
    _remove_mirror(int(card_id))
    return card


def fetch_droplet_pending(
    base_url: Optional[str] = None,
    timeout_s: float = 2.0,
) -> List[Dict[str, Any]]:
    """Best-effort GET of pending copilot_requests from a remote AIOS host.

    Used by turn_start.py so VS Code on the laptop can see requests that
    were submitted from the phone (which talks to the droplet). Silent
    failure is fine — we just won't show that section.

    Honors AIOS_DROPLET_URL env var. AIOS_API_TOKEN is added as a Bearer
    header if present.
    """
    base_url = base_url or os.getenv("AIOS_DROPLET_URL", "")
    if not base_url:
        return []
    base_url = base_url.rstrip("/")
    try:
        import urllib.request
        url = f"{base_url}/api/outbox?motor={MOTOR}&status=pending&limit=20"
        req = urllib.request.Request(url)
        token = os.getenv("AIOS_API_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def mark_droplet_done(
    droplet_card_id: int,
    note: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_s: float = 4.0,
) -> bool:
    """POST /api/outbox/{id}/approve to the droplet to close a remote card."""
    base_url = base_url or os.getenv("AIOS_DROPLET_URL", "")
    if not base_url:
        return False
    base_url = base_url.rstrip("/")
    try:
        import urllib.request
        payload = json.dumps({"note": note}).encode("utf-8")
        url = f"{base_url}/api/outbox/{int(droplet_card_id)}/approve"
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        token = os.getenv("AIOS_API_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


def sync_from_droplet() -> List[Dict[str, Any]]:
    """Pull pending copilot_requests from the droplet, mirror as files.

    Returns the list of cards that now have local mirror files. Each card
    dict gains:
        - mirror_path: workspace-relative path to the .md mirror
        - droplet_id:  remote outbox.id (so the done-script can close it)
    Does not write to local DB — droplet remains source of truth for
    these rows.
    """
    cards = fetch_droplet_pending()
    out: List[Dict[str, Any]] = []
    for c in cards:
        try:
            droplet_id = int(c.get("id"))
            # Use a separate id-space for mirrors of droplet rows so we
            # don't collide with locally-created copilot_requests.
            mirror_id = 900000 + droplet_id  # 9xxxxxx prefix = "from droplet"
            c2 = dict(c)
            c2["id"] = mirror_id
            c2["droplet_id"] = droplet_id
            mirror = _write_mirror(c2)
            if mirror:
                # Append a hint so Copilot knows how to close it
                try:
                    p = ROOT / mirror
                    txt = p.read_text()
                    if "droplet_id" not in txt:
                        p.write_text(
                            txt
                            + f"\n_droplet_id_: `{droplet_id}` "
                            f"(use `python scripts/copilot_inbox_done.py "
                            f"--droplet {droplet_id}` to close)\n"
                        )
                except Exception:
                    pass
                c2["mirror_path"] = mirror
            out.append(c2)
        except Exception:
            continue
    return out


__all__ = [
    "submit",
    "pending",
    "mark_done",
    "fetch_droplet_pending",
    "mark_droplet_done",
    "sync_from_droplet",
    "MOTOR",
    "MIRROR_DIR",
]
