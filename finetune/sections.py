"""
Finetune Section Builder
========================
Shared logic for generating self-knowledge training examples
from API endpoints, CLI commands, and schema definitions.

Each module's train.py calls these to build its "codebase" sections.
"""

import json
from typing import List, Dict, Any


def build_api_examples(module: str, endpoints: List[tuple]) -> List[Dict[str, Any]]:
    """
    Build training examples from API endpoint definitions.

    Args:
        module: Module name (e.g. "identity")
        endpoints: [(METHOD, PATH, DESCRIPTION), ...]

    Returns:
        List of JSONL-ready training dicts.
    """
    examples = []
    # Full capability listing
    listing = "\n".join(f"  {m} {p} — {d}" for m, p, d in endpoints)
    examples.append({
        "messages": [
            {"role": "system", "content": f"== STATE ==\nModule: {module}"},
            {"role": "user", "content": f"What API endpoints does the {module} module have?"},
            {"role": "assistant", "content": f"The {module} module exposes these endpoints:\n{listing}"},
        ],
        "metadata": {"source": module, "section": "api", "type": "listing"},
    })

    # Per-endpoint examples
    for method, path, desc in endpoints:
        examples.append({
            "messages": [
                {"role": "system", "content": f"== STATE ==\nModule: {module}"},
                {"role": "user", "content": f"How do I {desc.lower().rstrip('.')}?"},
                {"role": "assistant", "content": f"Use {method} {path} — {desc}"},
            ],
            "metadata": {"source": module, "section": "api", "type": "endpoint"},
        })

    return examples


def build_cli_examples(module: str, commands: List[tuple]) -> List[Dict[str, Any]]:
    """
    Build training examples from CLI command definitions.

    Args:
        module: Module name
        commands: [("/command args", "description"), ...]
    """
    examples = []
    listing = "\n".join(f"  {cmd} — {desc}" for cmd, desc in commands)
    examples.append({
        "messages": [
            {"role": "system", "content": f"== STATE ==\nModule: {module}"},
            {"role": "user", "content": f"What CLI commands does {module} have?"},
            {"role": "assistant", "content": f"Available commands:\n{listing}"},
        ],
        "metadata": {"source": module, "section": "cli", "type": "listing"},
    })

    for cmd, desc in commands:
        examples.append({
            "messages": [
                {"role": "system", "content": f"== STATE ==\nModule: {module}"},
                {"role": "user", "content": f"How do I {desc.lower().rstrip('.')} from the CLI?"},
                {"role": "assistant", "content": f"Run: {cmd}"},
            ],
            "metadata": {"source": module, "section": "cli", "type": "command"},
        })

    return examples


def build_schema_examples(module: str, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build training examples from schema/table definitions.

    Args:
        module: Module name
        tables: [{"name": "table_name", "columns": "col1, col2, ...", "description": "..."}, ...]
    """
    examples = []
    for tbl in tables:
        name = tbl["name"]
        cols = tbl.get("columns", "")
        desc = tbl.get("description", "")
        examples.append({
            "messages": [
                {"role": "system", "content": f"== STATE ==\nModule: {module}"},
                {"role": "user", "content": f"What data does the {name} table store?"},
                {"role": "assistant", "content": f"The {name} table stores {desc}. Columns: {cols}"},
            ],
            "metadata": {"source": module, "section": "schema", "type": "table"},
        })

    return examples
