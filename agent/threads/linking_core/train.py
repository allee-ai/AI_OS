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
# Template Loading
# ─────────────────────────────────────────────────────────────

def _load_templates(module: str, section: str) -> List[Dict[str, str]]:
    """Load enabled training templates from the DB for a module+section."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
            return conn.execute(
                "SELECT * FROM training_templates WHERE module = ? AND section = ? AND enabled = 1",
                (module, section),
            ).fetchall()
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────
# Batch Export Functions
# ─────────────────────────────────────────────────────────────

def export_training_data(
    output_path: Optional[Path] = None,
    include_spread: bool = True,
    min_strength: float = 0.5,
    min_fire_count: int = 3,
    max_associations: int = 100,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export LONG-potentiated concept links to JSONL for finetuning.
    
    Training goal: Teach the model associative recall.
    Capped at max_associations bidirectional pairs to avoid flooding
    the dataset with mechanical "I associate X with Y" patterns.
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

    # ── Data section: template-driven from training_templates table ──
    if "data" in sections:
        def get_state(query: str) -> str:
            try:
                from agent.subconscious.orchestrator import build_state
                return build_state(query)
            except Exception:
                return (
                    "== STATE ==\n"
                    "[self] My internal structure\n"
                    "  Threads: identity, philosophy, log, reflex, form, linking_core\n"
                    "[linking_core] My concept graph and relevance scoring\n"
                    "  context_level: 2\n"
                    "== END STATE =="
                )

        # Load templates from DB
        templates = _load_templates("linking_core", "data")

        # Association templates
        assoc_templates = [t for t in templates if t["name"] == "association"]
        if assoc_templates:
            links = get_long_links(limit=1000)
            links = [l for l in links
                     if l["strength"] >= min_strength and l["fire_count"] >= min_fire_count]
            links.sort(key=lambda l: l["strength"], reverse=True)
            links = links[:max_associations]

            for link in links:
                state = get_state(link["concept_a"])
                for tpl in assoc_templates:
                    try:
                        q = tpl["question_template"].format_map(link)
                        a = tpl["answer_template"].format_map(link)
                    except (KeyError, ValueError):
                        continue
                    examples.append({
                        "messages": [
                            {"role": "system", "content": state},
                            {"role": "user", "content": q},
                            {"role": "assistant", "content": a},
                        ],
                        "metadata": {"source": "linking_core", "section": "data", "type": "association", "template": tpl["name"], "strength": link["strength"]},
                    })

        # Spread activation templates
        spread_templates = [t for t in templates if t["name"] == "spread_activation"]
        if include_spread and spread_templates:
            # Get seeds from top links
            seed_links = get_long_links(limit=30)
            seeds = list(set([l["concept_a"] for l in seed_links]))[:5]
            for seed in seeds:
                activated = spread_activate([seed], activation_threshold=0.3, max_hops=2, limit=5)
                if activated:
                    row = {"seed": seed, "chain": ", ".join([a["concept"] for a in activated])}
                    state = get_state(seed)
                    for tpl in spread_templates:
                        try:
                            q = tpl["question_template"].format_map(row)
                            a = tpl["answer_template"].format_map(row)
                        except (KeyError, ValueError):
                            continue
                        examples.append({
                            "messages": [
                                {"role": "system", "content": state},
                                {"role": "user", "content": q},
                                {"role": "assistant", "content": a},
                            ],
                            "metadata": {"source": "linking_core", "section": "data", "type": "spread_activation", "template": tpl["name"], "seed": seed},
                        })

        # Architectural self-knowledge — this is critical, must be in weights
        stats = get_potentiation_stats()
        arch_state = get_state("linking core concept graph")
        arch_examples = [
            ("How does your concept graph work?",
             "My linking_core thread answers WHICH — which concepts are related, which threads "
             "are relevant to a query. It's a Hebbian associative graph stored in concept_links. "
             "Every conversation extracts concepts and fires links between co-occurring ones. "
             "Links have strength (0-1), fire_count, and potentiation state (SHORT or LONG). "
             "SHORT links decay quickly; LONG links (fire_count ≥ 3, strength ≥ 0.5) persist. "
             f"Current stats: {stats.get('long', 0)} LONG links, {stats.get('short', 0)} SHORT links."),
            ("What is spread activation?",
             "Spread activation is how I find relevant context. Given input concepts, I activate "
             "their neighbors in the graph, weighted by link strength. It ripples outward — hop 1 "
             "hits direct associations, hop 2 reaches second-order connections. The result is a "
             "ranked list of activated concepts. The orchestrator uses this to score all my threads "
             "and decide what goes into STATE."),
            ("How does the scoring system work?",
             "When you send a message, linking_core extracts concepts from your text, then scores "
             "every thread (identity, form, philosophy, etc.) by relevance. The score determines "
             "each thread's context_level in STATE: low score → L1 (lean, few facts), high score → "
             "L3 (full detail). This is the gating mechanism — not everything I know goes into STATE, "
             "only what's relevant to right now."),
            ("What's Hebbian learning?",
             "Neurons that fire together wire together. In my linking_core, when two concepts "
             "appear in the same conversation, their link strength increases. The more they co-occur, "
             "the stronger the link. Links also decay if they stop firing. This is how I build "
             "associative memory organically from conversations, without explicit programming."),
        ]
        for q, a in arch_examples:
            examples.append({
                "messages": [
                    {"role": "system", "content": arch_state},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a},
                ],
                "metadata": {"source": "linking_core", "section": "data", "type": "architecture"},
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
    """Get stats about exportable linking data (count-only, no row fetch)."""
    from .schema import get_connection, get_potentiation_stats
    from contextlib import closing

    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM concept_links WHERE potentiation = 'LONG'")
        long_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM concept_links WHERE potentiation = 'LONG' AND strength >= 0.5 AND fire_count >= 3")
        exportable = cur.fetchone()[0]

    stats = get_potentiation_stats()

    return {
        "long_links": long_count,
        "potentiation": stats,
        "exportable": exportable
    }


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import count_api_examples, count_cli_examples, count_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Concept associations & spread activation chains", "examples": stats.get("exportable", 0)},
        "api":    {"description": "Linking core API endpoints", "examples": count_api_examples(API_ENDPOINTS)},
        "cli":    {"description": "CLI commands (/graph, /mindmap)", "examples": count_cli_examples(CLI_COMMANDS)},
        "schema": {"description": "concept_links & key_cooccurrence tables", "examples": count_schema_examples(SCHEMA_TABLES)},
    }
