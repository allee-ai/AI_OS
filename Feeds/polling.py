"""
Feed Polling Loop
=================
Periodically checks enabled feed adapters for new messages/events.

Uses the BackgroundLoop infrastructure from subconscious for error recovery,
backoff, and graceful shutdown.

Flow:
  1. For each enabled feed, call the adapter's pull method
  2. Deduplicate against previously-seen event IDs
  3. Emit events via the event system (which triggers logging + reflex + bridge)
"""

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional, List, Any

from .events import emit_event, EventPriority


# ---------------------------------------------------------------------------
# Persistent seen-ID store (survives restarts)
# ---------------------------------------------------------------------------

_SEEN_IDS_PATH = Path(__file__).resolve().parent.parent / "data" / "db" / ".feed_seen_ids.json"
_seen_ids: Dict[str, Set[str]] = {}
_seen_lock = threading.Lock()
_MAX_SEEN_PER_FEED = 500  # Rolling window


def _load_seen_ids() -> None:
    global _seen_ids
    if _SEEN_IDS_PATH.exists():
        try:
            raw = json.loads(_SEEN_IDS_PATH.read_text())
            _seen_ids = {k: set(v) for k, v in raw.items()}
        except Exception:
            _seen_ids = {}


def _save_seen_ids() -> None:
    try:
        _SEEN_IDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        serialisable = {k: list(v)[-_MAX_SEEN_PER_FEED:] for k, v in _seen_ids.items()}
        _SEEN_IDS_PATH.write_text(json.dumps(serialisable))
    except Exception as e:
        print(f"[POLLING] Failed to persist seen IDs: {e}")


def _is_new(feed_name: str, event_id: str) -> bool:
    """Return True if this event_id hasn't been seen for this feed."""
    with _seen_lock:
        if feed_name not in _seen_ids:
            _seen_ids[feed_name] = set()
        if event_id in _seen_ids[feed_name]:
            return False
        _seen_ids[feed_name].add(event_id)
        # Trim oldest if over limit
        if len(_seen_ids[feed_name]) > _MAX_SEEN_PER_FEED:
            _seen_ids[feed_name] = set(list(_seen_ids[feed_name])[-_MAX_SEEN_PER_FEED:])
        return True


# ---------------------------------------------------------------------------
# Per-adapter poll functions
# ---------------------------------------------------------------------------

async def _poll_email() -> List[Dict[str, Any]]:
    """Poll connected email providers for new messages."""
    from .sources.email import get_connected_providers, get_adapter

    events_emitted = []
    for provider in get_connected_providers():
        try:
            adapter = get_adapter(provider)
            messages = await adapter.list_messages(max_results=10, query="is:unread")
            for msg in messages:
                msg_id = msg.get("id", "")
                if not msg_id or not _is_new("email", msg_id):
                    continue
                event = emit_event(
                    feed_name="email",
                    event_type="email_received",
                    payload={
                        "provider": provider,
                        "message_id": msg_id,
                        "thread_id": msg.get("threadId"),
                        **{k: v for k, v in msg.items() if k not in ("id", "threadId")},
                    },
                    priority=EventPriority.NORMAL,
                    event_id=msg_id,
                )
                events_emitted.append(event.to_dict())
        except Exception as e:
            print(f"[POLLING] Email/{provider} error: {e}")
    return events_emitted


async def _poll_github() -> List[Dict[str, Any]]:
    """Poll GitHub for new notifications."""
    try:
        from .sources.github import get_adapter
        adapter = get_adapter()
        notifications = await adapter.list_notifications()
        events_emitted = []
        for n in notifications:
            nid = str(n.get("id", ""))
            if not nid or not _is_new("github", nid):
                continue
            reason = n.get("reason", "unknown")
            subject = n.get("subject", {})
            event_type_map = {
                "mention": "mention",
                "review_requested": "review_requested",
                "assign": "issue_opened",
                "subscribed": "push_received",
            }
            event_type = event_type_map.get(reason, "mention")
            event = emit_event(
                feed_name="github",
                event_type=event_type,
                payload={
                    "notification_id": nid,
                    "reason": reason,
                    "title": subject.get("title", ""),
                    "type": subject.get("type", ""),
                    "url": subject.get("url", ""),
                    "repository": n.get("repository", {}).get("full_name", ""),
                },
                priority=EventPriority.NORMAL,
                event_id=nid,
            )
            events_emitted.append(event.to_dict())
        return events_emitted
    except Exception as e:
        print(f"[POLLING] GitHub error: {e}")
        return []


# ---------------------------------------------------------------------------
# Discord polling
# ---------------------------------------------------------------------------

async def _poll_discord() -> List[Dict[str, Any]]:
    """Poll monitored Discord channels for new messages."""
    try:
        from .sources.discord import get_adapter
        adapter = get_adapter()
        if not adapter.token:
            return []

        # Get monitored channel IDs from env (comma-separated)
        import os
        channel_ids = [c.strip() for c in os.getenv("AIOS_DISCORD_CHANNELS", "").split(",") if c.strip()]
        if not channel_ids:
            return []

        events_emitted = []
        for channel_id in channel_ids:
            try:
                messages = await adapter.get_messages(channel_id, limit=10)
                for msg in messages:
                    msg_id = str(msg.get("id", ""))
                    if not msg_id or not _is_new("discord", msg_id):
                        continue
                    author = msg.get("author", {})
                    # Skip bot's own messages
                    if author.get("bot", False):
                        continue
                    content = msg.get("content", "")
                    event_type = "mention_received" if adapter.token and f"<@" in content else "message_received"
                    event = emit_event(
                        feed_name="discord",
                        event_type=event_type,
                        payload={
                            "message_id": msg_id,
                            "channel_id": channel_id,
                            "guild_id": msg.get("guild_id", ""),
                            "author_id": str(author.get("id", "")),
                            "author_name": author.get("username", "unknown"),
                            "content": content,
                            "timestamp": msg.get("timestamp", ""),
                        },
                        priority=EventPriority.NORMAL,
                        event_id=msg_id,
                    )
                    events_emitted.append(event.to_dict())
            except Exception as e:
                print(f"[POLLING] Discord/{channel_id} error: {e}")
        return events_emitted
    except Exception as e:
        print(f"[POLLING] Discord error: {e}")
        return []


# ---------------------------------------------------------------------------
# Calendar polling
# ---------------------------------------------------------------------------

async def _poll_calendar() -> List[Dict[str, Any]]:
    """Poll iCal calendars for upcoming events."""
    try:
        from .sources.calendar import poll_calendars
        count = poll_calendars()
        # poll_calendars() emits events directly via emit_event;
        # return empty list since events are already emitted
        return [{}] * count if count else []
    except Exception as e:
        print(f"[POLLING] Calendar error: {e}")
        return []


# ---------------------------------------------------------------------------
# Adapter registry  — maps feed_name → async poll function
# ---------------------------------------------------------------------------

_POLL_FUNCTIONS: Dict[str, Any] = {
    "email": _poll_email,
    "github": _poll_github,
    "discord": _poll_discord,
    "calendar": _poll_calendar,
}


# ---------------------------------------------------------------------------
# Background loop using subconscious infrastructure
# ---------------------------------------------------------------------------

_loop_instance = None


def _poll_task() -> None:
    """Synchronous wrapper called by BackgroundLoop on each tick.

    Runs all enabled adapters' poll functions inside an async context.
    """
    import asyncio

    enabled = _get_enabled_feeds()
    if not enabled:
        return

    async def _run_all():
        total = 0
        for feed_name in enabled:
            fn = _POLL_FUNCTIONS.get(feed_name)
            if fn:
                events = await fn()
                total += len(events)
        if total > 0:
            _save_seen_ids()
            print(f"[POLLING] {total} new event(s) emitted")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_run_all())
        else:
            loop.run_until_complete(_run_all())
    except RuntimeError:
        asyncio.run(_run_all())


def _get_enabled_feeds() -> List[str]:
    """Return feed names that are toggled-on in .enabled.json AND have poll functions."""
    try:
        state_file = Path(__file__).resolve().parent / "sources" / ".enabled.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            return [name for name, on in state.items() if on and name in _POLL_FUNCTIONS]
    except Exception:
        pass
    return []


def start_polling(interval_seconds: int = 300) -> None:
    """Start the background polling loop (called once from server.py)."""
    global _loop_instance
    if _loop_instance is not None:
        return  # Already running

    _load_seen_ids()

    try:
        from agent.subconscious.loops import BackgroundLoop, LoopConfig

        config = LoopConfig(
            interval_seconds=interval_seconds,
            name="feed_polling",
            enabled=True,
            max_errors=5,
            error_backoff=2.0,
        )
        _loop_instance = BackgroundLoop(config, _poll_task)
        _loop_instance.start()
        print(f"📡 Feed polling started (every {interval_seconds}s)")
    except ImportError:
        print("[POLLING] BackgroundLoop not available — polling disabled")


def stop_polling() -> None:
    """Stop the background polling loop."""
    global _loop_instance
    if _loop_instance:
        _loop_instance.stop()
        _save_seen_ids()
        _loop_instance = None


def get_polling_status() -> Dict[str, Any]:
    """Return current polling loop status."""
    if _loop_instance is None:
        return {"status": "stopped", "enabled_feeds": _get_enabled_feeds()}
    return {
        **_loop_instance.stats,
        "enabled_feeds": _get_enabled_feeds(),
    }
