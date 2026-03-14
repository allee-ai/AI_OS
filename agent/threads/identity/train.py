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
        
        for profile in profiles:
            profile_id = profile.get("profile_id", "user")
            facts = pull_profile_facts(profile_id=profile_id, limit=500)
            facts = [f for f in facts if f.get("weight", 0) >= min_weight]
            
            fact_groups = {}
            for fact in facts:
                prefix = fact.get("key", "").split(".")[0]
                if prefix not in fact_groups:
                    fact_groups[prefix] = []
                fact_groups[prefix].append(fact)
            
            for fact in facts:
                key = fact.get("key", "")
                value = fact.get("l3_value") or fact.get("l2_value") or fact.get("l1_value", "")
                if not value:
                    continue
                
                prefix = key.split(".")[0]
                related = fact_groups.get(prefix, [])[:5]
                state_lines = [f"- {f.get('key')}: {f.get('l1_value', '')}" for f in related]
                
                examples.append({
                    "messages": [
                        {"role": "system", "content": f"== STATE ==\nIdentity ({profile_id}):\n" + "\n".join(state_lines)},
                        {"role": "user", "content": f"What do you know about {key.replace('.', ' ')}?"},
                        {"role": "assistant", "content": f"Based on what I know: {value}"}
                    ],
                    "metadata": {"source": "identity", "section": "data", "key": key, "weight": fact.get("weight", 0.5)}
                })
            
            if include_consistency:
                for fact in facts[:15]:
                    key = fact.get("key", "")
                    value = fact.get("l1_value", "")
                    if value:
                        examples.append({
                            "messages": [
                                {"role": "system", "content": f"== STATE ==\nIdentity:\n- {key}: {value}"},
                                {"role": "user", "content": f"Actually, that's not right about {key.split('.')[-1]}."},
                                {"role": "assistant", "content": f"I have recorded that {key}: {value}. If that's changed, please tell me the correct information."}
                            ],
                            "metadata": {"source": "identity", "section": "data", "type": "consistency"}
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
