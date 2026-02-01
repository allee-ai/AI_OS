"""
Form Thread Training Data
=========================
Logs confident capability decisions for fine-tuning.

Categories:
  - capability: Used capability appropriately
  - limitation: Correctly identified limitation

Usage:
    from .train import log_decision
    
    log_decision(
        category="capability",
        input_text="Can you search the web?",
        output_text="Yes, I can browse with my Kernel body.",
        confidence=0.9
    )
"""

import json
from datetime import datetime, timezone
from pathlib import Path

TRAINING_DIR = Path(__file__).parents[3] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = TRAINING_DIR / "form_decisions.jsonl"

CONFIDENCE_THRESHOLD = 0.7


def log_decision(
    category: str,
    input_text: str,
    output_text: str,
    confidence: float = 1.0,
    **context
) -> bool:
    """Log a form decision if confidence exceeds threshold."""
    if confidence < CONFIDENCE_THRESHOLD:
        return False
    
    record = {
        "thread": "form",
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
    output_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Export tool usage patterns to JSONL for finetuning.
    
    Training goal: Teach when and how to use available tools.
    """
    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "form_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []
    
    # Get registered tools if available
    try:
        from .tools.registry import get_registered_tools
        tools = get_registered_tools()
        
        for tool in tools:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            if name and desc:
                examples.append({
                    "messages": [
                        {"role": "system", "content": f"== STATE ==\nTool available: {name}"},
                        {"role": "user", "content": f"When should I use the {name} tool?"},
                        {"role": "assistant", "content": f"The {name} tool is used for: {desc}"}
                    ],
                    "metadata": {"source": "form", "type": "tool_description", "tool": name}
                })
    except ImportError:
        pass
    
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable form data."""
    try:
        from .tools.registry import get_registered_tools
        tools = get_registered_tools()
        return {"tools": len(tools), "exportable": len(tools)}
    except ImportError:
        return {"tools": 0, "exportable": 0}


# Add typing imports
from typing import Dict, Any, Optional
