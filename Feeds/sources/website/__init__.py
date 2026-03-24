"""
Website Feed Module
===================

Embeds a live website view in the Feeds viewer.
No OAuth needed — just a URL. Useful for monitoring your own site,
dashboards, or any web content alongside other feeds.

Events are emitted when the URL changes (via API) so triggers can react.
"""

from typing import List, Dict, Any, Optional
from Feeds.events import EventTypeDefinition, register_event_types, emit_event


# ============================================================================
# Event Types
# ============================================================================

WEBSITE_EVENT_TYPES = [
    EventTypeDefinition(
        name="url_changed",
        description="The monitored URL was changed",
        payload_schema={
            "old_url": "str",
            "new_url": "str",
        },
        example_payload={
            "old_url": "https://allee-ai.com",
            "new_url": "https://allee-ai.com/learning.html",
        },
    ),
    EventTypeDefinition(
        name="page_loaded",
        description="The website page was loaded in the viewer",
        payload_schema={
            "url": "str",
            "title": "str",
        },
        example_payload={
            "url": "https://allee-ai.com",
            "title": "Allee - Developer",
        },
    ),
]


# Register event types on import
register_event_types("website", WEBSITE_EVENT_TYPES)


# ============================================================================
# Configuration
# ============================================================================

# No OAuth needed — just a URL stored in settings
WEBSITE_CONFIG = {
    "provider": "website",
    "auth_type": "none",
    "settings": {
        "url": "https://allee-ai.com",
    },
}


# ============================================================================
# URL State
# ============================================================================

_current_url: str = "https://allee-ai.com"


def get_url() -> str:
    """Return the currently configured website URL."""
    return _current_url


def set_url(url: str) -> str:
    """Update the website URL and emit a url_changed event."""
    global _current_url
    old = _current_url
    _current_url = url
    if old != url:
        emit_event(
            feed_name="website",
            event_type="url_changed",
            payload={"old_url": old, "new_url": url},
        )
    return url
