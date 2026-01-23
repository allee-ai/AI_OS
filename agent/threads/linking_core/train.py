"""
Linking Core Training Data
==========================
Logs confident activation patterns for fine-tuning.

Categories:
  - activation: Spread activation found relevant concepts
  - cooccurrence: Concept co-occurrence strengthened

Usage:
    from .train import log_decision
    
    log_decision(
        category="activation",
        input_text="Did Sarah mention coffee?",
        output_text="Activated: sarah, coffee, mentioned",
        confidence=0.85,
        activated_concepts=["sarah", "coffee"]
    )
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "linking_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7


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
