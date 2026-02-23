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
        os.environ.get("OLLAMA_MODEL", os.environ.get("AIOS_MODEL", "llama3.2")),
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
