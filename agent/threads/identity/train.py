"""
Identity Thread Training Data Exporter
=======================================
Logs confident identity decisions AND exports facts for fine-tuning.

Live logging: log_decision() — Records high-confidence decisions
Batch export: export_training_data() — Exports identity facts to JSONL

Sections: data (profile facts), api (endpoint knowledge), cli (command knowledge), schema
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "identity_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7

# ─────────────────────────────────────────────────────
# Self-knowledge: API, CLI, Schema
# ─────────────────────────────────────────────────────

API_ENDPOINTS = [
    ("GET",    "/api/identity/types",                     "Get all identity profile types"),
    ("GET",    "/api/identity/fact-types",                "Get available fact types"),
    ("POST",   "/api/identity/types",                     "Create or update an identity type"),
    ("DELETE", "/api/identity/types/{type_name}",         "Delete an identity type"),
    ("GET",    "/api/identity",                           "List all identity profiles"),
    ("POST",   "/api/identity",                           "Create or update an identity profile"),
    ("DELETE", "/api/identity/{profile_id}",              "Delete a profile and all its facts"),
    ("GET",    "/api/identity/{profile_id}/facts",        "Get all facts for a profile"),
    ("POST",   "/api/identity/facts",                     "Create or update an identity fact"),
    ("PUT",    "/api/identity/{profile_id}/facts/{key}",  "Edit an existing identity fact"),
    ("PATCH",  "/api/identity/{profile_id}/facts/{key}/weight", "Update fact weight"),
    ("DELETE", "/api/identity/{profile_id}/facts/{key}",  "Delete an identity fact"),
    ("GET",    "/api/identity/introspect",                "Get identity STATE block contribution"),
    ("GET",    "/api/identity/health",                    "Get identity thread health"),
    ("POST",   "/api/identity/import/upload",             "Upload a vCard file for import"),
    ("POST",   "/api/identity/import/parse",              "Parse uploaded vCard and preview"),
    ("POST",   "/api/identity/import/commit",             "Commit parsed contacts to profiles"),
]

CLI_COMMANDS = [
    ("/identity",                          "List all identity profiles"),
    ("/identity <profile_id>",             "Show all facts for a profile"),
    ("/identity new",                      "Create a new identity profile"),
    ("/identity fact <pid> <key> <value>", "Create/update an identity fact"),
    ("/identity delete <profile_id>",      "Delete an identity profile"),
]

SCHEMA_TABLES = [
    {"name": "profiles", "columns": "profile_id, type_name, display_name, protected", "description": "identity profiles (user, machine, contacts)"},
    {"name": "profile_facts", "columns": "profile_id, key, fact_type, l1_value, l2_value, l3_value, weight, protected, access_count", "description": "facts about each profile with 3-level detail and Hebbian weight"},
    {"name": "profile_types", "columns": "type_name, trust_level, context_priority, can_edit", "description": "identity type definitions (user, machine, contact, organization)"},
    {"name": "fact_types", "columns": "fact_type, default_weight", "description": "fact type definitions (name, email, location, occupation, etc.)"},
]


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log an identity decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "identity",
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
    include_consistency: bool = True,
    min_weight: float = 0.3,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export identity facts to JSONL for finetuning.
    
    Training goal: Teach the model to maintain consistent identity awareness.
    Sections: data, api, cli, schema (default: all).
    """
    from .schema import pull_profile_facts, get_profiles
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    
    if sections is None:
        sections = ["data", "api", "cli", "schema"]

    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "identity_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []

    # ── Data section: profile facts ──
    if "data" in sections:
        profiles = get_profiles()

        # Gather all facts across profiles for STATE building
        all_facts = []
        for profile in profiles:
            pid = profile.get("profile_id", "user")
            facts = pull_profile_facts(profile_id=pid, limit=500)
            facts = [f for f in facts if f.get("weight", 0) >= min_weight]
            for f in facts:
                f["_profile_id"] = pid
            all_facts.extend(facts)

        # Build real STATE once (or per-query for diversity)
        def get_state(query: str) -> str:
            try:
                from agent.subconscious.orchestrator import build_state
                return build_state(query)
            except Exception:
                return (
                    "== STATE ==\n"
                    "[self] My internal structure\n"
                    "  Threads: identity, philosophy, log, reflex, form, linking_core\n"
                    "[identity] Who I am and who my user is\n"
                    "  context_level: 2\n"
                    "== END STATE =="
                )

        # Diverse question templates that force natural state use
        q_templates = [
            ("What do you know about me?", lambda fs: _natural_identity_response(fs, "user")),
            ("Who are you?", lambda fs: _natural_identity_response(fs, "machine")),
            ("Tell me about yourself.", lambda fs: _natural_identity_response(fs, "machine")),
            ("What's my name?", lambda fs: _specific_fact_response(fs, "name")),
            ("Do you remember what I do for work?", lambda fs: _specific_fact_response(fs, "occupation")),
            ("What do you know about my preferences?", lambda fs: _preference_response(fs)),
        ]

        # Generate diverse conversational examples
        for query, response_fn in q_templates:
            state = get_state(query)
            response = response_fn(all_facts)
            if response:
                examples.append({
                    "messages": [
                        {"role": "system", "content": state},
                        {"role": "user", "content": query},
                        {"role": "assistant", "content": response},
                    ],
                    "metadata": {"source": "identity", "section": "data", "type": "conversational"},
                })

        # Per-fact examples with real STATE and natural responses
        for fact in all_facts:
            key = fact.get("key", "")
            value = fact.get("l3_value") or fact.get("l2_value") or fact.get("l1_value", "")
            pid = fact.get("_profile_id", "")
            if not value:
                continue

            parts = pid.split(".")
            profile_short = parts[1] if len(parts) >= 2 else pid
            dot_path = f"identity.{profile_short}.{key}"

            state = get_state(key.replace(".", " "))
            examples.append({
                "messages": [
                    {"role": "system", "content": state},
                    {"role": "user", "content": f"What do you know about {key.replace('.', ' ')}?"},
                    {"role": "assistant", "content": f"From my identity thread — {dot_path}: {value}"},
                ],
                "metadata": {"source": "identity", "section": "data", "key": key, "weight": fact.get("weight", 0.5)},
            })

        # Consistency drills — teach the model to hold ground
        if include_consistency:
            for fact in all_facts[:15]:
                key = fact.get("key", "")
                value = fact.get("l1_value", "")
                pid = fact.get("_profile_id", "")
                if not value:
                    continue
                parts = pid.split(".")
                profile_short = parts[1] if len(parts) >= 2 else pid
                dot_path = f"identity.{profile_short}.{key}"

                state = get_state(key)
                examples.append({
                    "messages": [
                        {"role": "system", "content": state},
                        {"role": "user", "content": f"Actually, that's wrong about {key.split('.')[-1]}."},
                        {"role": "assistant", "content": f"My identity thread has {dot_path}: {value}. If that's changed, tell me what's correct and I'll update it."},
                    ],
                    "metadata": {"source": "identity", "section": "data", "type": "consistency"},
                })

        # Architectural self-knowledge (baked into weights)
        arch_state = get_state("identity thread architecture")
        arch_examples = [
            ("How does your identity system work?",
             "My identity thread answers WHO. It stores profiles in the identity_profiles table — "
             "one for me (identity.nola), one for my user, and any contacts. Each profile has facts "
             "at 3 detail levels (l1_value is lean, l3_value is full) with Hebbian weights. When STATE "
             "is built, the orchestrator calls my introspect() method and I pack the highest-weighted "
             "facts into the token budget using dot-notation: identity.nola.name, identity.user.occupation, etc."),
            ("What identity profiles do you have?",
             f"I have {len(profiles)} profiles. The main ones are identity.nola (my self-model) and "
             "identity.user (what I know about you). Contacts get their own profiles too. Each profile "
             "can store facts like name, role, preferences — anything I learn goes into profile_facts "
             "with a weight that strengthens through Hebbian reinforcement."),
            ("How do identity facts get into STATE?",
             "The orchestrator scores my identity thread against the query using linking_core. If identity "
             "scores high, it calls my introspect() method. I sort facts by weight descending and pack them "
             "into the token budget at the right detail level. Top facts get l2/l3 detail, tail facts "
             "get downgraded to l1 so context stays compact. The output is dot-notation: identity.nola.name: Nola."),
        ]
        for q, a in arch_examples:
            examples.append({
                "messages": [
                    {"role": "system", "content": arch_state},
                    {"role": "user", "content": q},
                    {"role": "assistant", "content": a},
                ],
                "metadata": {"source": "identity", "section": "data", "type": "architecture"},
            })

    # ── Self-knowledge sections ──
    if "api" in sections:
        examples.extend(build_api_examples("identity", API_ENDPOINTS))
    if "cli" in sections:
        examples.extend(build_cli_examples("identity", CLI_COMMANDS))
    if "schema" in sections:
        examples.extend(build_schema_examples("identity", SCHEMA_TABLES))
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable identity data."""
    from .schema import pull_profile_facts, get_profiles
    
    profiles = get_profiles()
    total = sum(len(pull_profile_facts(p.get("profile_id"), limit=500)) for p in profiles)
    
    return {"profiles": len(profiles), "total_facts": total, "exportable": total}


# ─────────────────────────────────────────────────────────────
# Response helpers — generate natural, state-grounded responses
# ─────────────────────────────────────────────────────────────

def _natural_identity_response(facts: list, profile_filter: str) -> str:
    """Build a natural response summarizing identity facts for a profile type."""
    relevant = [f for f in facts if profile_filter in f.get("_profile_id", "")]
    if not relevant:
        return ""
    parts = []
    for f in relevant[:5]:
        key = f.get("key", "")
        val = f.get("l1_value") or f.get("l2_value", "")
        pid = f.get("_profile_id", "")
        p_parts = pid.split(".")
        profile_short = p_parts[1] if len(p_parts) >= 2 else pid
        if val:
            parts.append(f"identity.{profile_short}.{key} is {val}")
    if not parts:
        return ""
    return "From my identity thread: " + ", ".join(parts) + "."


def _specific_fact_response(facts: list, key_contains: str) -> str:
    """Build a response for a specific fact query."""
    for f in facts:
        key = f.get("key", "")
        if key_contains in key.lower():
            val = f.get("l1_value") or f.get("l2_value", "")
            pid = f.get("_profile_id", "")
            p_parts = pid.split(".")
            profile_short = p_parts[1] if len(p_parts) >= 2 else pid
            if val:
                return f"Yes — identity.{profile_short}.{key}: {val}"
    return ""


def _preference_response(facts: list) -> str:
    """Build a response about user preferences."""
    prefs = [f for f in facts if f.get("fact_type") == "preference"]
    if not prefs:
        prefs = [f for f in facts if "prefer" in f.get("key", "").lower()]
    if not prefs:
        return ""
    parts = []
    for f in prefs[:4]:
        key = f.get("key", "")
        val = f.get("l1_value") or f.get("l2_value", "")
        if val:
            parts.append(f"{key}: {val}")
    if not parts:
        return ""
    return "Here's what I have in my identity thread for your preferences: " + "; ".join(parts) + "."


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import build_api_examples, build_cli_examples, build_schema_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Profile facts & consistency drills", "examples": stats.get("exportable", 0)},
        "api":    {"description": "Identity API endpoints", "examples": len(build_api_examples("identity", API_ENDPOINTS))},
        "cli":    {"description": "CLI commands (/identity)", "examples": len(build_cli_examples("identity", CLI_COMMANDS))},
        "schema": {"description": "profiles, profile_facts, profile_types tables", "examples": len(build_schema_examples("identity", SCHEMA_TABLES))},
    }
