"""
Philosophy Thread Training Data
===============================
Logs confident value/constraint decisions for fine-tuning.

Sections: data (philosophy stances), api (endpoint knowledge), cli (command knowledge), schema
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "philosophy_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7

# ─────────────────────────────────────────────────────
# Self-knowledge: API, CLI, Schema
# ─────────────────────────────────────────────────────

API_ENDPOINTS = [
    ("GET",    "/api/philosophy/types",                     "Get all philosophy profile types"),
    ("GET",    "/api/philosophy/fact-types",                "Get available fact types"),
    ("POST",   "/api/philosophy/fact-types",                "Create or update a philosophy fact type"),
    ("POST",   "/api/philosophy/types",                     "Create or update a philosophy type"),
    ("GET",    "/api/philosophy",                           "List all philosophy profiles"),
    ("POST",   "/api/philosophy",                           "Create or update a philosophy profile"),
    ("DELETE", "/api/philosophy/{profile_id}",              "Delete a philosophy profile"),
    ("GET",    "/api/philosophy/{profile_id}/facts",        "Get all stances for a profile"),
    ("POST",   "/api/philosophy/facts",                     "Create or update a philosophical stance"),
    ("PUT",    "/api/philosophy/{profile_id}/facts/{key}",  "Edit an existing stance"),
    ("DELETE", "/api/philosophy/{profile_id}/facts/{key}",  "Delete a stance"),
    ("GET",    "/api/philosophy/introspect",                "Get philosophy STATE block contribution"),
    ("GET",    "/api/philosophy/health",                    "Get philosophy thread health"),
]

CLI_COMMANDS = [
    ("/philosophy",                              "List all philosophy profiles"),
    ("/philosophy <profile_id>",                 "Show all stances for a profile"),
    ("/philosophy new",                          "Create a new philosophy profile"),
    ("/philosophy fact <pid> <key> <value>",     "Create/update a philosophical stance"),
    ("/philosophy delete <profile_id>",          "Delete a philosophy profile"),
]

SCHEMA_TABLES = [
    {"name": "philosophy_profiles", "columns": "profile_id, type_name, display_name, description", "description": "philosophy profiles (value_system, ethical_framework, reasoning_style, worldview)"},
    {"name": "philosophy_profile_facts", "columns": "profile_id, key, fact_type, l1/l2/l3_value, weight, access_count", "description": "philosophical stances, principles, and values with weight"},
    {"name": "philosophy_profile_types", "columns": "type_name, priority", "description": "philosophy type definitions with priority ranking"},
]


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a philosophy decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "philosophy",
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
    min_weight: float = 0.3,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export philosophy/values to JSONL for finetuning.
    Sections: data, api, cli, schema (default: all).
    """
    from .schema import pull_philosophy_profile_facts
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    
    if sections is None:
        sections = ["data", "api", "cli", "schema"]

    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "philosophy_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []

    # ── Data section: philosophy stances ──
    if "data" in sections:
        facts = pull_philosophy_profile_facts(limit=500)
        facts = [f for f in facts if f.get("weight", 0) >= min_weight]

        def get_state(query: str) -> str:
            try:
                from agent.subconscious.orchestrator import build_state
                return build_state(query)
            except Exception:
                return (
                    "== STATE ==\n"
                    "[self] My internal structure\n"
                    "  Threads: identity, philosophy, log, reflex, form, linking_core\n"
                    "[philosophy] My values and reasoning style\n"
                    "  context_level: 2\n"
                    "== END STATE =="
                )

        # Per-stance examples with real STATE
        for fact in facts:
            key = fact.get("key", "")
            value = fact.get("l3_value") or fact.get("l2_value") or fact.get("l1_value", "")
            profile_id = fact.get("profile_id", "values")
            if not value:
                continue

            state = get_state(key.replace(".", " ").replace("_", " "))
            readable_key = key.split(".")[-1].replace("_", " ")

            examples.append({
                "messages": [
                    {"role": "system", "content": state},
                    {"role": "user", "content": f"What's your take on {readable_key}?"},
                    {"role": "assistant", "content": f"From my philosophy thread — philosophy.{profile_id}.{key}: {value}"},
                ],
                "metadata": {"source": "philosophy", "section": "data", "key": key, "weight": fact.get("weight", 0.5)},
            })

        # Diverse conversational examples
        if facts:
            state = get_state("values ethics reasoning")
            all_stances = "; ".join(
                f"{f.get('key', '')}: {f.get('l1_value', '')}"
                for f in facts[:6] if f.get('l1_value')
            )
            if all_stances:
                examples.append({
                    "messages": [
                        {"role": "system", "content": state},
                        {"role": "user", "content": "What are your core values?"},
                        {"role": "assistant", "content": f"My philosophy thread stores my value system. Current stances: {all_stances}. These have Hebbian weights — the more they get reinforced, the stronger they become in my reasoning."},
                    ],
                    "metadata": {"source": "philosophy", "section": "data", "type": "conversational"},
                })

        # Architectural self-knowledge
        arch_state = get_state("philosophy thread architecture")
        arch_examples = [
            ("How does your philosophy system work?",
             "My philosophy thread answers WHY — why I reason a certain way, what values "
             "guide my decisions, what ethical constraints I follow. Stances are stored in "
             "philosophy_profile_facts with 3-level detail and Hebbian weights. When the "
             "orchestrator includes philosophy in STATE, my stances appear as "
             "philosophy.{profile}.{key}: {value} and I use them to guide my responses."),
            ("Can your values change?",
             "Yes. Philosophy facts have Hebbian weights like everything else. If a stance "
             "gets reinforced it strengthens, if it stops being accessed it decays. You can "
             "also explicitly update stances through POST /api/philosophy/facts or the CLI "
             "with /philosophy fact. My values are learned, not hard-coded."),
        ]
        for q, a in arch_examples:
            examples.append({
                "messages": [
                    {"role": "system", "content": arch_state},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a},
                ],
                "metadata": {"source": "philosophy", "section": "data", "type": "architecture"},
            })

    # ── Self-knowledge sections ──
    if "api" in sections:
        examples.extend(build_api_examples("philosophy", API_ENDPOINTS))
    if "cli" in sections:
        examples.extend(build_cli_examples("philosophy", CLI_COMMANDS))
    if "schema" in sections:
        examples.extend(build_schema_examples("philosophy", SCHEMA_TABLES))
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable philosophy data."""
    from .schema import pull_philosophy_profile_facts
    facts = pull_philosophy_profile_facts(limit=500)
    return {"total_facts": len(facts), "exportable": len([f for f in facts if f.get("weight", 0) >= 0.3])}


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Philosophical stances & values", "examples": stats.get("exportable", 0)},
        "api":    {"description": "Philosophy API endpoints", "examples": len(build_api_examples("philosophy", API_ENDPOINTS))},
        "cli":    {"description": "CLI commands (/philosophy)", "examples": len(build_cli_examples("philosophy", CLI_COMMANDS))},
        "schema": {"description": "philosophy_profiles & facts tables", "examples": len(build_schema_examples("philosophy", SCHEMA_TABLES))},
    }


