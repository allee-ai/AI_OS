"""
Linking Core Training Data Exporter
====================================
Logs confident activation patterns AND exports LONG links for fine-tuning.

Live logging (during conversation):
    log_decision() — Records high-confidence decisions

Batch export (for finetune):
    export_training_data() — Exports consolidated LONG links to JSONL

Sections: data (association examples), api (endpoint knowledge), cli (command knowledge), schema
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "linking_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7

# ─────────────────────────────────────────────────────
# Self-knowledge: API, CLI, Schema
# ─────────────────────────────────────────────────────

API_ENDPOINTS = [
    ("GET",    "/api/linking_core/concepts",          "List all unique concepts in the graph"),
    ("POST",   "/api/linking_core/concepts/extract",  "Extract concepts from input text"),
    ("GET",    "/api/linking_core/links",             "List all concept links"),
    ("GET",    "/api/linking_core/links/{concept}",   "Get all links for a specific concept"),
    ("POST",   "/api/linking_core/links",             "Create a new concept link"),
    ("PUT",    "/api/linking_core/links",             "Update link strength"),
    ("DELETE", "/api/linking_core/links",             "Delete a concept link"),
    ("GET",    "/api/linking_core/graph",             "Get graph data for 3D visualization"),
    ("GET",    "/api/linking_core/graph/path",        "Find activation path between two concepts"),
    ("GET",    "/api/linking_core/graph/structural",  "Structural mind map of entire agent"),
    ("POST",   "/api/linking_core/activate",          "Run spread activation from input concepts"),
    ("GET",    "/api/linking_core/activate/{text}",   "Extract concepts from text and activate"),
    ("POST",   "/api/linking_core/score",             "Score facts by relevance to input"),
    ("POST",   "/api/linking_core/score/threads",     "Score all threads for context gating"),
    ("GET",    "/api/linking_core/cooccurrence",      "Get co-occurrence pairs"),
    ("GET",    "/api/linking_core/stats",             "Get linking core statistics"),
]

CLI_COMMANDS = [
    ("/graph <query>",          "Spread-activate from query and show top-15 scored concepts"),
    ("/mindmap [thread|links]", "Show structural mind-map of the agent"),
]

SCHEMA_TABLES = [
    {"name": "concept_links", "columns": "concept_a, concept_b, strength, fire_count, potentiation, last_fired, created_at", "description": "Hebbian concept associations with strength and SHORT/LONG potentiation"},
    {"name": "key_cooccurrence", "columns": "key_a, key_b, count, last_seen", "description": "Co-occurrence counts between concepts appearing together"},
]


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a linking decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "linking_core",
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
    include_spread: bool = True,
    min_strength: float = 0.5,
    min_fire_count: int = 3,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export LONG-potentiated concept links to JSONL for finetuning.
    
    Training goal: Teach the model associative recall.
    Sections: data, api, cli, schema (default: all).
    """
    from .schema import get_long_links, get_potentiation_stats, spread_activate
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    
    if sections is None:
        sections = ["data", "api", "cli", "schema"]

    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "linking_core_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []

    # ── Data section: concept associations ──
    if "data" in sections:
        links = get_long_links(limit=1000)
        links = [l for l in links 
                 if l["strength"] >= min_strength and l["fire_count"] >= min_fire_count]
        
        for link in links:
            concept_a = link["concept_a"]
            concept_b = link["concept_b"]
            strength = link["strength"]
            fire_count = link["fire_count"]
            
            for primary, related in [(concept_a, concept_b), (concept_b, concept_a)]:
                examples.append({
                    "messages": [
                        {"role": "system", "content": f"== STATE ==\nAssociations: {primary} ↔ {related} (strength: {strength:.2f})"},
                        {"role": "user", "content": f"What do you associate with {primary}?"},
                        {"role": "assistant", "content": f"When {primary} comes up, I also think of {related}. They've been connected {fire_count} times."}
                    ],
                    "metadata": {"source": "linking_core", "section": "data", "type": "association", "strength": strength}
                })
        
        if include_spread and links:
            seeds = list(set([l["concept_a"] for l in links[:30]]))[:10]
            for seed in seeds:
                activated = spread_activate([seed], activation_threshold=0.3, max_hops=2, limit=5)
                if activated:
                    chain = ", ".join([a['concept'] for a in activated])
                    examples.append({
                        "messages": [
                            {"role": "system", "content": f"== STATE ==\nSpread activation from '{seed}'"},
                            {"role": "user", "content": f"What comes to mind when you think about {seed}?"},
                            {"role": "assistant", "content": f"Thinking about {seed} brings up: {chain}."}
                        ],
                        "metadata": {"source": "linking_core", "section": "data", "type": "spread_activation", "seed": seed}
                    })

    # ── Self-knowledge sections ──
    if "api" in sections:
        examples.extend(build_api_examples("linking_core", API_ENDPOINTS))
    if "cli" in sections:
        examples.extend(build_cli_examples("linking_core", CLI_COMMANDS))
    if "schema" in sections:
        examples.extend(build_schema_examples("linking_core", SCHEMA_TABLES))
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable linking data."""
    from .schema import get_long_links, get_potentiation_stats
    
    links = get_long_links(limit=1000)
    stats = get_potentiation_stats()
    exportable = len([l for l in links if l["strength"] >= 0.5 and l["fire_count"] >= 3])
    
    return {
        "long_links": len(links),
        "potentiation": stats,
        "exportable": exportable
    }


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Concept associations & spread activation chains", "examples": stats.get("exportable", 0)},
        "api":    {"description": "Linking core API endpoints", "examples": len(build_api_examples("linking_core", API_ENDPOINTS))},
        "cli":    {"description": "CLI commands (/graph, /mindmap)", "examples": len(build_cli_examples("linking_core", CLI_COMMANDS))},
        "schema": {"description": "concept_links & key_cooccurrence tables", "examples": len(build_schema_examples("linking_core", SCHEMA_TABLES))},
    }
