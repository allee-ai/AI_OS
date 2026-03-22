"""
Finetune Section Builder
========================
Shared logic for generating self-knowledge training examples
from API endpoints, CLI commands, and schema definitions.

Each module's train.py calls these to build its "codebase" sections.
The model needs to KNOW these in its weights — STATE won't surface
"what endpoints exist" at inference time.
"""

import json
from typing import List, Dict, Any


def _build_state_for_module(module: str) -> str:
    """Build a realistic STATE block for self-knowledge examples."""
    try:
        from agent.subconscious.orchestrator import build_state
        return build_state(f"How does my {module} system work?")
    except Exception:
        return (
            f"== STATE ==\n"
            f"[self] My internal structure\n"
            f"  Threads: identity, philosophy, log, reflex, form, linking_core\n"
            f"  Modules: chat, workspace\n"
            f"[{module}] Active thread\n"
            f"  context_level: 2\n"
            f"== END STATE =="
        )


def build_api_examples(module: str, endpoints: List[tuple]) -> List[Dict[str, Any]]:
    """Build training examples from API endpoint definitions."""
    state = _build_state_for_module(module)
    examples = []

    # Full capability listing
    listing = "\n".join(f"  {m} {p} — {d}" for m, p, d in endpoints)
    examples.append({
        "messages": [
            {"role": "system", "content": state},
            {"role": "user", "content": f"What API endpoints does {module} have?"},
            {"role": "assistant", "content": f"My {module} thread exposes these endpoints:\n{listing}"},
        ],
        "metadata": {"source": module, "section": "api", "type": "listing"},
    })

    # Per-endpoint examples — varied question styles
    question_templates = [
        "How do I {desc}?",
        "What's the endpoint for {desc_short}?",
        "I need to {desc}, how?",
    ]
    for i, (method, path, desc) in enumerate(endpoints):
        desc_lower = desc.lower().rstrip('.')
        template = question_templates[i % len(question_templates)]
        question = template.format(desc=desc_lower, desc_short=desc_lower.split()[0:3])
        examples.append({
            "messages": [
                {"role": "system", "content": state},
                {"role": "user", "content": question},
                {"role": "assistant", "content": f"{method} {path} — {desc}. That's part of my {module} thread."},
            ],
            "metadata": {"source": module, "section": "api", "type": "endpoint"},
        })

    return examples


def build_cli_examples(module: str, commands: List[tuple]) -> List[Dict[str, Any]]:
    """Build training examples from CLI command definitions."""
    state = _build_state_for_module(module)
    examples = []

    listing = "\n".join(f"  {cmd} — {desc}" for cmd, desc in commands)
    examples.append({
        "messages": [
            {"role": "system", "content": state},
            {"role": "user", "content": f"What commands do you have for {module}?"},
            {"role": "assistant", "content": f"My {module} CLI commands:\n{listing}"},
        ],
        "metadata": {"source": module, "section": "cli", "type": "listing"},
    })

    for cmd, desc in commands:
        examples.append({
            "messages": [
                {"role": "system", "content": state},
                {"role": "user", "content": f"How do I {desc.lower().rstrip('.')}?"},
                {"role": "assistant", "content": f"Run: {cmd}"},
            ],
            "metadata": {"source": module, "section": "cli", "type": "command"},
        })

    return examples


def build_schema_examples(module: str, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build training examples from schema/table definitions."""
    state = _build_state_for_module(module)
    examples = []

    for tbl in tables:
        name = tbl["name"]
        cols = tbl.get("columns", "")
        desc = tbl.get("description", "")
        examples.append({
            "messages": [
                {"role": "system", "content": state},
                {"role": "user", "content": f"What does {name} store?"},
                {"role": "assistant", "content": f"My {name} table stores {desc}. Columns: {cols}"},
            ],
            "metadata": {"source": module, "section": "schema", "type": "table"},
        })

    return examples
