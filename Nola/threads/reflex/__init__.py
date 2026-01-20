"""Reflex Thread - quick patterns, shortcuts, and triggers."""
from .adapter import ReflexThreadAdapter
from .api import router
from .schema import (
    get_greetings, get_shortcuts, get_system_reflexes,
    add_greeting, add_shortcut, add_system_reflex,
    delete_greeting, delete_shortcut, delete_system_reflex,
)

__all__ = [
    "ReflexThreadAdapter",
    "router",
    # Schema functions
    "get_greetings", "get_shortcuts", "get_system_reflexes",
    "add_greeting", "add_shortcut", "add_system_reflex",
    "delete_greeting", "delete_shortcut", "delete_system_reflex",
]
