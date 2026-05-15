"""Cortex-tag pass-forward: extract structured metadata from my own prior
turn's output so the *next* turn-start can surface it as STATE context.

The convention I follow at end of every coding turn:

    <state-tags>
    prediction: <what I expect to happen / what cade will ask next>
    affect: <one-word stance: focused / convergent / blocked / curious / ...>
    metacognition: <what I am confident about vs guessing>
    open-loops: <comma-separated short labels of unfinished threads>
    </state-tags>

The block is plain text inside my assistant message. This module finds
the most recent *completed* assistant turn in the VS Code Copilot
transcript JSONL, concatenates all ``assistant.message`` content
between the matching ``turn_start`` / ``turn_end`` pair, and parses
the tag block out. Returns ``{}`` silently on any failure — this is a
best-effort signal, never a blocker for the ritual.

Storage: writes the extracted tags to ``data/.last_cortex_tags.json``
so the value is available even if the transcript file moves.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = ROOT / "data" / ".last_cortex_tags.json"
HISTORY_FILE = ROOT / "data" / ".cortex_tag_history.jsonl"
HISTORY_KEEP = 20  # rolling window length

_TRANSCRIPTS_DIR = Path(
    "/Users/cade/Library/Application Support/Code/User/workspaceStorage/"
    "1d1eb7ce2af3f8d35653fa92652e7e62/GitHub.copilot-chat/transcripts"
)

_TAG_BLOCK_RE = re.compile(
    r"<state-tags>(.*?)</state-tags>", re.DOTALL | re.IGNORECASE
)
_TAG_LINE_RE = re.compile(r"^\s*([a-z][a-z0-9_\-]*)\s*:\s*(.+?)\s*$", re.IGNORECASE)

# Recognized tag keys (normalized). Anything else is captured under "extra".
_KNOWN_KEYS = {"prediction", "affect", "metacognition", "open-loops", "open_loops"}


def _find_transcript() -> Optional[Path]:
    """Most-recently-modified .jsonl in the transcripts dir."""
    if not _TRANSCRIPTS_DIR.is_dir():
        return None
    files = sorted(
        _TRANSCRIPTS_DIR.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None


def _extract_last_completed_assistant_text(path: Path) -> str:
    """Concatenate all assistant.message content from the PRIOR user turn.

    Copilot's transcript fires ``assistant.turn_start``/``turn_end`` per
    tool round-trip, not per user-visible turn. So a single user request
    produces many "turns" in the JSONL.  The meaningful boundary is
    ``user.message``.

    Algorithm:
      1. Walk events from the end.
      2. The FIRST user.message we hit (going backwards) is the *current*
         user turn we're processing right now — skip past it.
      3. The SECOND user.message is the start of the prior assistant
         response.  Grab everything between (second user.message, first
         user.message) that is an ``assistant.message`` and concatenate.
      4. If there is only one user.message (very first turn ever), there
         is no prior to extract — return "".
    """
    try:
        lines = path.read_text().splitlines()
    except Exception:
        return ""

    user_msg_indices: list[int] = []
    parsed: list[dict] = []
    for ln in lines:
        try:
            ev = json.loads(ln)
        except Exception:
            parsed.append({})
            continue
        parsed.append(ev)
        if ev.get("type") == "user.message":
            user_msg_indices.append(len(parsed) - 1)

    # Need at least two user messages to define a "prior" turn.
    if len(user_msg_indices) < 2:
        # Edge case: only one user message but maybe the assistant
        # already replied to it and we're being invoked mid-turn for a
        # second look. Fall back to "everything assistant said before
        # the only user.message" — useful when running ad-hoc.
        if len(user_msg_indices) == 1:
            cur_user = user_msg_indices[0]
            start, end = 0, cur_user
        else:
            return ""
    else:
        cur_user = user_msg_indices[-1]
        prior_user = user_msg_indices[-2]
        start, end = prior_user + 1, cur_user

    chunks: list[str] = []
    for i in range(start, end):
        ev = parsed[i]
        if ev.get("type") != "assistant.message":
            continue
        data = ev.get("data") or {}
        content = data.get("content")
        if isinstance(content, str) and content:
            chunks.append(content)
    return "\n".join(chunks)


def _parse_tags(text: str) -> dict:
    """Find <state-tags>...</state-tags> and return key->value dict.

    If multiple blocks are present (rare — only happens if I wrote one
    per intermediate message), merge them with later values winning.
    """
    out: dict = {}
    for m in _TAG_BLOCK_RE.finditer(text):
        inner = m.group(1)
        for line in inner.splitlines():
            mm = _TAG_LINE_RE.match(line)
            if not mm:
                continue
            key = mm.group(1).strip().lower().replace("_", "-")
            val = mm.group(2).strip()
            if not val:
                continue
            out[key] = val
    return out


def extract_and_cache() -> dict:
    """Read transcript, extract tags, write cache file, return payload.

    Payload shape::

        {
            "tags": {prediction, affect, metacognition, open-loops, ...},
            "source_transcript": <path>,
            "chars_scanned": <int>,
            "prior_had_assistant_content": <bool>,
            "prior_emitted_no_tags": <bool>,
            "current_user_query": <str>,    # the user message we are now answering
            "prediction_score": <float|None>,  # 0..1 jaccard of prior prediction vs current query
        }

    Returns ``{}`` on hard failure. Always safe to call.
    """
    out: dict = {}
    try:
        path = _find_transcript()
        if path is None:
            return out
        text = _extract_last_completed_assistant_text(path)
        current_user = _extract_current_user_query(path)
        tags = _parse_tags(text) if text else {}

        prior_had_content = bool(text and text.strip())
        out = {
            "tags": tags,
            "source_transcript": str(path),
            "chars_scanned": len(text or ""),
            "prior_had_assistant_content": prior_had_content,
            "prior_emitted_no_tags": prior_had_content and not tags,
            "current_user_query": current_user,
            "prediction_score": None,
        }

        # Score prior prediction against current user query.
        prior_prediction = tags.get("prediction") if tags else None
        if prior_prediction and current_user:
            out["prediction_score"] = _jaccard_overlap(prior_prediction, current_user)

        # Append to rolling history (only if we have some signal worth keeping).
        if tags or prior_had_content:
            try:
                _append_history({
                    "ts": _now_iso(),
                    "tags": tags or {},
                    "current_user_query": (current_user or "")[:500],
                    "prediction_score": out["prediction_score"],
                    "prior_emitted_no_tags": out["prior_emitted_no_tags"],
                })
            except Exception:
                pass

        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(json.dumps(out, indent=2))
        except Exception:
            pass
        return out
    except Exception:
        return out


# ── helpers: current user query, scoring, history ───────────────────────────

def _extract_current_user_query(path: Path) -> str:
    """The most recent user.message in the transcript (the one we're answering)."""
    try:
        lines = path.read_text().splitlines()
    except Exception:
        return ""
    for ln in reversed(lines):
        try:
            ev = json.loads(ln)
        except Exception:
            continue
        if ev.get("type") != "user.message":
            continue
        data = ev.get("data") or {}
        content = data.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return ""


_WORD_RE = re.compile(r"[a-z0-9_\-]{3,}")
_STOP = {
    "the", "and", "for", "this", "that", "with", "you", "are", "but", "not",
    "have", "has", "from", "your", "will", "would", "could", "should", "what",
    "when", "where", "why", "how", "next", "turn", "ask", "asks", "asked",
    "about", "into", "over", "just", "than", "then", "now", "back", "again",
    "very", "really", "still", "also", "more", "most", "some", "any",
    "let", "lets", "did", "does", "doing", "make", "made", "get", "got",
    "see", "look", "looks", "going", "want", "wants", "need", "needed",
    "thing", "things", "stuff", "one", "two", "three", "yes", "no",
}


def _jaccard_overlap(a: str, b: str) -> float:
    """Crude lexical overlap of two strings, range 0.0–1.0."""
    def _toks(s: str) -> set[str]:
        return {w for w in _WORD_RE.findall(s.lower()) if w not in _STOP}
    ta, tb = _toks(a), _toks(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return round(len(inter) / len(union), 3) if union else 0.0


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append_history(record: dict) -> None:
    """Append one record to history file and truncate to HISTORY_KEEP."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if HISTORY_FILE.exists():
        try:
            for ln in HISTORY_FILE.read_text().splitlines():
                if ln.strip():
                    existing.append(json.loads(ln))
        except Exception:
            existing = []
    existing.append(record)
    existing = existing[-HISTORY_KEEP:]
    HISTORY_FILE.write_text("\n".join(json.dumps(r) for r in existing) + "\n")


def _load_history() -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return [
            json.loads(ln) for ln in HISTORY_FILE.read_text().splitlines() if ln.strip()
        ]
    except Exception:
        return []


def load_cached() -> dict:
    """Return the most recently cached cortex tags (or {} if none)."""
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def render_banner_section(payload: dict) -> str:
    """Format extracted tags + history for the turn-start banner."""
    if not payload:
        return ""
    lines: list[str] = []

    tags = payload.get("tags") or {}
    if tags:
        lines.append("[cortex.tags] carried forward from prior turn:")
        order = ["prediction", "affect", "metacognition", "open-loops"]
        seen: set[str] = set()
        for k in order:
            if k in tags:
                lines.append(f"  {k}: {tags[k]}")
                seen.add(k)
        for k, v in tags.items():
            if k in seen:
                continue
            lines.append(f"  {k}: {v}")

        # Prediction hit-score for the prediction that was made last turn.
        score = payload.get("prediction_score")
        if score is not None and tags.get("prediction"):
            verdict = "hit" if score >= 0.30 else ("partial" if score >= 0.10 else "miss")
            lines.append(f"  prediction_score: {score:.2f} [{verdict}]  "
                         f"(jaccard vs current user query)")
    elif payload.get("prior_emitted_no_tags"):
        lines.append("!! cortex.tags: prior assistant turn produced output but "
                     "emitted NO <state-tags> block — habit slipping.")
        lines.append("   convention: end every turn with a state-tags block. "
                     "See .github/copilot-instructions.md → Turn-End Ritual.")

    # Trajectory: last N affects + open-loops counts + prediction hit-rate.
    hist = _load_history()
    if len(hist) >= 2:
        affects = [(h.get("tags") or {}).get("affect") for h in hist[-8:]]
        affects = [a for a in affects if a]
        if affects:
            lines.append("")
            lines.append(f"[cortex.trajectory] last {len(affects)} affects: "
                         + " → ".join(affects))
        # Prediction hit-rate over rolling window
        scored = [h for h in hist[-10:] if h.get("prediction_score") is not None]
        if scored:
            hits = sum(1 for h in scored if h["prediction_score"] >= 0.30)
            partials = sum(1 for h in scored if 0.10 <= h["prediction_score"] < 0.30)
            avg = sum(h["prediction_score"] for h in scored) / len(scored)
            lines.append(
                f"  prediction hit-rate (last {len(scored)}): "
                f"{hits} hit, {partials} partial, "
                f"{len(scored) - hits - partials} miss  •  "
                f"avg_score={avg:.2f}"
            )
        # Open-loops drift
        last_loops = (hist[-1].get("tags") or {}).get("open-loops") or \
                     (hist[-1].get("tags") or {}).get("open_loops")
        if last_loops:
            n = len([x for x in last_loops.split(",") if x.strip()])
            lines.append(f"  open-loops: {n} item(s) carried forward")

    return "\n".join(lines)


if __name__ == "__main__":
    # Quick CLI for manual probing:
    #   .venv/bin/python -m agent.subconscious.cortex_tags
    payload = extract_and_cache()
    if not payload:
        print("(no cortex tags found in prior turn)")
    else:
        print(render_banner_section(payload))
        print(f"\ncached to: {CACHE_FILE}")
