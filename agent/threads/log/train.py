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


# ─────────────────────────────────────────────────────────────
# Batch Export Functions  
# ─────────────────────────────────────────────────────────────

def export_training_data(
    output_path: Optional[Path] = None,
    include_multi_turn: bool = True,
    limit: int = 500
) -> Dict[str, Any]:
    """
    Export conversation history to JSONL for finetuning.
    
    Training goal: Teach conversation patterns and response style.
    """
    from contextlib import closing
    from data.db import get_connection
    
    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "log_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples = []
    
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ct.user_message, ct.assistant_message, c.session_id
            FROM convo_turns ct
            JOIN convos c ON ct.convo_id = c.id
            ORDER BY ct.created_at DESC
            LIMIT ?
        """, (limit,))
        
        for row in cur.fetchall():
            user_msg, assistant_msg, session_id = row
            if not user_msg or not assistant_msg or len(assistant_msg) < 20:
                continue
            
            examples.append({
                "messages": [
                    {"role": "system", "content": "== STATE ==\nConversation with persistent memory."},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_msg}
                ],
                "metadata": {"source": "log", "type": "conversation", "session_id": session_id}
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
    """Get stats about exportable conversation data."""
    from contextlib import closing
    from data.db import get_connection
    
    with closing(get_connection(readonly=True)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM convo_turns")
        total = cur.fetchone()[0]
    
    return {"total_turns": total, "exportable": total}


# Add typing imports
from typing import Dict, Any, Optional
