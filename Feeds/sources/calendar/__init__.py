"""
Calendar Feed Source
====================

Polls iCal (.ics) URLs for upcoming events and emits feed events.
Supports any calendar that exposes an iCal URL (Google Calendar,
Apple Calendar, Outlook, Fastmail, etc).

Event types:
    event_upcoming  — fires when an event is within the lookahead window
    event_starting  — fires when an event starts within the next 5 minutes
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from Feeds.events import EventTypeDefinition, register_event_types, emit_event, EventPriority

# ============================================================================
# Event Types
# ============================================================================

CALENDAR_EVENT_TYPES = [
    EventTypeDefinition(
        name="event_upcoming",
        description="A calendar event is coming up within the lookahead window",
        payload_schema={
            "calendar": "str",
            "uid": "str",
            "summary": "str",
            "start": "str",
            "end": "str",
            "location": "str",
            "description": "str",
            "minutes_until": "int",
        },
        example_payload={
            "calendar": "work",
            "uid": "abc123@google.com",
            "summary": "Team standup",
            "start": "2026-02-01T10:00:00Z",
            "end": "2026-02-01T10:30:00Z",
            "location": "Zoom",
            "description": "Daily standup meeting",
            "minutes_until": 15,
        },
    ),
    EventTypeDefinition(
        name="event_starting",
        description="A calendar event is starting in the next 5 minutes",
        payload_schema={
            "calendar": "str",
            "uid": "str",
            "summary": "str",
            "start": "str",
            "location": "str",
        },
        example_payload={
            "calendar": "work",
            "uid": "abc123@google.com",
            "summary": "Team standup",
            "start": "2026-02-01T10:00:00Z",
            "location": "Zoom",
        },
    ),
]

# Register on import
register_event_types("calendar", CALENDAR_EVENT_TYPES)


# ============================================================================
# Calendar DB helpers
# ============================================================================

def _ensure_calendar_table() -> None:
    """Create calendar_sources table if needed."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calendar_sources (
                    name TEXT PRIMARY KEY,
                    ical_url TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    lookahead_minutes INTEGER NOT NULL DEFAULT 30,
                    poll_interval_seconds INTEGER NOT NULL DEFAULT 300,
                    last_polled TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calendar_notified (
                    uid TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    notified_at TEXT NOT NULL DEFAULT (datetime('now')),
                    PRIMARY KEY (uid, event_type)
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[Calendar] Failed to create tables: {e}")


def add_calendar(name: str, ical_url: str, lookahead_minutes: int = 30,
                 poll_interval: int = 300) -> Dict[str, Any]:
    """Register a calendar source by iCal URL."""
    _ensure_calendar_table()
    from data.db import get_connection
    from contextlib import closing
    with closing(get_connection()) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO calendar_sources "
            "(name, ical_url, lookahead_minutes, poll_interval_seconds) VALUES (?, ?, ?, ?)",
            (name, ical_url, lookahead_minutes, poll_interval)
        )
        conn.commit()
    return {"name": name, "ical_url": ical_url, "lookahead_minutes": lookahead_minutes}


def get_calendars() -> List[Dict[str, Any]]:
    """Get all registered calendar sources."""
    _ensure_calendar_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name, ical_url, enabled, lookahead_minutes, "
                        "poll_interval_seconds, last_polled FROM calendar_sources")
            return [
                {"name": r[0], "ical_url": r[1], "enabled": bool(r[2]),
                 "lookahead_minutes": r[3], "poll_interval": r[4], "last_polled": r[5]}
                for r in cur.fetchall()
            ]
    except Exception:
        return []


def remove_calendar(name: str) -> bool:
    """Remove a calendar source."""
    _ensure_calendar_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM calendar_sources WHERE name = ?", (name,))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False


def _was_notified(uid: str, event_type: str) -> bool:
    """Check if we already emitted this event for this uid."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM calendar_notified WHERE uid = ? AND event_type = ?",
                (uid, event_type)
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def _mark_notified(uid: str, event_type: str) -> None:
    """Record that we emitted this event."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO calendar_notified (uid, event_type) VALUES (?, ?)",
                (uid, event_type)
            )
            conn.commit()
    except Exception:
        pass


# ============================================================================
# iCal parsing
# ============================================================================

def _parse_ical(text: str) -> List[Dict[str, Any]]:
    """Parse iCal text into a list of event dicts. Lightweight — no deps."""
    events = []
    current = None

    for line in text.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, _, value = line.partition(":")
            # Handle properties with params like DTSTART;TZID=...
            key = key.split(";")[0]
            mapping = {
                "UID": "uid",
                "SUMMARY": "summary",
                "DTSTART": "start",
                "DTEND": "end",
                "LOCATION": "location",
                "DESCRIPTION": "description",
            }
            field = mapping.get(key)
            if field:
                current[field] = value

    return events


def _parse_dt(value: str) -> Optional[datetime]:
    """Parse iCal datetime value into timezone-aware datetime."""
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    for fmt in ("%Y%m%dT%H%M%S%z", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


# ============================================================================
# Polling
# ============================================================================

def poll_calendars() -> int:
    """Poll all enabled calendars and emit events. Returns events emitted count."""
    import urllib.request
    import ssl

    calendars = get_calendars()
    total_emitted = 0
    now = datetime.now(timezone.utc)

    for cal in calendars:
        if not cal["enabled"]:
            continue
        try:
            from agent.core.url_validation import validate_url
            validate_url(cal["ical_url"])

            ctx = ssl.create_default_context()
            req = urllib.request.Request(cal["ical_url"], headers={"User-Agent": "AIOS-Calendar/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"[Calendar] Failed to fetch {cal['name']}: {e}")
            continue

        events = _parse_ical(text)
        lookahead = timedelta(minutes=cal["lookahead_minutes"])

        for ev in events:
            start = _parse_dt(ev.get("start", ""))
            if not start:
                continue
            uid = ev.get("uid", "")
            delta = start - now

            # Skip past events
            if delta.total_seconds() < -300:  # More than 5 min ago
                continue

            # event_starting: within 5 minutes
            if 0 <= delta.total_seconds() <= 300:
                if not _was_notified(uid, "event_starting"):
                    emit_event(
                        feed_name="calendar",
                        event_type="event_starting",
                        payload={
                            "calendar": cal["name"],
                            "uid": uid,
                            "summary": ev.get("summary", ""),
                            "start": ev.get("start", ""),
                            "location": ev.get("location", ""),
                        },
                        priority=EventPriority.HIGH,
                    )
                    _mark_notified(uid, "event_starting")
                    total_emitted += 1

            # event_upcoming: within lookahead window
            elif timedelta(0) < delta <= lookahead:
                if not _was_notified(uid, "event_upcoming"):
                    end_dt = _parse_dt(ev.get("end", ""))
                    emit_event(
                        feed_name="calendar",
                        event_type="event_upcoming",
                        payload={
                            "calendar": cal["name"],
                            "uid": uid,
                            "summary": ev.get("summary", ""),
                            "start": ev.get("start", ""),
                            "end": ev.get("end", ""),
                            "location": ev.get("location", ""),
                            "description": ev.get("description", "")[:200],
                            "minutes_until": int(delta.total_seconds() / 60),
                        },
                        priority=EventPriority.NORMAL,
                    )
                    _mark_notified(uid, "event_upcoming")
                    total_emitted += 1

        # Update last_polled
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute(
                    "UPDATE calendar_sources SET last_polled = ? WHERE name = ?",
                    (now.isoformat(), cal["name"])
                )
                conn.commit()
        except Exception:
            pass

    # Prune old notifications (> 24h)
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                "DELETE FROM calendar_notified WHERE notified_at < datetime('now', '-1 day')"
            )
            conn.commit()
    except Exception:
        pass

    return total_emitted
