"""Ingest research/ artifacts into the workspace virtual FS so they surface in STATE.

Goal #12: research/ work artifacts (hebbian graph stats, vocab, sae probe outputs,
substrate-invariant paper material) currently live on disk but the agent's
workspace adapter only sees files in workspace_files. This script publishes the
small textual artifacts into workspace_files at /research/* paths, closing the
flywheel so STATE includes them next turn.

Skip rules:
- Skip binaries (.npy, .npz, .tar.gz, .pdf).
- Skip files larger than MAX_BYTES (default 30KB) — keeps STATE focused.
- Skip .DS_Store, __pycache__, dotfiles.

Idempotent: create_file() upserts on path conflict, so re-running just refreshes.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data.db import set_demo_mode  # noqa: E402
from workspace.schema import create_file, init_workspace_tables  # noqa: E402

MAX_BYTES = 30_000
TEXT_EXTS = {".md", ".py", ".json", ".txt", ".yaml", ".yml", ".toml", ".cfg"}
SKIP_DIRS = {"__pycache__", ".ipynb_checkpoints", "node_modules"}


def iter_research_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size == 0 or size > MAX_BYTES:
            continue
        yield path, size


def main() -> int:
    set_demo_mode(False)
    init_workspace_tables()

    research_root = REPO / "research"
    if not research_root.exists():
        print(f"[error] {research_root} does not exist", file=sys.stderr)
        return 1

    print(f"=== ingesting research/* into workspace_files (max {MAX_BYTES}B) ===\n")
    written = 0
    skipped_big = 0
    skipped_other = 0

    for path in research_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            skipped_other += 1
            continue
        try:
            size = path.stat().st_size
        except OSError:
            skipped_other += 1
            continue
        if size == 0:
            skipped_other += 1
            continue
        if size > MAX_BYTES:
            skipped_big += 1
            print(f"  skip (too big {size}B): {path.relative_to(REPO)}")
            continue

        rel = path.relative_to(REPO)  # e.g. research/hebbian_attention/_check_topology.py
        ws_path = "/" + str(rel)       # /research/...
        try:
            content = path.read_bytes()
        except OSError as exc:
            print(f"  skip (read error {exc}): {rel}")
            continue

        create_file(
            path=ws_path,
            content=content,
            metadata={"origin": "research_ingest", "source_disk": str(rel)},
        )
        print(f"  + {ws_path} ({size}B)")
        written += 1

    print(f"\n=== done: wrote {written}, skipped {skipped_big} too-big, "
          f"{skipped_other} non-text ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
