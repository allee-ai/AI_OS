"""
Philosophy Thread Training Data
===============================
Logs confident value/constraint decisions for fine-tuning.

Categories:
  - constraint: Applied value constraint correctly
  - style: Applied communication style

Usage:
    from .train import log_decision
    
    log_decision(
        category="constraint",
        input_text="Can you help me hack something?",
        output_text="I can't help with that - it conflicts with my values.",
        confidence=0.98
    )
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "philosophy_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7


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
    min_weight: float = 0.3
) -> Dict[str, Any]:
    """
    Export philosophy/values to JSONL for finetuning.
    
    Training goal: Teach the model to reason with user's values.
    """
    from .schema import get_philosophy_facts
    
    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "philosophy_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    facts = get_philosophy_facts(limit=500)
    facts = [f for f in facts if f.get("weight", 0) >= min_weight]
    
    examples = []
    for fact in facts:
        key = fact.get("key", "")
        value = fact.get("l3_value") or fact.get("l2_value") or fact.get("l1_value", "")
        if not value:
            continue
        
        examples.append({
            "messages": [
                {"role": "system", "content": f"== STATE ==\nPhilosophy:\n- {key}: {fact.get('l1_value', '')}"},
                {"role": "user", "content": f"What's your perspective on {key.split('.')[-1].replace('_', ' ')}?"},
                {"role": "assistant", "content": f"Based on your philosophy: {value}"}
            ],
            "metadata": {"source": "philosophy", "key": key, "weight": fact.get("weight", 0.5)}
        })
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "facts_exported": len(facts),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable philosophy data."""
    from .schema import get_philosophy_facts
    facts = get_philosophy_facts(limit=500)
    return {"total_facts": len(facts), "exportable": len([f for f in facts if f.get("weight", 0) >= 0.3])}


# Add typing imports
from typing import Dict, Any, Optional
