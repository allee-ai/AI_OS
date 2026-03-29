"""
Chat Training Data Export
=========================
Exports conversation turns from all channels (react, cli, import)
plus self-knowledge (API endpoints, CLI commands, schema) into JSONL.

Each example: {messages: [system, user, assistant]}
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import closing


FINETUNE_DIR = Path(__file__).resolve().parents[1] / "finetune"

# ── Self-knowledge constants ────────────────────────────
API_ENDPOINTS = [
    ("GET",    "/api/chat/history",                      "Get recent chat history"),
    ("POST",   "/api/chat/message",                      "Send message and get response"),
    ("GET",    "/api/chat/agent-status",                  "Get agent availability"),
    ("POST",   "/api/chat/clear",                         "Clear chat history"),
    ("POST",   "/api/chat/start-session",                 "Start a new chat session"),
    ("POST",   "/api/chat/set-session/{session_id}",      "Set current session (load existing)"),
    ("GET",    "/api/conversations",                      "List all saved conversations (newest first, search)"),
    ("GET",    "/api/conversations/{session_id}",         "Get full conversation by session ID"),
    ("POST",   "/api/conversations/{session_id}/rename",  "Manually rename a conversation"),
    ("DELETE", "/api/conversations/{session_id}",         "Delete a conversation"),
    ("DELETE", "/api/conversations/source/{source}",      "Delete all conversations from a source"),
    ("POST",   "/api/conversations/{session_id}/archive", "Archive a conversation"),
    ("POST",   "/api/conversations/{session_id}/unarchive","Unarchive a conversation"),
    ("POST",   "/api/conversations/new",                  "Create a new conversation session"),
    ("GET",    "/api/conversations/{session_id}/export",  "Export single conversation as JSON"),
    ("GET",    "/api/conversations/export/all",           "Export all conversations as JSON"),
    ("POST",   "/api/ratings/rate",                       "Rate a message (up/down, save as training example)"),
    ("GET",    "/api/ratings/stats",                      "Get rated-message statistics"),
]

CLI_COMMANDS = [
    ("/convos",                  "List recent conversations"),
    ("/convos <id>",             "Show conversation turns"),
    ("/convos search <query>",   "Search conversations"),
    ("/convos new [name]",       "Create new conversation"),
    ("/convos delete <id>",      "Delete conversation"),
]

SCHEMA_TABLES = [
    {
        "name": "convos",
        "columns": "id, session_id, channel, name, started, last_updated, archived, weight, turn_count, indexed, state_snapshot_json, summary, source",
        "description": "Conversation metadata and state",
    },
    {
        "name": "convo_turns",
        "columns": "id, convo_id (FK), turn_index, timestamp, user_message, assistant_message, feed_type, context_level, metadata_json",
        "description": "Individual turns within conversations",
    },
]


def _build_training_state(query: str) -> str:
    """
    Build a real STATE block for a training pair.

    Uses the orchestrator to produce the same STATE the model would see
    at inference time, so training teaches STATE-following behavior.
    Falls back to a lightweight static STATE if orchestrator fails.
    """
    try:
        from agent.subconscious.orchestrator import build_state
        return build_state(query)
    except Exception:
        # Fallback: lightweight but realistic STATE structure
        return (
            "== STATE ==\n"
            "[self] My internal structure\n"
            "  Threads: identity, philosophy, log, reflex, form, linking_core\n"
            "  Modules: chat, workspace\n"
            "[identity] Who I am and who you are\n"
            "  I am a personal AI companion. I run locally for privacy.\n"
            "== END STATE =="
        )


def export_training_data(
    output_path: Optional[Path] = None,
    limit: int = 2000,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export conversation data + self-knowledge to JSONL.
    Sections: data, api, cli, schema (default: all).
    """
    from data.db import get_connection
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples

    if sections is None:
        sections = ["data", "api", "cli", "schema"]

    if output_path is None:
        output_path = FINETUNE_DIR / "chat_train.jsonl"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    examples = []

    # ── Data section: conversation turns ──
    # Only export turns from the real agent (source='aios'), not imported
    # ChatGPT/Copilot conversations which teach the wrong voice.
    if "data" in sections:
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT ct.user_message, ct.assistant_message, c.channel, c.session_id
                FROM convo_turns ct
                JOIN convos c ON ct.convo_id = c.id
                WHERE ct.user_message IS NOT NULL
                  AND ct.assistant_message IS NOT NULL
                  AND LENGTH(ct.assistant_message) >= 20
                  AND c.source = 'aios'
                ORDER BY ct.timestamp DESC
                LIMIT ?
            """, (limit,))

            for user_msg, assistant_msg, channel, session_id in cur.fetchall():
                # Build a real STATE block for this turn so the model
                # learns to ground its answers in STATE context.
                state_block = _build_training_state(user_msg)
                examples.append({
                    "messages": [
                        {"role": "system", "content": state_block},
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": assistant_msg},
                    ],
                    "metadata": {"source": "chat", "section": "data", "channel": channel or "react", "session_id": session_id},
                })

    # ── Self-knowledge sections ──
    if "api" in sections:
        examples.extend(build_api_examples("chat", API_ENDPOINTS))
    if "cli" in sections:
        examples.extend(build_cli_examples("chat", CLI_COMMANDS))
    if "schema" in sections:
        examples.extend(build_schema_examples("chat", SCHEMA_TABLES))

    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def get_export_stats() -> Dict[str, Any]:
    """Counts of exportable conversation turns, broken down by channel."""
    from data.db import get_connection

    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM convo_turns
            WHERE user_message IS NOT NULL
              AND assistant_message IS NOT NULL
              AND LENGTH(assistant_message) >= 20
        """)
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT c.channel, COUNT(*)
            FROM convo_turns ct
            JOIN convos c ON ct.convo_id = c.id
            WHERE ct.user_message IS NOT NULL
              AND ct.assistant_message IS NOT NULL
              AND LENGTH(ct.assistant_message) >= 20
            GROUP BY c.channel
        """)
        channels = {row[0] or "react": row[1] for row in cur.fetchall()}

    return {"examples": total, "channels": channels}


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import count_api_examples, count_cli_examples, count_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Conversation turns (all channels)", "examples": stats.get("examples", 0)},
        "api":    {"description": "Chat & conversation API endpoints", "examples": count_api_examples(API_ENDPOINTS)},
        "cli":    {"description": "CLI commands (/convos)", "examples": count_cli_examples(CLI_COMMANDS)},
        "schema": {"description": "convos + convo_turns tables", "examples": count_schema_examples(SCHEMA_TABLES)},
    }
