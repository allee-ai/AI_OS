"""
Outbox Module
=============
Generic motor-approval surface. Any subconscious motor (goal proposal,
email draft, file edit, message, "thought share") can drop a card here.
The user reviews on the website and approves / rejects / edits in one
click. Approval emits a unified_events row so the system can learn from
the supervision signal.

The outbox is the joint between the substrate (which acts) and the
operator (who decides). Every Tier-2 partner-job (email triage, promise
nag, weekly review, outcome auditor) reduces to "produce an outbox card."
"""

from .api import router
from .schema import (
    init_outbox_table,
    create_card,
    list_cards,
    get_card,
    resolve_card,
    count_pending,
)
from . import copilot_inbox

__all__ = [
    "router",
    "init_outbox_table",
    "create_card",
    "list_cards",
    "get_card",
    "resolve_card",
    "count_pending",
    "copilot_inbox",
]
