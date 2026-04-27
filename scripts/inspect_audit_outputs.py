"""Read the audit-rewrite outputs that the goal pipeline wrote to the
workspace virtual FS. Print path, size, original size (from disk),
first 60 lines, and a tail."""
from __future__ import annotations
import sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from workspace.schema import get_file  # type: ignore

TARGETS = [
    "docs/COMPARISON_FRAMEWORKS.md",
    "docs/BUSINESS_PLAN_REVISED.md",
    "docs/ARCHITECTURE.md",
    "docs/COMPARISON_SOAR.md",
    "CONTRIBUTING_REWRITE.md",
    "README.md",
    "docs/RESEARCH_PAPER.md",
    "docs/research2.md",
]

# Map workspace path -> on-disk original path (when comparable)
ORIGINAL = {
    "docs/COMPARISON_FRAMEWORKS.md": "docs/COMPARISON_FRAMEWORKS.md",
    "docs/BUSINESS_PLAN_REVISED.md": "docs/BUSINESS_PLAN.md",
    "docs/ARCHITECTURE.md": "docs/ARCHITECTURE.md",
    "docs/COMPARISON_SOAR.md": "docs/COMPARISON_SOAR.md",
    "CONTRIBUTING_REWRITE.md": "CONTRIBUTING.md",
    "README.md": "README.md",
    "docs/RESEARCH_PAPER.md": "docs/RESEARCH_PAPER.md",
    "docs/research2.md": "docs/research2.md",
}


def disk_size(rel: str) -> int:
    p = ROOT / rel
    return p.stat().st_size if p.exists() else 0


def main() -> None:
    for p in TARGETS:
        f = get_file(p)
        if not f:
            print(f"\n=== {p} :: NOT IN WORKSPACE DB ===")
            continue
        content = f.get("content")
        if isinstance(content, (bytes, bytearray)):
            try:
                text = content.decode("utf-8", errors="replace")
            except Exception:
                text = str(content)
        else:
            text = content or ""
        ws_size = len(text.encode("utf-8"))
        orig_rel = ORIGINAL.get(p, p)
        d_size = disk_size(orig_rel)
        print("\n" + "=" * 78)
        print(f"WORKSPACE FILE: {p}")
        print(f"  workspace bytes : {ws_size:,}")
        print(f"  original ({orig_rel}) on disk : {d_size:,}")
        if d_size:
            ratio = ws_size / d_size if d_size else 0.0
            print(f"  size ratio rewrite/original : {ratio:.2f}x")
        lines = text.splitlines()
        print(f"  total lines : {len(lines)}")
        print("-" * 78)
        head_n = min(60, len(lines))
        for i, ln in enumerate(lines[:head_n], 1):
            print(f"{i:>4}: {ln}")
        if len(lines) > head_n + 10:
            print(f"  ... ({len(lines) - head_n - 10} lines elided) ...")
            for i, ln in enumerate(lines[-10:], len(lines) - 9):
                print(f"{i:>4}: {ln}")


if __name__ == "__main__":
    main()
