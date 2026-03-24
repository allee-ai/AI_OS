"""
Workspace Q&A Training Generator
=================================
Deterministic loop — NO LLM calls.

Reads workspace files + summaries from the DB and generates
Q&A training pairs that teach the fine-tuned model to answer:
  - "Where is {filename}?"  → file path
  - "What is {filename}?"   → stored summary
  - "What files are in {directory}?" → listing

Also generates pairs from identity facts, reflex triggers, and
feed sources — any structured data that has a known answer.

Output: finetune/generated/workspace_qa.jsonl
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from .base import BackgroundLoop, LoopConfig

GENERATED_DIR = Path(__file__).parents[3] / "finetune" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = GENERATED_DIR / "workspace_qa.jsonl"

# Run every 30 minutes (cheap — no LLM calls)
DEFAULT_INTERVAL = float(os.getenv("AIOS_WORKSPACE_QA_INTERVAL", "1800"))


def _build_state_stub() -> str:
    """Minimal STATE stub for the system message."""
    return "== STATE ==\nModule: workspace\nContext: file lookup"


def _generate_workspace_pairs() -> List[Dict[str, Any]]:
    """Generate Q&A pairs from workspace_files table."""
    from data.db import get_connection
    from contextlib import closing

    examples = []
    state = _build_state_stub()

    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT path, name, is_folder, summary, size FROM workspace_files ORDER BY path"
        ).fetchall()

    if not rows:
        return examples

    files = [dict(r) for r in rows]

    # Build directory tree
    dirs: Dict[str, List[str]] = {}
    for f in files:
        parent = "/".join(f["path"].rsplit("/", 1)[:-1]) or "/"
        if parent not in dirs:
            dirs[parent] = []
        dirs[parent].append(f["name"])

    for f in files:
        if f["is_folder"]:
            continue

        name = f["name"]
        path = f["path"]

        # "Where is X?"
        examples.append({
            "messages": [
                {"role": "system", "content": state},
                {"role": "user", "content": f"Where is {name}?"},
                {"role": "assistant", "content": f"{name} is at {path}"},
            ],
            "metadata": {"source": "workspace_qa", "type": "location", "path": path},
        })

        # "What is X?" — only if we have a summary
        if f.get("summary"):
            examples.append({
                "messages": [
                    {"role": "system", "content": state},
                    {"role": "user", "content": f"What is {name}?"},
                    {"role": "assistant", "content": f.get("summary")},
                ],
                "metadata": {"source": "workspace_qa", "type": "summary", "path": path},
            })

    # "What files are in {dir}?"
    for dir_path, children in dirs.items():
        if len(children) < 2:
            continue
        listing = ", ".join(sorted(children))
        label = dir_path if dir_path != "/" else "the root"
        examples.append({
            "messages": [
                {"role": "system", "content": state},
                {"role": "user", "content": f"What files are in {label}?"},
                {"role": "assistant", "content": f"Files in {label}: {listing}"},
            ],
            "metadata": {"source": "workspace_qa", "type": "listing", "dir": dir_path},
        })

    return examples


def _generate_identity_pairs() -> List[Dict[str, Any]]:
    """Generate Q&A pairs from identity facts."""
    from data.db import get_connection
    from contextlib import closing

    examples = []
    state = "== STATE ==\nModule: identity\nContext: fact lookup"

    with closing(get_connection(readonly=True)) as conn:
        try:
            rows = conn.execute(
                "SELECT profile_id, key, l1_value FROM identity_facts WHERE l1_value IS NOT NULL AND l1_value != ''"
            ).fetchall()
        except Exception:
            return examples

    for r in rows:
        profile = r["profile_id"]
        key = r["key"]
        val = r["l1_value"]
        if profile == "primary_user":
            examples.append({
                "messages": [
                    {"role": "system", "content": state},
                    {"role": "user", "content": f"What is my {key}?"},
                    {"role": "assistant", "content": str(val)},
                ],
                "metadata": {"source": "workspace_qa", "type": "identity_fact", "profile": profile, "key": key},
            })
        else:
            examples.append({
                "messages": [
                    {"role": "system", "content": state},
                    {"role": "user", "content": f"What is {profile}'s {key}?"},
                    {"role": "assistant", "content": str(val)},
                ],
                "metadata": {"source": "workspace_qa", "type": "identity_fact", "profile": profile, "key": key},
            })

    return examples


def _generate_feed_pairs() -> List[Dict[str, Any]]:
    """Generate Q&A pairs from feed sources."""
    from data.db import get_connection
    from contextlib import closing

    examples = []
    state = "== STATE ==\nModule: feeds\nContext: source lookup"

    with closing(get_connection(readonly=True)) as conn:
        try:
            rows = conn.execute(
                "SELECT name, source_type, url, enabled FROM feed_sources"
            ).fetchall()
        except Exception:
            return examples

    if not rows:
        return examples

    sources = [dict(r) for r in rows]
    names = [s["name"] for s in sources if s.get("enabled")]

    if names:
        examples.append({
            "messages": [
                {"role": "system", "content": state},
                {"role": "user", "content": "What feeds am I subscribed to?"},
                {"role": "assistant", "content": f"You have {len(names)} active feeds: {', '.join(names)}"},
            ],
            "metadata": {"source": "workspace_qa", "type": "feed_listing"},
        })

    return examples


def run_workspace_qa() -> Dict[str, Any]:
    """Generate all deterministic Q&A pairs and write to JSONL."""
    all_pairs = []
    all_pairs.extend(_generate_workspace_pairs())
    all_pairs.extend(_generate_identity_pairs())
    all_pairs.extend(_generate_feed_pairs())

    if all_pairs:
        with open(OUTPUT_FILE, "w") as f:
            for pair in all_pairs:
                f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    return {
        "total": len(all_pairs),
        "workspace": len([p for p in all_pairs if p["metadata"]["type"] in ("location", "summary", "listing")]),
        "identity": len([p for p in all_pairs if p["metadata"]["type"] == "identity_fact"]),
        "feeds": len([p for p in all_pairs if p["metadata"]["type"] == "feed_listing"]),
        "output": str(OUTPUT_FILE),
    }


class WorkspaceQALoop(BackgroundLoop):
    """
    Deterministic training pair generator — no LLM calls.
    Reads structured data from DB and generates Q&A JSONL.
    """

    def __init__(self, interval: float = DEFAULT_INTERVAL, enabled: bool = True):
        config = LoopConfig(
            name="workspace_qa",
            interval_seconds=interval,
            enabled=enabled,
        )
        super().__init__(config=config, task=self._run)

    def _run(self) -> str:
        result = run_workspace_qa()
        summary = (f"Generated {result['total']} training pairs "
                   f"(workspace:{result['workspace']} identity:{result['identity']} feeds:{result['feeds']})")
        print(f"[workspace_qa] {summary}")
        return summary
