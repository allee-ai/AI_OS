"""
Nola Chat Module
----------------
Self-contained module for conversation management.

Exports:
- router: FastAPI router with all chat endpoints
- websocket_manager: WebSocket connection manager
- Schema functions for DB operations
"""

from .api import router, websocket_manager
from .schema import (
    init_convos_tables,
    save_conversation,
    add_turn,
    get_conversation,
    list_conversations,
    rename_conversation,
    archive_conversation,
    delete_conversation,
    update_conversation_weight,
    increment_conversation_weight,
    get_unindexed_high_weight_convos,
    mark_conversation_indexed,
)

__all__ = [
    "router",
    "websocket_manager",
    "init_convos_tables",
    "save_conversation", 
    "add_turn",
    "get_conversation",
    "list_conversations",
    "rename_conversation",
    "archive_conversation",
    "delete_conversation",
    "update_conversation_weight",
    "increment_conversation_weight",
    "get_unindexed_high_weight_convos",
    "mark_conversation_indexed",
]
