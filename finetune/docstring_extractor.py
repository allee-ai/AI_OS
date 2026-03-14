"""
Docstring Extractor — walks Python AST to harvest docstrings and
routes them to the correct training section based on source file type.

Routing rules:
    api.py      → "api"
    schema.py   → "schema"
    cli.py      → "cli"
    train.py    → "data"
    README.md   → "data"
    *other*.py  → "data"
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Module → source directory mapping ────────────────────────────────────

MODULE_DIRS: Dict[str, str] = {
    "linking_core": "agent/threads/linking_core",
    "identity":     "agent/threads/identity",
    "philosophy":   "agent/threads/philosophy",
    "log":          "agent/threads/log",
    "reflex":       "agent/threads/reflex",
    "form":         "agent/threads/form",
    "chat":         "chat",
    "docs":         "docs",
}

ROOT = Path(__file__).resolve().parent.parent  # repo root

# ── File-name → section routing ─────────────────────────────────────────

def _file_to_section(filename: str) -> str:
    """Determine the training section from the Python file name."""
    base = os.path.basename(filename).lower()
    if base == "api.py":
        return "api"
    if base == "schema.py":
        return "schema"
    if base == "cli.py":
        return "cli"
    return "data"

# ── AST extraction ──────────────────────────────────────────────────────

def _extract_docstrings(filepath: Path) -> List[Tuple[str, str, str]]:
    """
    Extract (qualified_name, docstring, kind) triples from a Python file.
    kind ∈ {"module", "class", "function"}
    """
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    results: List[Tuple[str, str, str]] = []

    # Module docstring
    mod_doc = ast.get_docstring(tree)
    if mod_doc:
        results.append((filepath.stem, mod_doc.strip(), "module"))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc and len(doc.strip()) > 15:
                results.append((node.name, doc.strip(), "function"))
        elif isinstance(node, ast.ClassDef):
            doc = ast.get_docstring(node)
            if doc and len(doc.strip()) > 15:
                results.append((node.name, doc.strip(), "class"))

    return results


def _extract_readme(readme_path: Path) -> Optional[str]:
    """Read first ~500 chars of a README for module-level context."""
    if not readme_path.exists():
        return None
    text = readme_path.read_text(encoding="utf-8").strip()
    return text[:2000] if text else None

# ── Training-pair generation ────────────────────────────────────────────

SYSTEM_PROMPT = "You are Nola, the AI of a Cognitive Operating System. Answer using specific implementation details from your own codebase."


def _make_pair(module: str, name: str, docstring: str, kind: str, section: str, filepath: str) -> dict:
    """Build a single training example from a docstring."""
    if kind == "module":
        user_q = f"What is the purpose of the {module} {section} module?"
        assistant_a = docstring
    elif kind == "class":
        user_q = f"What does the {name} class do in {module}?"
        assistant_a = docstring
    else:
        user_q = f"What does {name}() do in {module}'s {section} layer?"
        assistant_a = docstring

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_q},
            {"role": "assistant", "content": assistant_a},
        ],
        "metadata": {
            "source": module,
            "section": section,
            "type": "docstring",
            "kind": kind,
            "symbol": name,
            "file": filepath,
        },
    }


def _content_hash(pair: dict) -> str:
    """Stable hash of the user+assistant text."""
    text = pair["messages"][1]["content"] + "|" + pair["messages"][2]["content"]
    return hashlib.sha256(text.encode()).hexdigest()[:16]

# ── Dedup index ─────────────────────────────────────────────────────────

DEDUP_PATH = ROOT / "finetune" / "docstring_hashes.json"


def _load_dedup_index() -> set:
    if DEDUP_PATH.exists():
        try:
            return set(json.loads(DEDUP_PATH.read_text()))
        except Exception:
            return set()
    return set()


def _save_dedup_index(hashes: set) -> None:
    DEDUP_PATH.write_text(json.dumps(sorted(hashes), indent=2))

# ── Public API ──────────────────────────────────────────────────────────

def extract_module(module: str) -> List[dict]:
    """Extract all docstring training pairs for a single module."""
    dir_rel = MODULE_DIRS.get(module)
    if not dir_rel:
        return []

    mod_dir = ROOT / dir_rel
    if not mod_dir.is_dir():
        return []

    pairs: List[dict] = []

    # Walk all .py files in module directory
    for py_file in sorted(mod_dir.rglob("*.py")):
        if py_file.name.startswith("__") and py_file.name != "__init__.py":
            continue
        section = _file_to_section(py_file.name)
        rel = str(py_file.relative_to(ROOT))

        for name, doc, kind in _extract_docstrings(py_file):
            pairs.append(_make_pair(module, name, doc, kind, section, rel))

    # Try README
    readme = mod_dir / "README.md"
    content = _extract_readme(readme)
    if content:
        pairs.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Give me an overview of the {module} module."},
                {"role": "assistant", "content": content},
            ],
            "metadata": {
                "source": module,
                "section": "data",
                "type": "docstring",
                "kind": "readme",
                "symbol": "README",
                "file": str(readme.relative_to(ROOT)),
            },
        })

    return pairs


def extract_all(deduplicate: bool = True) -> Dict[str, List[dict]]:
    """
    Extract docstring training pairs for all modules.
    Returns {module: [pairs]}.  Skips already-seen pairs when deduplicate=True.
    """
    seen = _load_dedup_index() if deduplicate else set()
    result: Dict[str, List[dict]] = {}

    for module in MODULE_DIRS:
        raw = extract_module(module)
        unique: List[dict] = []
        for p in raw:
            h = _content_hash(p)
            if h not in seen:
                seen.add(h)
                unique.append(p)
        result[module] = unique

    if deduplicate:
        _save_dedup_index(seen)

    return result


def extract_and_save(deduplicate: bool = True) -> Dict[str, int]:
    """
    Extract docstrings and append to each module's generated JSONL.
    Returns {module: new_count}.
    """
    output_dir = ROOT / "finetune" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    data = extract_all(deduplicate=deduplicate)
    counts: Dict[str, int] = {}

    for module, pairs in data.items():
        if not pairs:
            counts[module] = 0
            continue
        out = output_dir / f"{module}.jsonl"
        with open(out, "a", encoding="utf-8") as f:
            for p in pairs:
                f.write(json.dumps(p) + "\n")
        counts[module] = len(pairs)

    return counts


def get_stats() -> Dict[str, int]:
    """Get count of extractable docstrings per module (no dedup)."""
    return {mod: len(extract_module(mod)) for mod in MODULE_DIRS}


# ── CLI entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--save" in sys.argv:
        counts = extract_and_save(deduplicate="--no-dedup" not in sys.argv)
        total = sum(counts.values())
        print(f"Saved {total} new docstring pairs:")
        for m, c in sorted(counts.items()):
            if c > 0:
                print(f"  {m}: {c}")
    else:
        stats = get_stats()
        total = sum(stats.values())
        print(f"Extractable docstring pairs ({total} total):")
        for m, c in sorted(stats.items()):
            print(f"  {m}: {c}")
