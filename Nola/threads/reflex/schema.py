"""
Reflex Thread Schema
====================
Quick patterns, shortcuts, and triggers.

This thread is a dashboard for reflexive responses - like Form, it's tool-like
rather than data-heavy. Currently uses in-memory storage as it's minimally designed.

Future: Could store patterns in a simple JSON config or minimal DB table.
"""

from typing import List, Dict, Any


# In-memory storage for now (patterns are lightweight)
_GREETINGS: Dict[str, Dict] = {}
_SHORTCUTS: Dict[str, Dict] = {}
_SYSTEM_REFLEXES: Dict[str, Dict] = {}


def get_greetings(level: int = 2) -> List[Dict]:
    """Get greeting patterns."""
    return [
        {"key": k, "data": v, "metadata": {"type": "pattern"}, "level": 1, "weight": v.get("weight", 0.8)}
        for k, v in _GREETINGS.items()
    ]


def get_shortcuts(level: int = 2) -> List[Dict]:
    """Get user shortcuts."""
    return [
        {"key": k, "data": v, "metadata": {"type": "shortcut"}, "level": 1, "weight": 0.7}
        for k, v in _SHORTCUTS.items()
    ]


def get_system_reflexes(level: int = 2) -> List[Dict]:
    """Get system reflexes."""
    return [
        {"key": k, "data": v, "metadata": {"type": "system"}, "level": 1, "weight": v.get("weight", 0.9)}
        for k, v in _SYSTEM_REFLEXES.items()
    ]


def add_greeting(key: str, response: str, weight: float = 0.8) -> None:
    """Add a greeting response."""
    _GREETINGS[key] = {"value": response, "weight": weight}


def add_shortcut(trigger: str, response: str, description: str = "") -> None:
    """Add a user shortcut."""
    key = f"shortcut_{trigger.lower().replace(' ', '_')}"
    _SHORTCUTS[key] = {"trigger": trigger, "response": response, "description": description}


def add_system_reflex(key: str, trigger_type: str, action: str, description: str = "", weight: float = 0.9) -> None:
    """Add a system reflex."""
    _SYSTEM_REFLEXES[key] = {
        "trigger_type": trigger_type,
        "action": action,
        "description": description,
        "weight": weight
    }


def delete_greeting(key: str) -> bool:
    """Delete a greeting."""
    if key in _GREETINGS:
        del _GREETINGS[key]
        return True
    return False


def delete_shortcut(key: str) -> bool:
    """Delete a shortcut."""
    if key in _SHORTCUTS:
        del _SHORTCUTS[key]
        return True
    return False


def delete_system_reflex(key: str) -> bool:
    """Delete a system reflex."""
    if key in _SYSTEM_REFLEXES:
        del _SYSTEM_REFLEXES[key]
        return True
    return False


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
