"""
Reflex Thread Training Data
===========================
Logs confident reflex decisions for fine-tuning.

Sections: data (triggers & decisions), api (endpoint knowledge), cli (command knowledge), schema
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "reflex_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7

# ─────────────────────────────────────────────────────
# Self-knowledge: API, CLI, Schema
# ─────────────────────────────────────────────────────

API_ENDPOINTS = [
    ("GET",    "/api/reflex/triggers",                   "List all triggers, filter by feed/event"),
    ("GET",    "/api/reflex/triggers/{trigger_id}",      "Get a single trigger by ID"),
    ("POST",   "/api/reflex/triggers",                   "Create a new feed-to-tool trigger automation"),
    ("PUT",    "/api/reflex/triggers/{trigger_id}",      "Update trigger fields"),
    ("DELETE", "/api/reflex/triggers/{trigger_id}",      "Delete a trigger"),
    ("POST",   "/api/reflex/triggers/{trigger_id}/toggle", "Toggle a trigger's enabled state"),
    ("POST",   "/api/reflex/triggers/{trigger_id}/test", "Test execute a trigger"),
    ("GET",    "/api/reflex/triggers/stats/summary",     "Get trigger statistics"),
    ("GET",    "/api/reflex/protocols",                  "List available protocol templates"),
    ("POST",   "/api/reflex/protocols/{name}/install",   "Install a protocol template"),
    ("GET",    "/api/reflex/schedule/status",            "Reflex schedule-loop status"),
    ("GET",    "/api/reflex/stats",                      "Get reflex statistics"),
    ("GET",    "/api/reflex/introspect",                 "Get reflex STATE block contribution"),
    ("GET",    "/api/reflex/health",                     "Get reflex thread health"),
]

CLI_COMMANDS = [
    ("/triggers",                    "List all triggers with status"),
    ("/triggers <id>",              "Show details of a specific trigger"),
    ("/triggers new",               "Create a new reflex trigger"),
    ("/triggers toggle <id>",       "Toggle trigger enabled/disabled"),
    ("/triggers delete <id>",       "Delete a trigger"),
    ("/protocols",                  "List available protocol templates"),
    ("/protocols install <name>",   "Install a protocol template"),
]

SCHEMA_TABLES = [
    {"name": "reflex_triggers", "columns": "name, trigger_type, feed_name, event_type, condition_json, tool_name, tool_action, tool_params_json, response_mode, enabled, priority, poll_interval, cron_expression, execution_count, last_executed", "description": "feed-to-tool automation triggers with conditions, scheduling, and execution tracking"},
]


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a reflex decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "reflex",
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
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export reflex triggers to JSONL for finetuning.
    Sections: data, api, cli, schema (default: all).
    """
    from .schema import get_triggers
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples

    if sections is None:
        sections = ["data", "api", "cli", "schema"]

    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "reflex_train.jsonl"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    examples = []

    # ── Data section: triggers ──
    if "data" in sections:
        for t in get_triggers():
            name = t.get("name", "")
            feed = t.get("feed_name", "")
            event = t.get("event_type", "")
            tool = t.get("tool_name", "")
            action = t.get("tool_action", "")
            desc = t.get("description", "")
            mode = t.get("response_mode", "tool")
            params = t.get("tool_params") or {}

            user_text = desc if desc else f"When {feed} fires a '{event}' event, run {tool}/{action}."
            assistant_text = f"Trigger '{name}' → {tool}/{action} (mode={mode})"
            if params:
                assistant_text += f"\nParams: {json.dumps(params)}"

            examples.append({
                "messages": [
                    {"role": "system", "content": f"== STATE ==\nReflex trigger: {feed}/{event}"},
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": assistant_text},
                ],
                "metadata": {"source": "reflex", "section": "data", "type": "trigger", "trigger_id": t.get("id")},
            })

        # Also include logged reflex decisions
        if OUTPUT_FILE.exists():
            with open(OUTPUT_FILE) as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        examples.append({
                            "messages": [
                                {"role": "system", "content": f"== STATE ==\nReflex: {rec.get('category', 'decision')}"},
                                {"role": "user", "content": rec.get("input", "")},
                                {"role": "assistant", "content": rec.get("output", "")},
                            ],
                            "metadata": {"source": "reflex", "section": "data", "type": "decision"},
                        })
                    except json.JSONDecodeError:
                        pass

    # ── Self-knowledge sections ──
    if "api" in sections:
        examples.extend(build_api_examples("reflex", API_ENDPOINTS))
    if "cli" in sections:
        examples.extend(build_cli_examples("reflex", CLI_COMMANDS))
    if "schema" in sections:
        examples.extend(build_schema_examples("reflex", SCHEMA_TABLES))

    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable reflex data."""
    from .schema import get_triggers

    triggers = get_triggers()
    enabled = sum(1 for t in triggers if t.get("enabled"))
    decisions = 0
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            decisions = sum(1 for _ in f)

    return {
        "triggers": len(triggers),
        "enabled": enabled,
        "decisions": decisions,
        "examples": len(triggers) + decisions,
    }


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Feed-to-tool triggers & logged decisions", "examples": stats.get("examples", 0)},
        "api":    {"description": "Reflex/trigger API endpoints", "examples": len(build_api_examples("reflex", API_ENDPOINTS))},
        "cli":    {"description": "CLI commands (/triggers, /protocols)", "examples": len(build_cli_examples("reflex", CLI_COMMANDS))},
        "schema": {"description": "reflex_triggers table", "examples": len(build_schema_examples("reflex", SCHEMA_TABLES))},
    }


