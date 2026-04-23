"""
scripts/reflex_grader.py — grade ungraded 'expected' meta-thoughts

For each ungraded expectation in reflex_meta_thoughts:
  1. Gather evidence since its created_at (recent log_events + commits)
  2. Ask the LLM (role=AUDIT) whether subsequent observable behavior
     aligned with, violated, or was silent on the expectation
  3. Write grade_delta JSON and set graded=1

Usage:
    .venv/bin/python scripts/reflex_grader.py               # grade up to 10
    .venv/bin/python scripts/reflex_grader.py --limit 25
    .venv/bin/python scripts/reflex_grader.py --dry-run     # no writes
    .venv/bin/python scripts/reflex_grader.py --stale-days 0.25   # only items older than 6h

Why this script exists:
  Reflex expectations have been piling up ungraded for two assessments in a
  row. The grader was the missing piece between "write it down" and
  "learn from it". This closes that loop.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure project root on path when run directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.db import get_connection
from agent.threads.reflex.schema import grade_expectation
from agent.services.llm import generate


JUDGE_SYSTEM = """You are grading a reflex expectation against what actually happened.

An expectation is a short belief written by the agent or a seed-author
about what should be true, how a feature should behave, or a principle
to follow. Your job is to judge whether subsequent observable activity
(log events + git commits) aligned with, violated, or is silent on the
expectation.

Respond with STRICT JSON only, no prose outside the JSON:
{
  "verdict": "confirmed" | "violated" | "silent",
  "match": true | false,
  "reasoning": "one or two sentences, referencing specific evidence when possible",
  "evidence_refs": ["short phrase from a log event or commit", ...]
}

Rules:
- "confirmed" → observable activity clearly aligns with the expectation. match=true.
- "violated"  → observable activity contradicts the expectation. match=false.
- "silent"    → no evidence either way. match=false (can't confirm).
- Keep reasoning under 240 characters.
- Only cite evidence that actually appears in the provided text.
"""


def _iso_to_dt(s: str) -> datetime:
    # sqlite CURRENT_TIMESTAMP returns "YYYY-MM-DD HH:MM:SS" (UTC, naive)
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _fetch_ungraded(limit: int, stale_days: float) -> list[dict]:
    """Get up to `limit` ungraded 'expected' meta-thoughts older than
    `stale_days` days. Oldest first — we pay down debt, not new arrivals."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    cutoff_s = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    with closing(get_connection(readonly=True)) as c:
        rows = c.execute(
            """
            SELECT id, content, source, created_at
              FROM reflex_meta_thoughts
             WHERE kind = 'expected' AND graded = 0
               AND created_at <= ?
             ORDER BY created_at ASC
             LIMIT ?
            """,
            (cutoff_s, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def _events_since(ts: str, limit: int = 30) -> list[dict]:
    with closing(get_connection(readonly=True)) as c:
        rows = c.execute(
            """
            SELECT event_type, source, data, timestamp
              FROM unified_events
             WHERE timestamp >= ?
             ORDER BY timestamp ASC
             LIMIT ?
            """,
            (ts, int(limit)),
        ).fetchall()
    return [dict(r) for r in rows]


def _commits_since(ts: str, limit: int = 20) -> list[str]:
    # ts is "YYYY-MM-DD HH:MM:SS" UTC. git log --since accepts ISO-ish.
    try:
        proc = subprocess.run(
            ["git", "-C", str(_ROOT), "log",
             f"--since={ts}", f"-n{int(limit)}",
             "--pretty=format:%h %s"],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            return []
        return [ln for ln in proc.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def _render_evidence(events: list[dict], commits: list[str]) -> str:
    lines = []
    if commits:
        lines.append("## Commits since expectation was written")
        for c in commits:
            lines.append(f"- {c}")
    else:
        lines.append("## Commits since expectation was written\n(none)")
    lines.append("")
    if events:
        lines.append("## Log events since expectation was written")
        for e in events[:30]:
            desc = (e.get("data") or "").strip().replace("\n", " ")
            if len(desc) > 200:
                desc = desc[:200] + "…"
            lines.append(f"- [{e.get('event_type')}/{e.get('source')}] {desc}")
    else:
        lines.append("## Log events since expectation was written\n(none)")
    return "\n".join(lines)


def _judge(content: str, evidence: str) -> dict:
    prompt = (
        f"EXPECTATION (written by {{source}}):\n{content}\n\n"
        f"OBSERVABLE ACTIVITY SINCE THEN:\n{evidence}\n\n"
        "Grade the expectation against the activity. Return JSON only."
    )
    raw = generate(prompt, system=JUDGE_SYSTEM, role="AUDIT",
                   temperature=0.2, max_tokens=400)
    # Extract JSON even if the model wraps it in prose
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return {"verdict": "silent", "match": False,
                "reasoning": f"judge returned non-JSON: {raw[:120]!r}",
                "evidence_refs": []}
    try:
        obj = json.loads(raw[start:end+1])
    except Exception as e:
        return {"verdict": "silent", "match": False,
                "reasoning": f"json parse failed: {e}",
                "evidence_refs": []}
    # Coerce types defensively
    obj.setdefault("verdict", "silent")
    obj["match"] = bool(obj.get("match", False))
    obj["reasoning"] = str(obj.get("reasoning", ""))[:480]
    refs = obj.get("evidence_refs") or []
    if isinstance(refs, list):
        obj["evidence_refs"] = [str(r)[:120] for r in refs[:5]]
    else:
        obj["evidence_refs"] = []
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description="Grade ungraded reflex expectations.")
    ap.add_argument("--limit", type=int, default=10,
                    help="Max expectations to grade this pass (default 10)")
    ap.add_argument("--stale-days", type=float, default=0.25,
                    help="Only grade expectations older than this many days (default 0.25 = 6h)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print judgments without writing grades")
    args = ap.parse_args()

    items = _fetch_ungraded(args.limit, args.stale_days)
    if not items:
        print("no ungraded expectations past the stale threshold. nothing to do.")
        return 0

    print(f"grading {len(items)} expectation(s)…")
    graded = 0
    silents = 0
    errors = 0

    for it in items:
        mid = it["id"]
        content = it["content"]
        src = it.get("source", "unknown")
        ct = it["created_at"]

        events = _events_since(ct, limit=30)
        commits = _commits_since(ct, limit=20)
        evidence = _render_evidence(events, commits)

        print(f"\n── #{mid} [{src}] {ct}")
        print(f"   {content[:110]}{'…' if len(content) > 110 else ''}")
        print(f"   evidence: {len(events)} events, {len(commits)} commits")

        try:
            judgment = _judge(content, evidence)
        except Exception as e:
            errors += 1
            print(f"   ERROR judging: {e}")
            continue

        print(f"   verdict={judgment['verdict']} match={judgment['match']}")
        print(f"   reason: {judgment['reasoning'][:200]}")

        if judgment["verdict"] == "silent":
            silents += 1

        if args.dry_run:
            continue

        actual = (
            f"verdict={judgment['verdict']}; refs="
            + "; ".join(judgment.get("evidence_refs", [])[:3])
        )[:500]
        notes = judgment["reasoning"][:500]
        ok = grade_expectation(mid, actual=actual,
                                match=judgment["match"], notes=notes)
        if ok:
            graded += 1
        else:
            errors += 1
            print(f"   ERROR: grade_expectation rejected the write")

    print(
        f"\ndone. graded={graded} silent={silents} errors={errors} "
        f"of {len(items)} attempted."
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
