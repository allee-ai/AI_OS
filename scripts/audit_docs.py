"""Doc/STATE audit — surface overlap, drift, and disconnection.

The premise: AI_OS now has dozens of strategy/research/architecture docs
scattered across docs/, research/papers/, _archive/, and root. With STATE
as the source of truth, any doc that doesn't show up in STATE — or that
is mostly redundant with a fresher sibling — is dead weight.

This script walks every .md doc, runs each through linking_core's
entity extraction (the same concept-resolver that builds STATE), and
reports:

  - per-doc: bytes, mtime age, concept count, top-overlap siblings
  - rework candidates: stale, redundant, or disconnected docs
  - optional: writes one proposed_goal per rework candidate so the
    audit feeds the live goals.open queue

This is the doc-side companion to STATE itself — same query pipeline,
applied to authored content instead of runtime state.

Usage:
    .venv/bin/python scripts/audit_docs.py                    # report only
    .venv/bin/python scripts/audit_docs.py --propose-goals    # + write goals
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Make repo root importable so we can use linking_core / loops.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ── Doc set ───────────────────────────────────────────────────────────

# Roots scanned for audit. _archive/ included on purpose: archived docs
# are the most likely to be redundant with current ones.
DOC_ROOTS = [
    ROOT / "docs",
    ROOT / "research",
    ROOT / "_archive",
]

# Top-level files that look like load-bearing docs.
ROOT_DOCS = [
    "README.md",
    "ROADMAP.md" if (ROOT / "ROADMAP.md").exists() else None,
    "ARCHITECTURE.md" if (ROOT / "ARCHITECTURE.md").exists() else None,
    "BUSINESS_PLAN.md" if (ROOT / "BUSINESS_PLAN.md").exists() else None,
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md" if (ROOT / "CHANGELOG.md").exists() else None,
]


def collect_docs() -> List[Path]:
    docs: List[Path] = []
    for name in ROOT_DOCS:
        if not name:
            continue
        p = ROOT / name
        if p.exists():
            docs.append(p)
    for root in DOC_ROOTS:
        if not root.exists():
            continue
        for p in root.rglob("*.md"):
            # Skip git internals, node_modules, anything weird
            if any(part.startswith(".") for part in p.parts):
                continue
            docs.append(p)
    return sorted(set(docs))


# ── Per-doc analysis ──────────────────────────────────────────────────

def analyze_doc(path: Path, extract_fn) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    bytes_ = len(text.encode("utf-8"))
    mtime = path.stat().st_mtime
    age_days = (time.time() - mtime) / 86400.0

    # Concepts that this doc connects to in the live system.
    try:
        concepts = sorted(set(extract_fn(text)))
    except Exception as e:
        concepts = []
        print(f"  [warn] concept-extract failed for {path}: {e}", file=sys.stderr)

    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": bytes_,
        "mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        "age_days": round(age_days, 1),
        "concept_count": len(concepts),
        "concepts": concepts,
    }


def jaccard(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb)


# ── Rework heuristics ─────────────────────────────────────────────────

# Anything matching at least one of these is flagged for review.
STALE_AGE_DAYS = 60        # not touched in 2 months
HIGH_OVERLAP   = 0.70      # >70% concept Jaccard with another doc
TINY_BYTES     = 800       # under ~800 bytes is probably a stub
DISCONNECTED   = 3         # fewer than this many concepts → not in STATE


def is_archived(path: str) -> bool:
    """Archive paths are intentionally cold — staleness alone isn't actionable."""
    return path.startswith("_archive/") or "/_archive/" in path


def find_rework_candidates(docs: List[Dict[str, object]]) -> List[Dict[str, object]]:
    out: List[Dict[str, object]] = []
    for i, d in enumerate(docs):
        reasons: List[str] = []
        archived = is_archived(str(d["path"]))

        # Stale only matters for live docs. Archive docs are cold by design.
        if not archived and d["age_days"] > STALE_AGE_DAYS:
            reasons.append(f"stale ({d['age_days']:.0f}d old)")

        if d["bytes"] < TINY_BYTES:
            reasons.append(f"tiny ({d['bytes']}B — stub?)")

        if d["concept_count"] < DISCONNECTED:
            reasons.append(
                f"disconnected ({d['concept_count']} known concepts — "
                "doesn't connect to STATE)"
            )

        # Find the most-overlapping sibling. Only flag if newer (the older
        # version is the redundant one).
        best_overlap = 0.0
        best_sibling = ""
        for j, other in enumerate(docs):
            if i == j:
                continue
            score = jaccard(d["concepts"], other["concepts"])
            if score > best_overlap:
                best_overlap = score
                best_sibling = other["path"]
                best_sibling_age = other["age_days"]
        if best_overlap >= HIGH_OVERLAP and best_sibling:
            # Only flag the older twin as the rework candidate
            if d["age_days"] > best_sibling_age:  # type: ignore[has-type]
                reasons.append(
                    f"redundant ({best_overlap:.0%} concept overlap with "
                    f"newer {best_sibling})"
                )

        if reasons:
            out.append({
                **d,
                "archived": archived,
                "reasons": reasons,
                "top_overlap": best_overlap,
                "top_sibling": best_sibling,
            })
    return out


# ── Report ────────────────────────────────────────────────────────────

def render_markdown(docs: List[Dict[str, object]],
                    rework: List[Dict[str, object]]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines: List[str] = []
    lines.append(f"# Doc audit — {now}")
    lines.append("")
    lines.append(f"Scanned **{len(docs)}** docs across "
                 f"{', '.join(str(r.relative_to(ROOT)) for r in DOC_ROOTS if r.exists())}, "
                 f"plus root-level load-bearing docs.")
    lines.append("")

    live_rework    = [d for d in rework if not d.get("archived")]
    archive_notes  = [d for d in rework if d.get("archived")]

    lines.append(f"Rework candidates: **{len(live_rework)}** live docs "
                 f"(plus {len(archive_notes)} archive observations).")
    lines.append("")

    lines.append("## Live rework candidates (write into goals.open)")
    lines.append("")
    if not live_rework:
        lines.append("_None — live corpus is current and well-connected to STATE._")
    else:
        for d in sorted(live_rework, key=lambda x: (-len(x["reasons"]), x["path"])):  # type: ignore[arg-type]
            lines.append(f"### `{d['path']}`")
            lines.append(f"- size: {d['bytes']:,}B  •  age: {d['age_days']}d  "
                         f"•  concepts: {d['concept_count']}")
            for r in d["reasons"]:  # type: ignore[index]
                lines.append(f"- ⚑ {r}")
            lines.append("")

    lines.append("## Archive observations (FYI, no goals written)")
    lines.append("")
    if not archive_notes:
        lines.append("_Archive is clean — no current doc has a redundant archived twin._")
    else:
        for d in sorted(archive_notes, key=lambda x: (-len(x["reasons"]), x["path"])):  # type: ignore[arg-type]
            lines.append(f"- `{d['path']}` — {', '.join(d['reasons'])}")  # type: ignore[index]
        lines.append("")

    lines.append("## Full corpus (sorted by concept density)")
    lines.append("")
    lines.append("| Doc | Bytes | Age (d) | Concepts |")
    lines.append("|-----|-------|---------|----------|")
    for d in sorted(docs, key=lambda x: -int(x["concept_count"])):  # type: ignore[arg-type]
        lines.append(
            f"| `{d['path']}` | {d['bytes']:,} | {d['age_days']} | "
            f"{d['concept_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


# ── Goals integration ─────────────────────────────────────────────────

def write_goals(rework: List[Dict[str, object]]) -> int:
    """Push one proposed_goal per rework doc. Returns count written.

    Goals land in `proposed_goals` with status='pending' so they show up
    in goals.open in STATE without auto-approval.
    """
    try:
        from agent.subconscious.loops.goals import propose_goal
    except Exception as e:
        print(f"[error] couldn't import propose_goal: {e}", file=sys.stderr)
        return 0

    count = 0
    for d in rework:
        # Don't write goals for archive docs — staleness alone isn't actionable
        # and we filter them out of the rework set already; this is belt-and-
        # suspenders in case a redundant archive sneaks through.
        if d.get("archived"):
            continue
        path = d["path"]
        reasons_str = "; ".join(d["reasons"])  # type: ignore[index]
        goal = f"Audit and rework {path}"
        rationale = (
            f"Doc audit flagged this file: {reasons_str}. "
            f"Either delete, merge into a sibling doc, or refresh so it "
            f"connects to current STATE."
        )
        # Priority: redundant/stale → low; disconnected/tiny → medium
        prio = "low"
        if any("disconnected" in r or "tiny" in r for r in d["reasons"]):  # type: ignore[index]
            prio = "medium"
        try:
            propose_goal(
                goal=goal,
                rationale=rationale,
                priority=prio,
                sources=["scripts/audit_docs.py", path],  # type: ignore[list-item]
            )
            count += 1
        except Exception as e:
            print(f"  [warn] propose_goal failed for {path}: {e}", file=sys.stderr)
    return count


# ── Entrypoint ────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--propose-goals", action="store_true",
                    help="write one proposed_goal per rework candidate")
    ap.add_argument("--out", default=None,
                    help="report path (default: data/audits/doc_audit_<date>.md)")
    args = ap.parse_args()

    # Lazy import so a broken DB doesn't stop --help.
    from agent.threads.linking_core.schema import extract_concepts_from_text

    docs_paths = collect_docs()
    print(f"[audit] scanning {len(docs_paths)} docs ...")
    docs = [analyze_doc(p, extract_concepts_from_text) for p in docs_paths]

    rework = find_rework_candidates(docs)
    print(f"[audit] {len(rework)} rework candidate(s)")

    report = render_markdown(docs, rework)

    out_path = args.out
    if not out_path:
        audits_dir = ROOT / "data" / "audits"
        audits_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = str(audits_dir / f"doc_audit_{date}.md")
    Path(out_path).write_text(report, encoding="utf-8")
    print(f"[audit] report written: {out_path}")

    if args.propose_goals:
        n = write_goals(rework)
        print(f"[audit] {n} proposed_goal(s) written to DB")

    return 0


if __name__ == "__main__":
    sys.exit(main())
