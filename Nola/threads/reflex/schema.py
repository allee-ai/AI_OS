"""
Reflex Thread Schema
====================
Database functions for reflex patterns (greetings, shortcuts, system triggers).

This thread uses the generic module system from the main schema.
Tables are dynamically created per module:
    - thread_reflex_greetings
    - thread_reflex_shortcuts  
    - thread_reflex_system
"""

# Database connection from central location
from data.db import get_connection

# Generic module functions - these will be refactored later
try:
    from Nola.threads.schema import (
        push_to_module,
        pull_from_module,
        delete_from_module,
        get_registered_modules,
    )
except ImportError:
    from ..schema import (
        push_to_module,
        pull_from_module,
        delete_from_module,
        get_registered_modules,
    )


def get_greetings(level: int = 2):
    """Get greeting patterns."""
    return pull_from_module("reflex", "greetings", level=level)


def get_shortcuts(level: int = 2):
    """Get user shortcuts."""
    return pull_from_module("reflex", "shortcuts", level=level)


def get_system_reflexes(level: int = 2):
    """Get system reflexes."""
    return pull_from_module("reflex", "system", level=level)


def add_greeting(key: str, response: str, weight: float = 0.8):
    """Add a greeting response."""
    push_to_module(
        thread="reflex",
        module="greetings",
        key=key,
        metadata={"type": "pattern", "description": f"Greeting: {key}"},
        data={"value": response},
        level=1,
        weight=weight
    )


def add_shortcut(trigger: str, response: str, description: str = ""):
    """Add a user shortcut."""
    push_to_module(
        thread="reflex",
        module="shortcuts",
        key=f"shortcut_{trigger.lower().replace(' ', '_')}",
        metadata={"type": "shortcut", "description": description or f"Shortcut: {trigger}"},
        data={"trigger": trigger, "response": response},
        level=1,
        weight=0.7
    )


def add_system_reflex(key: str, trigger_type: str, action: str, description: str = "", weight: float = 0.9):
    """Add a system reflex."""
    push_to_module(
        thread="reflex",
        module="system",
        key=key,
        metadata={"type": "system", "description": description or f"System: {key}"},
        data={"trigger_type": trigger_type, "action": action},
        level=1,
        weight=weight
    )


def delete_greeting(key: str) -> bool:
    """Delete a greeting."""
    return delete_from_module("reflex", "greetings", key)


def delete_shortcut(key: str) -> bool:
    """Delete a shortcut."""
    return delete_from_module("reflex", "shortcuts", key)


def delete_system_reflex(key: str) -> bool:
    """Delete a system reflex."""
    return delete_from_module("reflex", "system", key)


__all__ = [
    'get_greetings',
    'get_shortcuts', 
    'get_system_reflexes',
    'add_greeting',
    'add_shortcut',
    'add_system_reflex',
    'delete_greeting',
    'delete_shortcut',
    'delete_system_reflex',
]
