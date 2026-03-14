"""
Workspace Summarizer
====================
LLM-powered file summarization for L2 context.

Generates a 2-3 sentence summary per file and stores it in the DB.
Uses a configurable prompt that can be edited via the API/UI.
"""

import os
from typing import Optional

# ─────────────────────────────────────────────────────────────
# Configurable summarizer prompt
# ─────────────────────────────────────────────────────────────

_DEFAULT_PROMPT = (
    "Summarize this document in 2-3 sentences. "
    "Focus on what it contains and its purpose. "
    "Be concise and factual."
)

_SETTINGS_KEY = "workspace_summary_prompt"


def get_summary_prompt() -> str:
    """Get the current summarizer prompt (from settings DB or default)."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT value FROM settings WHERE key = ?", (_SETTINGS_KEY,)
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return _DEFAULT_PROMPT


def set_summary_prompt(prompt: str) -> bool:
    """Update the summarizer prompt in settings."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                """INSERT INTO settings (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (_SETTINGS_KEY, prompt.strip()),
            )
            conn.commit()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Summarization
# ─────────────────────────────────────────────────────────────

def summarize_text(text: str, prompt: Optional[str] = None) -> Optional[str]:
    """
    Call Ollama to summarize a text block.
    
    Returns the summary string or None on failure.
    """
    if not text or not text.strip():
        return None

    prompt = prompt or get_summary_prompt()
    model = os.environ.get(
        "AIOS_SUMMARY_MODEL",
        os.environ.get("OLLAMA_MODEL", os.environ.get("AIOS_MODEL", "kimi-k2:1t-cloud")),
    )
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    # Truncate to first 4KB to keep it cheap
    truncated = text[:4096]

    try:
        import ollama

        client = ollama.Client(host=host)
        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": truncated},
            ],
            options={"temperature": 0.3, "num_predict": 200},
        )
        content = resp.get("message", {}).get("content", "").strip()
        return content if content else None
    except Exception as e:
        print(f"[Summarizer] Failed: {e}")
        return None


def summarize_file(path: str, prompt: Optional[str] = None) -> Optional[str]:
    """
    Summarize a workspace file and store the result.
    
    Reads the file content from the DB, calls the LLM, and stores the
    generated summary back in workspace_files.summary.
    
    Returns the summary string or None.
    """
    from workspace.schema import get_file, update_file_summary

    file_data = get_file(path)
    if not file_data or file_data.get("is_folder"):
        return None

    content = file_data.get("content")
    if not content:
        return None

    summary = summarize_text(content, prompt)
    if summary:
        update_file_summary(path, summary)
    return summary


# ─────────────────────────────────────────────────────────────
# Conversation Summarization
# ─────────────────────────────────────────────────────────────

_DEFAULT_CONVO_PROMPT = (
    "Summarize this conversation in 2-3 sentences. "
    "Focus on the main topics discussed, key decisions made, "
    "and any action items. Be concise and factual."
)

_CONVO_SETTINGS_KEY = "convo_summary_prompt"


def get_convo_summary_prompt() -> str:
    """Get the current conversation summarizer prompt."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT value FROM settings WHERE key = ?", (_CONVO_SETTINGS_KEY,)
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
    except Exception:
        pass
    return _DEFAULT_CONVO_PROMPT


def set_convo_summary_prompt(prompt: str) -> bool:
    """Update the conversation summarizer prompt."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                """INSERT INTO settings (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (_CONVO_SETTINGS_KEY, prompt.strip()),
            )
            conn.commit()
        return True
    except Exception:
        return False


def summarize_conversation(session_id: str, prompt: Optional[str] = None) -> Optional[str]:
    """
    Summarize a conversation and store the result.

    Reads turns from the DB, formats them into a transcript,
    calls the LLM, and stores via chat.schema.update_summary().

    Returns the summary string or None.
    """
    from chat.schema import get_conversation, update_summary

    convo = get_conversation(session_id)
    if not convo:
        return None

    turns = convo.get("turns", [])
    if not turns:
        return None

    # Build a transcript (truncated to fit context window)
    lines = []
    for t in turns:
        if t.get("user"):
            lines.append(f"User: {t['user'][:300]}")
        if t.get("assistant"):
            lines.append(f"Assistant: {t['assistant'][:300]}")

    transcript = "\n".join(lines)

    prompt = prompt or get_convo_summary_prompt()
    summary = summarize_text(transcript, prompt)
    if summary:
        update_summary(session_id, summary)
    return summary


def batch_summarize_conversations(limit: int = 10) -> int:
    """
    Summarize unsummarized conversations with enough turns.

    Called by the consolidation loop. Only processes conversations
    with >= 2 turns and no existing summary.

    Returns number of conversations summarized.
    """
    from chat.schema import get_unindexed_high_weight_convos

    convos = get_unindexed_high_weight_convos(min_weight=0.0, limit=limit)
    count = 0
    for c in convos:
        sid = c.get("session_id", "")
        turns = c.get("turn_count", 0)
        summary = c.get("summary")
        if turns >= 2 and not summary:
            result = summarize_conversation(sid)
            if result:
                count += 1
    return count

    # Decode
    try:
        text = content.decode("utf-8") if isinstance(content, bytes) else str(content)
    except Exception:
        return None

    mime = file_data.get("mime_type", "")
    if not (
        mime.startswith("text/")
        or mime in ("application/json", "application/javascript", "application/xml")
    ):
        return None

    summary = summarize_text(text, prompt)
    if summary:
        update_file_summary(path, summary)
    return summary
