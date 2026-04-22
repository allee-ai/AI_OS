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
    Summarize a text block using the configured LLM provider.
    
    Returns the summary string or None on failure.
    """
    if not text or not text.strip():
        return None

    prompt = prompt or get_summary_prompt()
    # Role-specific override (AIOS_SUMMARY_PROVIDER/MODEL/ENDPOINT) with
    # fallback to global AIOS_MODEL_* and the legacy AIOS_SUMMARY_MODEL.
    from agent.services.role_model import resolve_role
    cfg = resolve_role("SUMMARY")
    provider = cfg.provider
    model = cfg.model or os.environ.get(
        "AIOS_SUMMARY_MODEL",
        os.environ.get("AIOS_MODEL_NAME", "qwen2.5:7b"),
    )

    # Truncate to first 6KB to keep it reasonable
    truncated = text[:6144]
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": truncated},
    ]

    try:
        if provider == "openai":
            import urllib.request, json
            api_key = cfg.api_key or os.environ.get("OPENAI_API_KEY", "")
            base_url = (cfg.endpoint or "").rstrip("/") or "https://api.openai.com/v1"
            payload = {"model": model, "messages": messages, "max_tokens": 500, "temperature": 0.3}
            req = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                content = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        elif provider == "http":
            import urllib.request, json
            endpoint = cfg.endpoint or os.environ.get("AIOS_MODEL_ENDPOINT", "")
            req = urllib.request.Request(
                endpoint,
                data=json.dumps({"messages": messages}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                content = (body.get("message") or body.get("content") or "").strip()

        else:
            # ollama (default)
            import ollama
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            client = ollama.Client(host=host)
            resp = client.chat(
                model=model,
                messages=messages,
                options={"temperature": 0.3, "num_predict": 500},
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

    For short conversations (<=4K chars), summarizes directly.
    For long conversations, uses chunked hierarchical summarization:
      1. Split transcript into ~3K-char chunks
      2. Summarize each chunk independently
      3. Combine chunk summaries and produce a final summary

    Target output: ~500 tokens (3-5 dense sentences).
    Returns the summary string or None.
    """
    from chat.schema import get_conversation, update_summary

    convo = get_conversation(session_id)
    if not convo:
        return None

    turns = convo.get("turns", [])
    if not turns:
        return None

    # Build full transcript — keep more per turn for better summaries
    lines = []
    for t in turns:
        if t.get("user"):
            lines.append(f"User: {t['user'][:500]}")
        if t.get("assistant"):
            lines.append(f"Assistant: {t['assistant'][:500]}")

    transcript = "\n".join(lines)
    prompt = prompt or get_convo_summary_prompt()

    CHUNK_SIZE = 3000  # chars per chunk (~750 tokens)

    if len(transcript) <= CHUNK_SIZE + 500:
        # Short conversation — single pass
        summary = summarize_text(transcript, prompt)
    else:
        # Chunked hierarchical summarization
        chunks = _split_into_chunks(transcript, CHUNK_SIZE)

        chunk_prompt = (
            "Summarize this section of a conversation in 2-3 sentences. "
            "Capture the key topics, decisions, and context. Be factual and concise."
        )
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            cs = summarize_text(chunk, chunk_prompt)
            if cs:
                chunk_summaries.append(f"[Part {i+1}/{len(chunks)}] {cs}")

        if not chunk_summaries:
            # All chunks failed — fall back to truncated single pass
            summary = summarize_text(transcript[:CHUNK_SIZE], prompt)
        elif len(chunk_summaries) == 1:
            summary = chunk_summaries[0]
        else:
            # Final pass: combine chunk summaries into one cohesive summary
            combined = "\n".join(chunk_summaries)
            final_prompt = (
                f"Below are summaries of {len(chunk_summaries)} sections of a single conversation. "
                "Combine them into one cohesive 3-5 sentence summary covering the main topics, "
                "key decisions, and outcomes. Do not mention 'parts' or 'sections'."
            )
            summary = summarize_text(combined, final_prompt)
            if not summary:
                # Fall back to joining chunk summaries
                summary = " ".join(cs.split("] ", 1)[-1] for cs in chunk_summaries)

    if summary:
        update_summary(session_id, summary)
    return summary


def _split_into_chunks(text: str, chunk_size: int) -> list:
    """Split text into chunks, preferring to break at newlines."""
    chunks = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        # Find a newline near the chunk boundary to break cleanly
        cut = text.rfind("\n", chunk_size // 2, chunk_size)
        if cut == -1:
            cut = chunk_size
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


def batch_summarize_conversations(limit: int = 10) -> int:
    """
    Summarize unsummarized conversations with enough turns.

    Called by the consolidation loop. Only processes conversations
    with >= 2 turns and no existing summary.

    Returns number of conversations summarized.
    """
    from chat.schema import get_unindexed_high_weight_convos

    from chat.schema import mark_conversation_indexed

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
                mark_conversation_indexed(sid)
        elif summary:
            # Already has a summary but wasn't marked indexed
            mark_conversation_indexed(sid)
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
