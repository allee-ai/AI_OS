"""
outreach/ — Nola's outbound communication layer.

Builds on top of Feeds/sources/email (which already does IMAP read +
draft) by adding the missing piece: a queue of outbound messages with
an explicit human send-gate.

Standing rule: nothing leaves drafted state without explicit approval
via scripts/outreach.py --approve <id>.  Approved items are then sent
via --send <id> (or --send-approved for batch).

Persona: every outreach goes out as Nola from assistant@allee-ai.com.
The voice is consistent across surfaces because the system prompt is
loaded from philosophy thread + identity.machine.

This module deliberately does not own SMTP credentials — it reads them
from the existing Feeds/sources/email Proton Bridge config so there's
one source of truth for inbound + outbound.
"""

from outreach.schema import (
    init_outreach_tables,
    queue_draft,
    approve_draft,
    reject_draft,
    list_queue,
    get_item,
    mark_sent,
    mark_failed,
    set_send_after,
)

__all__ = [
    "init_outreach_tables",
    "queue_draft",
    "approve_draft",
    "reject_draft",
    "list_queue",
    "get_item",
    "mark_sent",
    "mark_failed",
    "set_send_after",
]
