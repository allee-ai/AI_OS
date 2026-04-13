"""
Feed → Agent → Response Bridge
================================
Closes the loop between external events and the agent's reasoning.

When a feed event arrives that warrants a response, this module:
1. Builds a ResponseTemplate with deterministic routing fields
2. Calls the agent to fill the probabilistic slots (subject, body)
3. Dispatches the response through the correct adapter

The bridge registers as an event handler so it fires automatically
whenever emit_event() is called (from polling, webhooks, or tests).

Configuration:
- AIOS_FEED_BRIDGE=1          Enable the bridge (default: off)
- AIOS_FEED_DRAFT_ONLY=1      Generate drafts but don't send (default: on)
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List

from .events import FeedEvent, register_handler
from .router import ResponseTemplate


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _is_enabled() -> bool:
    return os.getenv("AIOS_FEED_BRIDGE", "0") == "1"


def _is_draft_only() -> bool:
    return os.getenv("AIOS_FEED_DRAFT_ONLY", "1") == "1"


# ---------------------------------------------------------------------------
# Response history  (in-memory, last N for UI / debugging)
# ---------------------------------------------------------------------------

_response_log: List[Dict[str, Any]] = []
_MAX_RESPONSE_LOG = 100


def get_response_log(limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent bridge responses, newest first."""
    return list(reversed(_response_log[-limit:]))


# ---------------------------------------------------------------------------
# Event → should we respond?
# ---------------------------------------------------------------------------

# Events these handlers will try to generate a response for
_RESPONDABLE_EVENTS: Dict[str, List[str]] = {
    "email": ["email_received"],
    "github": ["mention", "review_requested", "issue_opened"],
    "discord": ["dm_received", "mention_received"],
}


def _should_respond(event: FeedEvent) -> bool:
    """Decide whether the agent should draft a response for this event."""
    if not _is_enabled():
        return False
    feed_events = _RESPONDABLE_EVENTS.get(event.feed_name, [])
    return event.event_type in feed_events


# ---------------------------------------------------------------------------
# Build the deterministic part of the response
# ---------------------------------------------------------------------------

def _build_template(event: FeedEvent) -> ResponseTemplate:
    """Create a ResponseTemplate with routing fields filled from the event."""
    payload = event.payload

    if event.feed_name == "email":
        return ResponseTemplate(
            platform="email",
            to=payload.get("from", payload.get("sender", "")),
            to_name=payload.get("from_name", payload.get("sender_name", "")),
            thread_id=payload.get("thread_id", ""),
            in_reply_to=payload.get("message_id", ""),
            conversation=[],
        )

    if event.feed_name == "github":
        return ResponseTemplate(
            platform="github",
            to=payload.get("repository", ""),
            to_name=payload.get("title", ""),
            thread_id=payload.get("url", ""),
            in_reply_to=payload.get("notification_id", ""),
            conversation=[],
        )

    if event.feed_name == "discord":
        return ResponseTemplate(
            platform="discord",
            to=payload.get("channel_id", ""),
            to_name=payload.get("sender_name", ""),
            thread_id=payload.get("channel_id", ""),
            in_reply_to=payload.get("message_id", ""),
            conversation=[],
        )

    # Generic fallback
    return ResponseTemplate(
        platform=event.feed_name,
        to=payload.get("sender", ""),
        to_name="",
        thread_id="",
    )


# ---------------------------------------------------------------------------
# Call the agent to fill probabilistic slots
# ---------------------------------------------------------------------------

def _generate_response(event: FeedEvent, template: ResponseTemplate) -> ResponseTemplate:
    """Use the agent to generate subject + body for the response.

    Constructs a prompt with the event context and asks the agent
    to produce a reply.  Falls back to a simple echo if the agent
    is unavailable.
    """
    prompt = _build_agent_prompt(event, template)

    try:
        from agent.agent import get_agent
        agent = get_agent()
        if agent is None:
            raise ImportError("Agent not initialised")

        # Get consciousness context for richer replies
        consciousness = ""
        try:
            from agent.subconscious.orchestrator import get_subconscious
            sub = get_subconscious()
            consciousness = sub.get_state(query=prompt)
        except Exception:
            pass

        raw = agent.generate(
            user_input=prompt,
            feed_type="conversational",
            consciousness_context=consciousness,
        )

        # Parse subject/body from the response
        subject, body = _parse_agent_response(raw, event)
        template.subject = subject
        template.body = body

    except Exception as e:
        print(f"[BRIDGE] Agent generation failed: {e}")
        template.subject = f"Re: {event.payload.get('subject', event.event_type)}"
        template.body = f"(Auto-draft failed: {e})"

    return template


def _build_agent_prompt(event: FeedEvent, template: ResponseTemplate) -> str:
    """Construct the prompt the agent sees when generating a feed response."""
    parts = [
        f"You received a notification from {event.feed_name} ({event.event_type}).",
        "",
    ]

    p = event.payload
    if event.feed_name == "email":
        # JSON-encode untrusted fields to prevent prompt injection
        parts.append(f"From: {json.dumps(str(p.get('from', p.get('sender', 'unknown'))))}")
        if p.get("subject"):
            parts.append(f"Subject: {json.dumps(str(p['subject']))}")
        if p.get("snippet") or p.get("body"):
            parts.append(f"Body: {json.dumps(str(p.get('snippet', p.get('body', '')))[:500])}")
    elif event.feed_name == "github":
        parts.append(f"Repo: {json.dumps(str(p.get('repository', '')))}")
        parts.append(f"Title: {json.dumps(str(p.get('title', '')))}")
        parts.append(f"Reason: {json.dumps(str(p.get('reason', '')))}")
    elif event.feed_name == "discord":
        parts.append(f"From: {json.dumps(str(p.get('sender_name', 'someone')))}")
        parts.append(f"Message: {json.dumps(str(p.get('content', ''))[:500])}")
    else:
        parts.append(f"Payload: {json.dumps(p)[:500]}")

    draft_note = " Write a draft reply." if _is_draft_only() else " Write a reply."
    parts.append("")
    parts.append(
        f"Compose a response on behalf of the user.{draft_note}"
        " Keep it natural and concise.  "
        "Reply with SUBJECT: on the first line, then BODY: on the next line, "
        "followed by the message body."
    )
    return "\n".join(parts)


def _parse_agent_response(raw: str, event: FeedEvent) -> tuple:
    """Extract (subject, body) from the agent's raw text output."""
    subject = f"Re: {event.payload.get('subject', event.event_type)}"
    body = raw.strip()

    lines = raw.strip().splitlines()
    for i, line in enumerate(lines):
        if line.upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
        elif line.upper().startswith("BODY:"):
            body = "\n".join(lines[i + 1:]).strip() if i + 1 < len(lines) else line.split(":", 1)[1].strip()
            break

    return subject, body


# ---------------------------------------------------------------------------
# Dispatch the response through the correct adapter
# ---------------------------------------------------------------------------

async def _dispatch(event: FeedEvent, template: ResponseTemplate) -> Dict[str, Any]:
    """Send (or draft) the response via the appropriate feed adapter."""
    result: Dict[str, Any] = {
        "feed": event.feed_name,
        "event_type": event.event_type,
        "to": template.to,
        "subject": template.subject,
        "body": template.body,
        "draft_only": _is_draft_only(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # AI OS never sends directly — always draft-only.
    # The user reviews and sends from their own email client.
    result["status"] = "drafted"
    return result


def _extract_issue_number(url: str) -> Optional[int]:
    """Try to extract an issue/PR number from a GitHub API URL."""
    import re
    m = re.search(r'/(?:issues|pulls)/(\d+)', url)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# The handler registered with the event system
# ---------------------------------------------------------------------------

async def _handle_event(event: FeedEvent) -> None:
    """Core handler: decide → generate → dispatch → log."""
    if not _should_respond(event):
        return

    template = _build_template(event)
    template = _generate_response(event, template)
    result = await _dispatch(event, template)

    # Append to in-memory log for the UI
    _response_log.append(result)
    if len(_response_log) > _MAX_RESPONSE_LOG:
        _response_log[:] = _response_log[-_MAX_RESPONSE_LOG:]

    # Persist to unified event log
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="bridge_response",
            data=f"[{result['feed']}] {result.get('status', '?')}: {template.subject}",
            metadata=result,
            source="feed.bridge",
        )
    except Exception:
        pass

    status = result.get("status", "unknown")
    print(f"[BRIDGE] {event.feed_name}/{event.event_type} → {status}")


def _sync_handler(event: FeedEvent) -> None:
    """Sync wrapper for the async handler (event system calls sync handlers)."""
    coro = _handle_event(event)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_bridge() -> None:
    """Register the bridge handler with the event system.

    Safe to call multiple times — only registers once.
    """
    if not _is_enabled():
        print("🌉 Feed bridge disabled (set AIOS_FEED_BRIDGE=1 to enable)")
        return

    register_handler(_sync_handler)  # subscribe to ALL events
    mode = "draft-only" if _is_draft_only() else "live-send"
    print(f"🌉 Feed bridge started ({mode})")


def get_bridge_status() -> Dict[str, Any]:
    """Return current bridge configuration and stats."""
    return {
        "enabled": _is_enabled(),
        "draft_only": _is_draft_only(),
        "respondable_events": _RESPONDABLE_EVENTS,
        "responses_logged": len(_response_log),
        "recent": get_response_log(5),
    }
