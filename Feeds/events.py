"""
Feed Events System
==================

Event registry and logging for feed modules.
Each feed can define event types (e.g., email_received, message_sent).
Events are logged to the unified event log for history and triggering reflexes.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
import json


class EventPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class FeedEvent:
    """A normalized event from any feed source."""
    feed_name: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    event_id: Optional[str] = None
    priority: EventPriority = EventPriority.NORMAL
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feed_name": self.feed_name,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
            "priority": self.priority.name,
        }


@dataclass
class EventTypeDefinition:
    """Definition of an event type a feed can emit."""
    name: str
    description: str
    payload_schema: Dict[str, str] = field(default_factory=dict)  # field_name -> type hint
    example_payload: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Event Registry
# ============================================================================

# Global registry of event types per feed
_EVENT_REGISTRY: Dict[str, List[EventTypeDefinition]] = {}

# Callbacks for event handlers (reflex triggers will register here)
_EVENT_HANDLERS: Dict[str, List[Callable[[FeedEvent], None]]] = {}


def register_event_types(feed_name: str, event_types: List[EventTypeDefinition]) -> None:
    """Register event types for a feed module."""
    _EVENT_REGISTRY[feed_name] = event_types


def get_event_types(feed_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Get registered event types, optionally filtered by feed."""
    if feed_name:
        types = _EVENT_REGISTRY.get(feed_name, [])
        return {feed_name: [asdict(t) for t in types]}
    
    return {
        name: [asdict(t) for t in types]
        for name, types in _EVENT_REGISTRY.items()
    }


def get_all_triggers() -> List[Dict[str, Any]]:
    """Get all available triggers (feed + event_type pairs) for Reflex UI."""
    triggers = []
    for feed_name, event_types in _EVENT_REGISTRY.items():
        for et in event_types:
            triggers.append({
                "feed_name": feed_name,
                "event_type": et.name,
                "description": et.description,
                "payload_schema": et.payload_schema,
            })
    return triggers


# ============================================================================
# Event Emission & Logging
# ============================================================================

def emit_event(
    feed_name: str,
    event_type: str,
    payload: Dict[str, Any],
    priority: EventPriority = EventPriority.NORMAL,
    event_id: Optional[str] = None,
) -> FeedEvent:
    """
    Emit a feed event. This:
    1. Creates the event object
    2. Logs it to the unified event log (if available)
    3. Notifies registered handlers (for reflex triggers)
    
    Args:
        feed_name: Source feed (e.g., "gmail", "discord")
        event_type: Type of event (e.g., "email_received", "message_sent")
        payload: Event-specific data
        priority: Event priority for ordering
        event_id: Optional unique ID for deduplication
    
    Returns:
        The created FeedEvent
    """
    event = FeedEvent(
        feed_name=feed_name,
        event_type=event_type,
        payload=payload,
        priority=priority,
        event_id=event_id,
    )
    
    # Log to unified event log
    _log_feed_event(event)
    
    # Notify handlers (reflex triggers)
    _notify_handlers(event)
    
    return event


def _log_feed_event(event: FeedEvent) -> Optional[int]:
    """Log event to the unified event log if available."""
    try:
        from agent.threads.log.schema import log_event
        
        # Create human-readable description
        data = f"[{event.feed_name}] {event.event_type}"
        if "subject" in event.payload:
            data += f": {event.payload['subject']}"
        elif "message" in event.payload:
            msg = event.payload["message"]
            data += f": {msg[:50]}..." if len(msg) > 50 else f": {msg}"
        elif "title" in event.payload:
            data += f": {event.payload['title']}"
        
        return log_event(
            event_type="feed",
            data=data,
            metadata={
                "feed_name": event.feed_name,
                "event_type": event.event_type,
                "payload": event.payload,
                "event_id": event.event_id,
                "priority": event.priority.name,
            },
            source=f"feed.{event.feed_name}",
        )
    except ImportError:
        # Log thread not available - this is a TODO
        print(f"[FEEDS] Event not logged (log thread unavailable): {event.feed_name}/{event.event_type}")
        return None
    except Exception as e:
        print(f"[FEEDS] Failed to log event: {e}")
        return None


def _notify_handlers(event: FeedEvent) -> None:
    """Notify registered event handlers and execute reflex triggers."""
    import asyncio
    
    # Global handlers (listen to all events)
    for handler in _EVENT_HANDLERS.get("*", []):
        try:
            result = handler(event)
            # Handle async handlers
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(result)
                    else:
                        loop.run_until_complete(result)
                except RuntimeError:
                    asyncio.run(result)
        except Exception as e:
            print(f"[FEEDS] Handler error: {e}")
    
    # Feed-specific handlers
    key = f"{event.feed_name}.{event.event_type}"
    for handler in _EVENT_HANDLERS.get(key, []):
        try:
            result = handler(event)
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(result)
                    else:
                        loop.run_until_complete(result)
                except RuntimeError:
                    asyncio.run(result)
        except Exception as e:
            print(f"[FEEDS] Handler error for {key}: {e}")
    
    # Execute reflex triggers
    try:
        from agent.threads.reflex.executor import execute_matching_triggers
        
        async def run_triggers():
            await execute_matching_triggers(
                feed_name=event.feed_name,
                event_type=event.event_type,
                event_payload=event.payload,
            )
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(run_triggers())
            else:
                loop.run_until_complete(run_triggers())
        except RuntimeError:
            asyncio.run(run_triggers())
    except ImportError:
        # Reflex executor not available
        pass
    except Exception as e:
        print(f"[FEEDS] Trigger execution error: {e}")


def register_handler(
    handler: Callable[[FeedEvent], None],
    feed_name: Optional[str] = None,
    event_type: Optional[str] = None,
) -> None:
    """
    Register a handler for feed events.
    
    Args:
        handler: Callback function receiving FeedEvent
        feed_name: Filter to specific feed (None = all feeds)
        event_type: Filter to specific event type (None = all types)
    """
    if feed_name and event_type:
        key = f"{feed_name}.{event_type}"
    elif feed_name:
        key = f"{feed_name}.*"
    else:
        key = "*"
    
    if key not in _EVENT_HANDLERS:
        _EVENT_HANDLERS[key] = []
    _EVENT_HANDLERS[key].append(handler)


def unregister_handler(handler: Callable[[FeedEvent], None]) -> None:
    """Remove a handler from all event subscriptions."""
    for key in _EVENT_HANDLERS:
        if handler in _EVENT_HANDLERS[key]:
            _EVENT_HANDLERS[key].remove(handler)


# ============================================================================
# Event History Query
# ============================================================================

def get_recent_events(
    feed_name: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Get recent feed events from the log.
    
    Args:
        feed_name: Filter by feed source
        event_type: Filter by event type
        limit: Maximum events to return
    
    Returns:
        List of event records from unified_events
    """
    try:
        from agent.threads.log.schema import get_events
        
        # Query events with type "feed"
        events = get_events(event_type="feed", limit=limit)
        
        # Filter by feed_name and event_type if specified
        filtered = []
        for e in events:
            metadata = e.get("metadata", {})
            if feed_name and metadata.get("feed_name") != feed_name:
                continue
            if event_type and metadata.get("event_type") != event_type:
                continue
            filtered.append(e)
        
        return filtered
    except ImportError:
        return []


# ============================================================================
# Built-in Event Types (Common across many feeds)
# ============================================================================

COMMON_EVENT_TYPES = {
    "message_received": EventTypeDefinition(
        name="message_received",
        description="A new message was received",
        payload_schema={"sender": "str", "content": "str", "channel": "str"},
        example_payload={"sender": "user@example.com", "content": "Hello!", "channel": "general"},
    ),
    "message_sent": EventTypeDefinition(
        name="message_sent",
        description="A message was sent",
        payload_schema={"recipient": "str", "content": "str", "channel": "str"},
        example_payload={"recipient": "user@example.com", "content": "Hi there!", "channel": "general"},
    ),
    "connection_status": EventTypeDefinition(
        name="connection_status",
        description="Connection status changed",
        payload_schema={"status": "str", "error": "str?"},
        example_payload={"status": "connected"},
    ),
    "error": EventTypeDefinition(
        name="error",
        description="An error occurred",
        payload_schema={"error": "str", "code": "str?"},
        example_payload={"error": "Rate limit exceeded", "code": "429"},
    ),
}
