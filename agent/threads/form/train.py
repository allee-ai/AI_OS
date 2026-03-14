"""
Form Thread Training Data
=========================
Logs confident capability decisions for fine-tuning.

Sections: data (tool definitions), api (endpoint knowledge), cli (command knowledge), schema
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "form_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7

# ─────────────────────────────────────────────────────
# Self-knowledge: API, CLI, Schema
# ─────────────────────────────────────────────────────

API_ENDPOINTS = [
    ("GET",    "/api/form/tools",                    "Get all tool definitions"),
    ("GET",    "/api/form/tools/{name}",             "Get a specific tool with handler code"),
    ("POST",   "/api/form/tools",                    "Create a new tool definition"),
    ("PUT",    "/api/form/tools/{name}",             "Update a tool definition"),
    ("DELETE", "/api/form/tools/{name}",             "Delete a tool definition"),
    ("POST",   "/api/form/tools/{name}/rename",      "Rename a tool and its executable"),
    ("GET",    "/api/form/tools/{name}/code",        "Get the executable code for a tool"),
    ("PUT",    "/api/form/tools/{name}/code",        "Update the executable code for a tool"),
    ("POST",   "/api/form/tools/{name}/execute",     "Execute a tool action in sandbox"),
    ("GET",    "/api/form/categories",               "Get available tool categories"),
    ("GET",    "/api/form/traces",                   "Get recent tool execution traces by weight"),
    ("GET",    "/api/form/traces/{trace_id}",        "Get a single tool trace"),
    ("GET",    "/api/form/traces/stats",             "Get aggregate stats for tool traces"),
    ("GET",    "/api/form/introspect",               "Get form STATE block contribution"),
    ("GET",    "/api/form/health",                   "Get form thread health"),
]

CLI_COMMANDS = [
    ("/tools",                              "List all tools with status"),
    ("/tools <name>",                       "Show details for a specific tool"),
    ("/tools new",                          "Create a new tool definition"),
    ("/tools run <name> <action> [json]",   "Execute a tool action"),
    ("/tools code <name>",                  "Display executable code for a tool"),
    ("/tools toggle <name>",                "Toggle tool enabled/disabled"),
    ("/tools delete <name>",                "Delete a tool definition"),
    ("/tools categories",                   "List available tool categories"),
]

SCHEMA_TABLES = [
    {"name": "form_tools", "columns": "name, description, category, actions, run_file, run_type, requires_env, weight, enabled, allowed", "description": "tool definitions with actions, code references, Hebbian weight, and enable/disable state"},
]


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a form decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "form",
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
    Export tool usage patterns to JSONL for finetuning.
    Sections: data, api, cli, schema (default: all).
    """
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples

    if sections is None:
        sections = ["data", "api", "cli", "schema"]

    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "form_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []

    # ── Data section: tool definitions ──
    if "data" in sections:
        try:
            from .tools.registry import get_all_tools
            tools = get_all_tools()
            
            for tool in tools:
                name = tool.name
                desc = tool.description
                if name and desc:
                    examples.append({
                        "messages": [
                            {"role": "system", "content": f"== STATE ==\nTool available: {name}"},
                            {"role": "user", "content": f"When should I use the {name} tool?"},
                            {"role": "assistant", "content": f"The {name} tool is used for: {desc}"}
                        ],
                        "metadata": {"source": "form", "section": "data", "type": "tool_description", "tool": name}
                    })
        except ImportError:
            pass

    # ── Self-knowledge sections ──
    if "api" in sections:
        examples.extend(build_api_examples("form", API_ENDPOINTS))
    if "cli" in sections:
        examples.extend(build_cli_examples("form", CLI_COMMANDS))
    if "schema" in sections:
        examples.extend(build_schema_examples("form", SCHEMA_TABLES))
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable form data."""
    try:
        from .tools.registry import get_all_tools
        tools = get_all_tools()
        return {"tools": len(tools), "exportable": len(tools)}
    except ImportError:
        return {"tools": 0, "exportable": 0}


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Tool definitions & usage patterns", "examples": stats.get("exportable", 0)},
        "api":    {"description": "Form/tools API endpoints", "examples": len(build_api_examples("form", API_ENDPOINTS))},
        "cli":    {"description": "CLI commands (/tools)", "examples": len(build_cli_examples("form", CLI_COMMANDS))},
        "schema": {"description": "form_tools table", "examples": len(build_schema_examples("form", SCHEMA_TABLES))},
    }


