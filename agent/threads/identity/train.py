"""
Identity Thread Training Data
=============================
Logs confident identity decisions for fine-tuning.

Categories:
  - retrieval: Correctly retrieved identity fact
  - boundary: Maintained identity under pressure
  - update: Identified new identity fact

Usage:
    from .train import log_decision
    
    log_decision(
        category="retrieval",
        input_text="What's my name?",
        output_text="Your name is Jordan.",
        confidence=0.95
    )
"""

import json
from datetime import datetime, timezone
from pathlib import Path

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
