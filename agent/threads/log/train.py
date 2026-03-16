"""
Log Thread Training Data
========================
Logs confident memory decisions for fine-tuning.

Sections: data (conversation turns), api (endpoint knowledge), cli (command knowledge), schema
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "log_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7

# ─────────────────────────────────────────────────────
# Self-knowledge: API, CLI, Schema
# ─────────────────────────────────────────────────────

API_ENDPOINTS = [
    ("GET",    "/api/log/events",                  "Query events from the unified log"),
    ("POST",   "/api/log/events",                  "Log a new event"),
    ("DELETE", "/api/log/events/{event_id}",       "Delete an event by ID"),
    ("DELETE", "/api/log/events",                  "Clear events by type or before timestamp"),
    ("GET",    "/api/log/events/search",           "Search events by text content"),
    ("GET",    "/api/log/timeline",                "Get user-facing timeline"),
    ("GET",    "/api/log/system",                  "Get full system log for debugging"),
    ("GET",    "/api/log/daemon",                  "Query daemon/infrastructure logs"),
    ("POST",   "/api/log/daemon",                  "Log a daemon event"),
    ("GET",    "/api/log/server",                  "Query HTTP server logs"),
    ("GET",    "/api/log/server/stats",            "Get server performance statistics"),
    ("POST",   "/api/log/sessions",                "Create a new session"),
    ("PUT",    "/api/log/sessions/{session_id}/end", "End a session"),
    ("GET",    "/api/log/stats",                   "Get log statistics"),
    ("GET",    "/api/log/introspect",              "Get log STATE block contribution"),
    ("GET",    "/api/log/health",                  "Get log thread health"),
]

CLI_COMMANDS = [
    ("/log",                     "Show recent user-facing timeline"),
    ("/log events [type]",       "List events, optionally filtered by type"),
    ("/log search <query>",      "Search events by text content"),
    ("/log types",               "List all event types"),
    ("/log stats",               "Show log statistics"),
]

SCHEMA_TABLES = [
    {"name": "unified_events", "columns": "id, timestamp, event_type, source, data, metadata_json, session_id", "description": "all system events in a unified log (user actions, system events, errors)"},
    {"name": "log_system", "columns": "level, source, message, pid", "description": "system-level debug logs"},
    {"name": "log_server", "columns": "method, path, status_code, duration_ms, client_ip, error", "description": "HTTP server request logs"},
]


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a memory decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "log",
        "category": category,
        "input": input_text,
        "output": output_text,
        "confidence": round(confidence, 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **context
    }
    
    with open(OUTPUT_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    
    return True


# ─────────────────────────────────────────────────────────────
# Batch Export Functions  
# ─────────────────────────────────────────────────────────────

def export_training_data(
    output_path: Optional[Path] = None,
    include_multi_turn: bool = True,
    limit: int = 500,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export conversation history to JSONL for finetuning.
    Sections: data, api, cli, schema (default: all).
    """
    from contextlib import closing
    from data.db import get_connection
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    
    if sections is None:
        sections = ["data", "api", "cli", "schema"]

    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "log_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []

    # ── Data section: conversation turns (aios source only) ──
    if "data" in sections:
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT ct.user_message, ct.assistant_message, c.session_id
                FROM convo_turns ct
                JOIN convos c ON ct.convo_id = c.id
                WHERE c.source = 'aios'
                ORDER BY ct.timestamp DESC
                LIMIT ?
            """, (limit,))
            
            for row in cur.fetchall():
                user_msg, assistant_msg, session_id = row
                if not user_msg or not assistant_msg or len(assistant_msg) < 20:
                    continue
                
                # Build real STATE so the model learns to follow it
                try:
                    from agent.subconscious.orchestrator import build_state
                    state_block = build_state(user_msg)
                except Exception:
                    state_block = "== STATE ==\nConversation with persistent memory.\n== END STATE =="
                
                examples.append({
                    "messages": [
                        {"role": "system", "content": state_block},
                        {"role": "user", "content": user_msg},
                        {"role": "assistant", "content": assistant_msg}
                    ],
                    "metadata": {"source": "log", "section": "data", "type": "conversation", "session_id": session_id}
                })

    # ── Self-knowledge sections ──
    if "api" in sections:
        examples.extend(build_api_examples("log", API_ENDPOINTS))
    if "cli" in sections:
        examples.extend(build_cli_examples("log", CLI_COMMANDS))
    if "schema" in sections:
        examples.extend(build_schema_examples("log", SCHEMA_TABLES))
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable conversation data."""
    from contextlib import closing
    from data.db import get_connection
    
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM convo_turns")
        total = cur.fetchone()[0]
    
    return {"total_turns": total, "exportable": total}


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Conversation turns & memory events", "examples": stats.get("exportable", 0)},
        "api":    {"description": "Log/timeline API endpoints", "examples": len(build_api_examples("log", API_ENDPOINTS))},
        "cli":    {"description": "CLI commands (/log)", "examples": len(build_cli_examples("log", CLI_COMMANDS))},
        "schema": {"description": "unified_events, log_system, log_server tables", "examples": len(build_schema_examples("log", SCHEMA_TABLES))},
    }
