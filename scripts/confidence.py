#!/usr/bin/env python3
"""confidence.py — score a proposed next action against approval history.

Purpose: gate the autopilot's "want me to do that next?" reflex. Asking
breaks autonomy in a learning system. Instead, score the proposed move
against:

  1. track_record  — recent turn_outcome grades (committed/partial/reverted)
  2. blast         — declared/inferred radius (low/med/high)
  3. reversibility — declared (default true)
  4. goal_alignment — keyword overlap with open proposed_goals
  5. precedent      — keyword overlap with recently committed convo_turns
  6. user_correction_alignment — overlap with user-correction meta_thoughts
     (rejected: strong dampen; expected/unknown: mild boost). Carries the
     structural asymmetry: the user can see things the agent can't, and
     her corrections are off-policy.

Weighted score in [0,1] -> recommendation:
  >= proceed_threshold (default 0.70)  PROCEED      (do it, no ask)
  >= ask_threshold     (default 0.45)  PROCEED-NOTED (do it, log margin)
  else                                  ASK         (genuine uncertainty)

Usage:
  scripts/confidence.py "<proposed action>" [options]

Options:
  --blast {low,med,high}     default low
  --not-reversible           irreversible action (e.g. delete, force push)
  --writes-db                bumps blast to med if it was low
  --deletes                  bumps blast to high
  --json                     machine-readable output
  --proceed-threshold FLOAT  default 0.70
  --ask-threshold FLOAT      default 0.45
  --window INT               # turns to consider for track_record (default 20)
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "db" / "state.db"

# Weights sum to 1.0
WEIGHTS = {
    "track_record":              0.35,
    "blast":                     0.20,
    "reversibility":             0.15,
    "goal_alignment":            0.10,
    "precedent":                 0.10,
    "user_correction_alignment": 0.10,
}

BLAST_SCORE = {"low": 1.0, "med": 0.55, "high": 0.20}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for",
    "is", "are", "be", "with", "that", "this", "it", "as", "at", "by",
    "from", "into", "do", "did", "done", "i", "you", "we", "they", "my",
    "our", "your", "so", "if", "not", "no", "yes", "can", "will", "would",
    "should", "want", "next", "then", "now", "just", "still", "more", "less",
    "any", "some", "all", "one", "two", "three", "make", "made", "let", "lets",
    "let's", "out", "up", "down", "off", "over", "under", "than", "also",
}

_TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")


def tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 2}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap_ratio(query: set[str], target: set[str]) -> float:
    """Fraction of query tokens present in target (asymmetric)."""
    if not query:
        return 0.0
    return len(query & target) / len(query)


def score_track_record(conn: sqlite3.Connection, window: int) -> tuple[float, str]:
    """Per-turn averaging with recency weighting.

    Each turn contributes a status score in [-0.5, 1.0]:
      ok / committed-only        -> +1.0
      committed > reverted       -> +0.7
      partial (surviving > 0)    -> +0.4
      reverted > committed       -> -0.5
    Then a half-life weight: most recent turn weight 1.0, decays by 0.93 per
    turn back. Final score = (weighted_avg + 0.5) / 1.5  clipped to [0,1].
    """
    cur = conn.execute(
        "SELECT metadata_json FROM unified_events "
        "WHERE event_type='turn_outcome' "
        "ORDER BY id DESC LIMIT ?",
        (window,),
    )
    rows = cur.fetchall()
    if not rows:
        return 0.5, "no turn_outcome history; neutral"

    counts = {"committed": 0, "partial": 0, "reverted": 0, "ok": 0}
    weighted = 0.0
    weight_total = 0.0
    decay = 0.93
    w = 1.0
    for (meta,) in rows:
        try:
            m = json.loads(meta or "{}")
        except json.JSONDecodeError:
            w *= decay
            continue
        c = int(m.get("committed", 0))
        s = int(m.get("surviving", 0))
        r = int(m.get("reverted", 0))
        status = m.get("status", "unknown")

        if status == "ok" or (c > 0 and r == 0 and s == 0):
            turn_score = 1.0
            counts["ok"] += 1
        elif c > r and c > 0:
            turn_score = 0.7
            counts["committed"] += 1
        elif r > c and r > 0:
            turn_score = -0.5
            counts["reverted"] += 1
        else:
            turn_score = 0.4  # partial / still-dirty
            counts["partial"] += 1

        weighted += w * turn_score
        weight_total += w
        w *= decay

    if weight_total <= 0:
        return 0.5, "track_record weight=0; neutral"
    avg = weighted / weight_total
    # avg in [-0.5, 1.0] -> normalize to [0,1]
    s = max(0.0, min(1.0, (avg + 0.5) / 1.5))
    detail = (
        f"last {len(rows)} turns (recency-weighted): "
        f"ok={counts['ok']} committed>reverted={counts['committed']} "
        f"partial={counts['partial']} reverted>committed={counts['reverted']} "
        f"-> avg={avg:+.2f}"
    )
    return s, detail


def score_blast(blast: str) -> tuple[float, str]:
    return BLAST_SCORE.get(blast, 0.5), f"blast={blast}"


def score_reversibility(reversible: bool) -> tuple[float, str]:
    return (1.0, "reversible") if reversible else (0.2, "NOT reversible")


def score_goal_alignment(conn: sqlite3.Connection, q_tokens: set[str]) -> tuple[float, str]:
    cur = conn.execute(
        "SELECT id, goal, priority FROM proposed_goals WHERE status='open' ORDER BY id DESC LIMIT 30"
    )
    rows = cur.fetchall()
    if not rows:
        return 0.5, "no open goals; neutral"

    best_goal_id = None
    best_overlap = 0.0
    best_text = ""
    for gid, goal_text, _prio in rows:
        gtokens = tokens(goal_text or "")
        ov = overlap_ratio(q_tokens, gtokens)
        if ov > best_overlap:
            best_overlap = ov
            best_goal_id = gid
            best_text = (goal_text or "")[:60]

    if best_overlap < 0.10:
        return 0.5, f"no goal match (best overlap {best_overlap:.2f}); neutral"
    # 0.10 -> 0.55, 0.50 -> 0.95
    s = min(1.0, 0.5 + best_overlap)
    return s, f"matches goal #{best_goal_id} ('{best_text}', overlap {best_overlap:.2f})"


def score_precedent(conn: sqlite3.Connection, q_tokens: set[str], scan: int = 80) -> tuple[float, str]:
    """Look at recent convo_turns. If similar past summaries were committed, boost.
    If reverted, dampen."""
    cur = conn.execute(
        "SELECT t.user_message, "
        "       (SELECT ue.metadata_json FROM unified_events ue "
        "        WHERE ue.event_type='turn_outcome' AND ue.timestamp > t.timestamp "
        "        ORDER BY ue.id ASC LIMIT 1) "
        "FROM convo_turns t "
        "WHERE t.user_message IS NOT NULL "
        "ORDER BY t.id DESC LIMIT ?",
        (scan,),
    )
    rows = cur.fetchall()
    if not rows:
        return 0.5, "no convo precedent; neutral"

    matches: list[tuple[float, str]] = []
    for msg, meta in rows:
        if not msg:
            continue
        ov = jaccard(q_tokens, tokens(msg))
        if ov >= 0.10:
            status = "unknown"
            if meta:
                try:
                    status = json.loads(meta).get("status", "unknown")
                except json.JSONDecodeError:
                    pass
            matches.append((ov, status))

    if not matches:
        return 0.5, "no similar prior turns; neutral"

    # Weight by overlap. committed=+1, partial=+0.4, reverted=-0.6
    weight = 0.0
    total = 0.0
    for ov, status in matches[:6]:
        s = {"committed": 1.0, "partial": 0.4, "reverted": -0.6, "ok": 1.0}.get(status, 0.3)
        weight += ov * s
        total += ov
    if total == 0:
        return 0.5, "no weighted precedent"
    raw = weight / total
    s = max(0.0, min(1.0, 0.5 + raw / 2))
    statuses = ", ".join(f"{ov:.2f}/{st}" for ov, st in matches[:3])
    return s, f"{len(matches)} similar turns ({statuses})"


def score_user_correction_alignment(
    conn: sqlite3.Connection, q_tokens: set[str], scan: int = 60
) -> tuple[float, str]:
    """Score against recent user_correction meta_thoughts.

    The user sees off-policy signal the agent can't generate from inside
    its own loop. If a proposed action overlaps with a 'rejected' user
    correction, that's a strong signal this category of action was
    previously corrected — dampen hard. Overlap with 'expected'/'unknown'
    user notes — mild boost (the user flagged this territory as worth
    watching).

    Returns (score, detail). No user_correction history -> 0.5 neutral.
    """
    cur = conn.execute(
        "SELECT id, kind, content, weight FROM reflex_meta_thoughts "
        "WHERE source = 'user_correction' "
        "ORDER BY id DESC LIMIT ?",
        (scan,),
    )
    rows = cur.fetchall()
    if not rows:
        return 0.5, "no user_correction history; neutral"

    # Use overlap_ratio (asymmetric, query-side) rather than jaccard:
    # user notes are typically longer / richer than the one-line action,
    # so jaccard under-counts conceptual matches. A 0.15 query-side
    # overlap means 15% of the action's tokens appear in the note \u2014
    # tight enough to avoid noise, loose enough to catch reformulations
    # like "kill env hub" matching note #233's "hub-key stoplist".
    rejected_hits: list[tuple[float, int]] = []
    positive_hits: list[tuple[float, int]] = []
    for mid, kind, content, _w in rows:
        if not content:
            continue
        ov = overlap_ratio(q_tokens, tokens(content))
        if ov < 0.15:
            continue
        if kind == "rejected":
            rejected_hits.append((ov, mid))
        elif kind in ("expected", "unknown"):
            positive_hits.append((ov, mid))

    if not rejected_hits and not positive_hits:
        return 0.5, f"scanned {len(rows)} user notes; no overlap; neutral"

    # Strong dampen if any rejected overlap. Best-overlap weighted.
    if rejected_hits:
        best_ov, best_id = max(rejected_hits, key=lambda x: x[0])
        # 0.10 -> 0.40, 0.50 -> 0.10, 1.00 -> 0.00
        s = max(0.0, 0.5 - best_ov)
        return s, (
            f"⚠ overlaps user-rejected note #{best_id} "
            f"(overlap {best_ov:.2f}); strong dampen"
        )

    # Otherwise, mild boost from positive hits.
    best_ov, best_id = max(positive_hits, key=lambda x: x[0])
    s = min(1.0, 0.5 + best_ov * 0.6)
    return s, (
        f"matches user-flagged note #{best_id} (overlap {best_ov:.2f}); mild boost"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Confidence-gate a proposed next action.")
    ap.add_argument("action", help="Proposed next action (one line).")
    ap.add_argument("--blast", choices=["low", "med", "high"], default="low")
    ap.add_argument("--not-reversible", action="store_true",
                    help="Action is irreversible (delete, force-push, drop table).")
    ap.add_argument("--writes-db", action="store_true",
                    help="Action writes to state.db; bumps blast to med if low.")
    ap.add_argument("--deletes", action="store_true",
                    help="Action deletes data/files; sets blast=high.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--proceed-threshold", type=float, default=0.70)
    ap.add_argument("--ask-threshold", type=float, default=0.45)
    ap.add_argument("--window", type=int, default=20)
    args = ap.parse_args()

    blast = args.blast
    if args.deletes:
        blast = "high"
    elif args.writes_db and blast == "low":
        blast = "med"

    reversible = not args.not_reversible

    if not DB.exists():
        print(f"ERROR: DB not found at {DB}", file=sys.stderr)
        return 2

    q_tokens = tokens(args.action)

    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        sig: dict[str, dict] = {}
        s_track, d_track = score_track_record(conn, args.window)
        sig["track_record"] = {"score": s_track, "detail": d_track}
        s_blast, d_blast = score_blast(blast)
        sig["blast"] = {"score": s_blast, "detail": d_blast}
        s_rev, d_rev = score_reversibility(reversible)
        sig["reversibility"] = {"score": s_rev, "detail": d_rev}
        s_goal, d_goal = score_goal_alignment(conn, q_tokens)
        sig["goal_alignment"] = {"score": s_goal, "detail": d_goal}
        s_prec, d_prec = score_precedent(conn, q_tokens)
        sig["precedent"] = {"score": s_prec, "detail": d_prec}
        s_uca, d_uca = score_user_correction_alignment(conn, q_tokens)
        sig["user_correction_alignment"] = {"score": s_uca, "detail": d_uca}

    weighted = sum(WEIGHTS[k] * sig[k]["score"] for k in WEIGHTS)
    if weighted >= args.proceed_threshold:
        rec = "PROCEED"
        reason = "high confidence; do it without asking"
    elif weighted >= args.ask_threshold:
        rec = "PROCEED-NOTED"
        reason = "moderate confidence; do it but log a forward note about the margin"
    else:
        rec = "ASK"
        reason = "genuine uncertainty; confirm with user first"

    if args.json:
        out = {
            "action": args.action,
            "blast": blast,
            "reversible": reversible,
            "tokens": sorted(q_tokens),
            "signals": sig,
            "weights": WEIGHTS,
            "weighted_score": round(weighted, 3),
            "recommendation": rec,
            "reason": reason,
            "thresholds": {
                "proceed": args.proceed_threshold,
                "ask": args.ask_threshold,
            },
        }
        print(json.dumps(out, indent=2))
        return 0

    # Human output
    print(f"proposed: {args.action}")
    print(f"  blast={blast}  reversible={reversible}")
    print(f"  tokens: {sorted(q_tokens)[:12]}{'...' if len(q_tokens) > 12 else ''}")
    print()
    for k in ("track_record", "blast", "reversibility", "goal_alignment", "precedent", "user_correction_alignment"):
        s = sig[k]
        bar = "#" * int(round(s["score"] * 10))
        print(f"  {k:<26} {s['score']:.2f}  [{bar:<10}]  ({WEIGHTS[k]:.0%})  {s['detail']}")
    print()
    print(f"  weighted_score = {weighted:.3f}")
    print(f"  recommendation = {rec}")
    print(f"  reason         = {reason}")
    print(f"  thresholds     = proceed≥{args.proceed_threshold:.2f}  "
          f"ask<{args.ask_threshold:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
