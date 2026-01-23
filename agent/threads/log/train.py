"""
Log Thread Training Data
========================
Logs confident memory decisions for fine-tuning.

Categories:
  - recall: Retrieved relevant memory
  - record: Recorded significant event

Usage:
    from .train import log_decision
    
    log_decision(
        category="recall",
        input_text="What did we talk about yesterday?",
        output_text="Yesterday you mentioned the project deadline.",
        confidence=0.9
    )
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "log_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a memory decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "log",
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
