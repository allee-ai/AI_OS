"""
Reflex Thread Training Data
===========================
Logs confident reflex decisions for fine-tuning.

Categories:
  - trigger: Reflex correctly fired
  - inhibit: Reflex correctly inhibited

Usage:
    from .train import log_decision
    
    log_decision(
        category="trigger",
        input_text="Check the weather",
        output_text="Executed weather reflex",
        confidence=0.95
    )
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "reflex_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a reflex decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "reflex",
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
    include_system: bool = True
) -> Dict[str, Any]:
    """
    Export reflex patterns to JSONL for finetuning.
    
    Training goal: Teach trigger recognition and instant responses.
    """
    from .schema import get_greetings, get_shortcuts, get_system_reflexes
    
    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "reflex_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []
    
    # Greetings
    for g in get_greetings(level=3):
        key = g.get("key", "")
        data = g.get("data", {})
        response = data.get("value", "") if isinstance(data, dict) else str(data)
        if response:
            examples.append({
                "messages": [
                    {"role": "system", "content": f"== STATE ==\nReflex: greeting '{key}'"},
                    {"role": "user", "content": key},
                    {"role": "assistant", "content": response}
                ],
                "metadata": {"source": "reflex", "type": "greeting"}
            })
    
    # Shortcuts
    for s in get_shortcuts(level=3):
        data = s.get("data", {})
        trigger = data.get("trigger", "") if isinstance(data, dict) else ""
        response = data.get("response", "") if isinstance(data, dict) else ""
        if trigger and response:
            examples.append({
                "messages": [
                    {"role": "system", "content": f"== STATE ==\nReflex: shortcut '{trigger}'"},
                    {"role": "user", "content": trigger},
                    {"role": "assistant", "content": response}
                ],
                "metadata": {"source": "reflex", "type": "shortcut"}
            })
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable reflex data."""
    from .schema import get_greetings, get_shortcuts, get_system_reflexes
    g = len(get_greetings(level=3))
    s = len(get_shortcuts(level=3))
    return {"greetings": g, "shortcuts": s, "total": g + s}


# Add typing imports
from typing import Dict, Any, Optional
