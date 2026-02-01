"""
Linking Core Training Data Exporter
====================================
Logs confident activation patterns AND exports LONG links for fine-tuning.

Live logging (during conversation):
    log_decision() — Records high-confidence decisions

Batch export (for finetune):
    export_training_data() — Exports consolidated LONG links to JSONL
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

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


# ─────────────────────────────────────────────────────────────
# Batch Export Functions
# ─────────────────────────────────────────────────────────────

def export_training_data(
    output_path: Optional[Path] = None,
    include_spread: bool = True,
    min_strength: float = 0.5,
    min_fire_count: int = 3
) -> Dict[str, Any]:
    """
    Export LONG-potentiated concept links to JSONL for finetuning.
    
    Training goal: Teach the model associative recall.
    """
    from .schema import get_long_links, get_potentiation_stats, spread_activate
    
    if output_path is None:
        output_path = Path(__file__).parents[3] / "finetune" / "linking_core_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get consolidated links
    links = get_long_links(limit=1000)
    links = [l for l in links 
             if l["strength"] >= min_strength and l["fire_count"] >= min_fire_count]
    
    examples = []
    
    # Generate association examples
    for link in links:
        concept_a = link["concept_a"]
        concept_b = link["concept_b"]
        strength = link["strength"]
        fire_count = link["fire_count"]
        
        # Bidirectional examples
        for primary, related in [(concept_a, concept_b), (concept_b, concept_a)]:
            examples.append({
                "messages": [
                    {"role": "system", "content": f"== STATE ==\nAssociations: {primary} ↔ {related} (strength: {strength:.2f})"},
                    {"role": "user", "content": f"What do you associate with {primary}?"},
                    {"role": "assistant", "content": f"When {primary} comes up, I also think of {related}. They've been connected {fire_count} times."}
                ],
                "metadata": {"source": "linking_core", "type": "association", "strength": strength}
            })
    
    # Add spread activation examples
    if include_spread and links:
        seeds = list(set([l["concept_a"] for l in links[:30]]))[:10]
        for seed in seeds:
            activated = spread_activate([seed], activation_threshold=0.3, max_hops=2, limit=5)
            if activated:
                chain = ", ".join([a['concept'] for a in activated])
                examples.append({
                    "messages": [
                        {"role": "system", "content": f"== STATE ==\nSpread activation from '{seed}'"},
                        {"role": "user", "content": f"What comes to mind when you think about {seed}?"},
                        {"role": "assistant", "content": f"Thinking about {seed} brings up: {chain}."}
                    ],
                    "metadata": {"source": "linking_core", "type": "spread_activation", "seed": seed}
                })
    
    # Write JSONL
    with open(output_path, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "links_exported": len(links),
        "stats": get_potentiation_stats(),
        "exported_at": datetime.now(timezone.utc).isoformat()
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable linking data."""
    from .schema import get_long_links, get_potentiation_stats
    
    links = get_long_links(limit=1000)
    stats = get_potentiation_stats()
    exportable = len([l for l in links if l["strength"] >= 0.5 and l["fire_count"] >= 3])
    
    return {
        "long_links": len(links),
        "potentiation": stats,
        "exportable": exportable
    }

