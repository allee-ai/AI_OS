"""
Feed Intelligence — LLM-powered capabilities across feeds.
=============================================================

Provides summarization, triage, action-item extraction, smart reply
drafting, and priority detection for email threads and other feed
content.  Uses the same LLM provider configured for the rest of AI OS
(``workspace.summarizer.summarize_text`` under the hood).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


# ── prompts ──────────────────────────────────────────────────

_THREAD_SUMMARY_PROMPT = (
    "You are summarizing an email thread for a busy user.  "
    "Write a concise 2-4 sentence summary covering: who is involved, "
    "the main topic, key decisions or questions, and any open action items.  "
    "Use plain language, no markdown."
)

_ACTION_ITEMS_PROMPT = (
    "Extract all actionable tasks from the following email thread.  "
    "Return a JSON array of objects with keys: \"task\" (string), "
    "\"assignee\" (string or null), \"deadline\" (string or null).  "
    "Only output the JSON array, nothing else."
)

_TRIAGE_PROMPT = (
    "You are an email triage assistant.  For each email below, assign:\n"
    "- \"priority\": one of \"urgent\", \"high\", \"normal\", \"low\"\n"
    "- \"category\": one of \"action_required\", \"fyi\", \"scheduling\", "
    "\"newsletter\", \"social\", \"notification\", \"spam\"\n"
    "- \"reason\": one sentence explaining the classification\n\n"
    "Return a JSON array in the same order as the input.  Only output JSON."
)

_SMART_REPLY_PROMPT = (
    "Draft three short, natural reply options for the email below.  "
    "Vary the tone: one positive/accepting, one asking a follow-up question, "
    "one politely declining or deferring.  "
    "Return a JSON array of three strings.  Only output JSON."
)

_DIGEST_PROMPT = (
    "You are creating a daily email digest for a busy professional.  "
    "Given the list of recent emails below, write a short briefing "
    "(3-5 bullet points) covering what's important, any deadlines, "
    "and anything that needs a reply.  Be concise and direct."
)


# ── helpers ──────────────────────────────────────────────────

def _llm(text: str, system_prompt: str, max_chars: int = 6000) -> Optional[str]:
    """Call the configured LLM through the workspace summarizer path."""
    from workspace.summarizer import summarize_text
    return summarize_text(text[:max_chars], prompt=system_prompt)


def _format_thread(messages: List[Dict[str, Any]], max_messages: int = 25) -> str:
    """Turn a list of email dicts into a readable text block.

    Content is JSON-encoded per field so the LLM treats it as data rather
    than instructions (defense-in-depth against prompt injection).
    """
    parts: list[str] = []
    for m in messages[:max_messages]:
        parts.append(
            f"From: {json.dumps(str(m.get('from', '?')))}\n"
            f"Date: {json.dumps(str(m.get('date', '?')))}\n"
            f"Subject: {json.dumps(str(m.get('subject', '')))}\n"
            f"Body: {json.dumps(str(m.get('snippet', m.get('body', '')))[:500])}\n"
        )
    return "\n---\n".join(parts)


def _parse_json(raw: Optional[str], fallback: Any = None) -> Any:
    """Best-effort JSON parse from LLM output."""
    if not raw:
        return fallback
    # Strip markdown fences if the model wrapped its response
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return fallback


# ── public API ───────────────────────────────────────────────

def summarize_thread(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Summarize a list of email messages (a thread / chain)."""
    if not messages:
        return None
    text = _format_thread(messages)
    return _llm(text, _THREAD_SUMMARY_PROMPT)


def extract_action_items(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract action items / tasks from an email thread."""
    if not messages:
        return []
    text = _format_thread(messages)
    raw = _llm(text, _ACTION_ITEMS_PROMPT)
    items = _parse_json(raw, [])
    if not isinstance(items, list):
        return []
    return items


def triage_emails(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Classify a batch of emails by priority and category."""
    if not messages:
        return []
    # Build a compact representation for the LLM
    entries: list[str] = []
    for i, m in enumerate(messages):
        entries.append(
            f"{i + 1}. From: {m.get('from', '?')} | "
            f"Subject: {m.get('subject', '')} | "
            f"Preview: {m.get('snippet', '')[:120]}"
        )
    text = "\n".join(entries)
    raw = _llm(text, _TRIAGE_PROMPT)
    result = _parse_json(raw, [])
    if not isinstance(result, list):
        return []
    # Merge classifications back into minimal dicts
    out: list[dict] = []
    for i, m in enumerate(messages):
        classification = result[i] if i < len(result) else {}
        out.append({
            "id": m.get("id", ""),
            "from": m.get("from", ""),
            "subject": m.get("subject", ""),
            "priority": classification.get("priority", "normal"),
            "category": classification.get("category", "fyi"),
            "reason": classification.get("reason", ""),
        })
    return out


def smart_replies(message: Dict[str, Any]) -> List[str]:
    """Generate 3 short reply suggestions for a single email."""
    text = (
        f"From: {json.dumps(str(message.get('from', '?')))}\n"
        f"Subject: {json.dumps(str(message.get('subject', '')))}\n"
        f"Body: {json.dumps(str(message.get('snippet', message.get('body', '')))[:500])}"
    )
    raw = _llm(text, _SMART_REPLY_PROMPT)
    replies = _parse_json(raw, [])
    if not isinstance(replies, list):
        return []
    return [str(r) for r in replies[:3]]


def daily_digest(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Generate a morning-briefing-style digest of recent emails."""
    if not messages:
        return None
    entries: list[str] = []
    for m in messages[:30]:  # cap at 30 for context window
        entries.append(
            f"• From: {m.get('from', '?')} — "
            f"{m.get('subject', '(no subject)')}: "
            f"{m.get('snippet', '')[:100]}"
        )
    text = "\n".join(entries)
    return _llm(text, _DIGEST_PROMPT, max_chars=8000)
