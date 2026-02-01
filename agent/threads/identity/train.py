"""
Identity Thread Training Data Exporter
=======================================
Logs confident identity decisions AND exports facts for fine-tuning.

Live logging: log_decision() — Records high-confidence decisions
Batch export: export_training_data() — Exports identity facts to JSONL
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "identity_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7


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
    min_weight: float = 0.3
) -> Dict[str, Any]:
    """
    Export identity facts to JSONL for finetuning.
    
    Training goal: Teach the model to maintain consistent identity awareness.
    """
    from .schema import pull_profile_facts, get_profiles
    
    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "identity_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    profiles = get_profiles()
    examples = []
    total_facts = 0
    
    for profile in profiles:
        profile_id = profile.get("profile_id", "user")
        facts = pull_profile_facts(profile_id=profile_id, limit=500)
        facts = [f for f in facts if f.get("weight", 0) >= min_weight]
        total_facts += len(facts)
        
        # Group facts by prefix for context
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
            
            # Build state with related facts
            prefix = key.split(".")[0]
            related = fact_groups.get(prefix, [])[:5]
            state_lines = [f"- {f.get('key')}: {f.get('l1_value', '')}" for f in related]
            
            examples.append({
                "messages": [
                    {"role": "system", "content": f"== STATE ==\nIdentity ({profile_id}):\n" + "\n".join(state_lines)},
                    {"role": "user", "content": f"What do you know about {key.replace('.', ' ')}?"},
                    {"role": "assistant", "content": f"Based on what I know: {value}"}
                ],
                "metadata": {"source": "identity", "key": key, "weight": fact.get("weight", 0.5)}
            })
        
        # Consistency examples
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
                        "metadata": {"source": "identity", "type": "consistency"}
                    })
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "facts_exported": total_facts,
        "profiles": len(profiles),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable identity data."""
    from .schema import pull_profile_facts, get_profiles
    
    profiles = get_profiles()
    total = sum(len(pull_profile_facts(p.get("profile_id"), limit=500)) for p in profiles)
    
    return {"profiles": len(profiles), "total_facts": total, "exportable": total}
