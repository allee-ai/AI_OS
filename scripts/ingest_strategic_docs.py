"""Ingest strategic docs into the workspace virtual FS so they surface in STATE.

The workspace adapter shows whatever lives in workspace_files. Right now
that's 6 toy files. This script adds the actual planning docs so the
running agent (and the autopilot context) can reason about the business
plan, roadmap, research paper, and architecture.

Run: .venv/bin/python scripts/ingest_strategic_docs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from workspace.schema import create_file, init_workspace_tables, ensure_folder
from workspace.api import index_file as _api_index  # noqa: F401  (used reference)
# create_file marks indexed=0; we re-chunk via the schema function directly:
from contextlib import closing
from data.db import get_connection


# Mapping: source path on disk → virtual path inside workspace
STRATEGIC = {
    REPO / "docs" / "BUSINESS_PLAN.md":   "/strategy/BUSINESS_PLAN.md",
    REPO / "docs" / "ROADMAP.md":         "/strategy/ROADMAP.md",
    REPO / "docs" / "RESEARCH_PAPER.md":  "/strategy/RESEARCH_PAPER.md",
    REPO / "docs" / "ARCHITECTURE.md":    "/strategy/ARCHITECTURE.md",
    REPO / "docs" / "ASSESSMENT.md":      "/strategy/ASSESSMENT.md",
    REPO / "docs" / "AUTONOMY_ASSESSMENT.md": "/strategy/AUTONOMY_ASSESSMENT.md",
    REPO / "research" / "papers" / "substrate_invariant" / "paper.md":
        "/strategy/substrate_invariant_paper.md",
    REPO / "research" / "papers" / "substrate_invariant" / "outreach" / "hn_show.md":
        "/strategy/outreach_hn.md",
    REPO / "research" / "papers" / "substrate_invariant" / "outreach" / "lesswrong.md":
        "/strategy/outreach_lesswrong.md",
}


def chunk_after_create(virtual_path: str) -> int:
    """Chunk the file we just created so workspace_chunks fills."""
    from workspace.schema import get_file
    f = get_file(virtual_path)
    if not f:
        return 0
    try:
        from workspace.schema import chunk_file
    except ImportError:
        # chunk_file might live elsewhere
        return 0
    try:
        return chunk_file(f["id"])
    except Exception:
        return 0


def main() -> None:
    init_workspace_tables()
    ensure_folder("/strategy")

    written = 0
    skipped = 0
    for src, vpath in STRATEGIC.items():
        if not src.exists():
            print(f"  ! missing: {src.relative_to(REPO)}")
            skipped += 1
            continue
        content = src.read_bytes()
        meta = {
            "source_path": str(src.relative_to(REPO)),
            "category": "strategy",
            "ingested_by": "ingest_strategic_docs.py",
        }
        info = create_file(vpath, content, mime_type="text/markdown", metadata=meta)
        n_chunks = chunk_after_create(vpath)
        print(f"  ingested {vpath}  ({info['size']:>7,}b, {n_chunks} chunks)  ← {src.relative_to(REPO)}")
        written += 1

    # Verify what's now in workspace
    with closing(get_connection(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT path, size FROM workspace_files WHERE is_folder=0 ORDER BY path"
        ).fetchall()
    print()
    print(f"  total files in workspace: {len(rows)}")
    for r in rows:
        print(f"    {r['path']:<50} {r['size']:>10,}b")
    print()
    print(f"  ingested: {written}  skipped: {skipped}")
    print()
    print("  next: re-run scripts/turn_start.py — workspace should now")
    print("        surface BUSINESS_PLAN, ROADMAP, paper, etc. in STATE.")


if __name__ == "__main__":
    main()
