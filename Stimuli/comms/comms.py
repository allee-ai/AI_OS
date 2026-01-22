#!/usr/bin/env python3
"""
Open Source Messaging Integration Stub

This module is a placeholder for future integration with open-source 
messaging platforms. The goal is to provide external communication 
channels for AI_OS instances without vendor lock-in.

Planned integrations (contributions welcome):
- Matrix/Element: Federated, self-hosted messaging
- Signal Protocol: End-to-end encrypted messaging
- XMPP/Jabber: Open standard messaging
- IRC: Classic open protocol

The interface should:
- Poll or receive messages from external sources
- Append new messages to Stimuli/stimuli.json
- Download and store media attachments locally
- Maintain message history with unique IDs

See docs/database_integration_plan.md for storage architecture.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Destination paths
INBOX_FILE = Path("Stimuli/stimuli.json")
MEDIA_DIR = Path("Stimuli/media")
INBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def load_inbox() -> List[dict]:
    """Load existing messages from local storage."""
    if not INBOX_FILE.exists():
        return []
    try:
        return json.loads(INBOX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_inbox(items: List[dict]) -> None:
    """Save messages to local storage."""
    INBOX_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_messages(page_size: int = 50) -> List[dict]:
    """
    Fetch messages from external messaging service.
    
    TODO: Implement for your chosen open-source platform:
    - Matrix: Use matrix-nio library
    - Signal: Use signal-cli or libsignal
    - XMPP: Use slixmpp or aioxmpp
    
    Returns:
        List of message dicts with keys: id, sender, body, timestamp
    """
    raise NotImplementedError(
        "Messaging integration not configured. "
        "See docs or contribute an implementation for Matrix, Signal, or XMPP."
    )


def send_message(recipient: str, body: str) -> dict:
    """
    Send a message via external messaging service.
    
    TODO: Implement outbound messaging for your platform.
    
    Returns:
        Message confirmation dict with id and status
    """
    raise NotImplementedError(
        "Outbound messaging not configured. "
        "Implement for your chosen open-source platform."
    )


def poll_and_update() -> int:
    """
    Poll for new messages and update local inbox.
    
    Returns:
        Number of new messages added
    """
    try:
        messages = fetch_messages()
    except NotImplementedError as e:
        print(f"[comms] {e}")
        return 0
    
    inbox = load_inbox()
    existing_ids = {m.get("id") for m in inbox}
    
    new_count = 0
    for msg in messages:
        if msg.get("id") not in existing_ids:
            msg["received_at"] = datetime.now().isoformat()
            inbox.append(msg)
            new_count += 1
    
    if new_count > 0:
        save_inbox(inbox)
        print(f"[comms] Added {new_count} new messages")
    
    return new_count


if __name__ == "__main__":
    print("Open Source Messaging Stub")
    print("=" * 40)
    print("This module awaits implementation.")
    print("Recommended: Matrix/Element for federated messaging")
    print("See: https://matrix.org/docs/develop")
    poll_and_update()
