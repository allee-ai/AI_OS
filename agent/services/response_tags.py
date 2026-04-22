"""
Response-Tag Parser
===================

Strict parser for meta-thought tags embedded in model responses.

Architecture:
  The model emits zero or more of four tags at the end of its response:
    <rejected>...</rejected>
    <expected>...</expected>
    <unknown>...</unknown>
    <compression>...</compression>

  This module extracts those tags, returns the cleaned user-facing text,
  and returns the list of extracted thoughts for linking_core to commit.

Schema-bounded:
  - Only the four names above are recognized.
  - Unknown/malformed tags pass through as text (silent drop of meta).
  - Per-turn caps prevent flooding.
  - Content is clamped to 500 chars.
  - Function never raises.  On any failure returns (original_text, []).

See: /memories/repo/state_architecture.md (meta-thoughts, Phase 2)
"""

from __future__ import annotations

import re
from typing import List, Dict, Tuple


# The closed set of recognized kinds.  Must match
# agent.threads.reflex.schema.META_THOUGHT_KINDS.
RECOGNIZED_KINDS: Tuple[str, ...] = ("rejected", "expected", "unknown", "compression")

# Per-turn limits — defense against a runaway model flooding state.
MAX_PER_KIND: int = 2
MAX_TOTAL: int = 6
MAX_CONTENT_LEN: int = 500

# Non-greedy match of any recognized tag.  DOTALL so content can span lines.
_TAG_RE = re.compile(
    r"<(?P<kind>rejected|expected|unknown|compression)>(?P<content>.*?)</(?P=kind)>",
    re.DOTALL | re.IGNORECASE,
)


def _jaccard_overlap(a: str, b: str) -> float:
    """Word-level Jaccard similarity, 0..1.  Cheap echo detector."""
    try:
        sa = set(w for w in re.findall(r"\w+", a.lower()) if len(w) > 2)
        sb = set(w for w in re.findall(r"\w+", b.lower()) if len(w) > 2)
        if not sa or not sb:
            return 0.0
        inter = sa & sb
        union = sa | sb
        return len(inter) / len(union) if union else 0.0
    except Exception:
        return 0.0


def parse_response_tags(
    response_text: str,
    user_message: str = "",
) -> Tuple[str, List[Dict]]:
    """Extract meta-thought tags from a model response.

    Args:
        response_text: The raw text returned by the LLM.
        user_message: The user's message this turn.  Used for echo
            detection — tag content that overlaps heavily with the
            user's message is downweighted (likely prompt injection
            or dumb echo).

    Returns:
        (stripped_text, thoughts) where:
          - stripped_text: response with all recognized tags removed.
          - thoughts: list of dicts:
              {"kind": str, "content": str, "weight": float, "echo": bool}
            weight is 0.2 on likely echo, else 0.5.

    Never raises.  On any internal error, returns (response_text, []).
    """
    if not response_text or not isinstance(response_text, str):
        return response_text or "", []

    try:
        thoughts: List[Dict] = []
        per_kind: Dict[str, int] = {k: 0 for k in RECOGNIZED_KINDS}

        # Collect matches in order of appearance.
        for m in _TAG_RE.finditer(response_text):
            if len(thoughts) >= MAX_TOTAL:
                break
            kind = m.group("kind").lower()
            if kind not in RECOGNIZED_KINDS:
                continue  # redundant — regex already restricts — but safe
            if per_kind[kind] >= MAX_PER_KIND:
                continue
            content = (m.group("content") or "").strip()
            if not content:
                continue
            if len(content) > MAX_CONTENT_LEN:
                content = content[:MAX_CONTENT_LEN]
            # Echo detection — if content heavily overlaps user_message,
            # likely a dumb echo or injection.  Keep it, but downweight.
            echo = False
            weight = 0.5
            if user_message:
                overlap = _jaccard_overlap(content, user_message)
                if overlap >= 0.7:
                    echo = True
                    weight = 0.2
            thoughts.append({
                "kind": kind,
                "content": content,
                "weight": weight,
                "echo": echo,
            })
            per_kind[kind] += 1

        # Strip ALL recognized tags from the text (even those beyond caps —
        # they were proposed but not committed; they shouldn't leak to user).
        stripped = _TAG_RE.sub("", response_text)
        # Collapse runs of blank lines left behind.
        stripped = re.sub(r"\n{3,}", "\n\n", stripped).rstrip()

        return stripped, thoughts
    except Exception:
        # Never fail a turn because of tag parsing.
        return response_text, []


def commit_thoughts(
    thoughts: List[Dict],
    *,
    session_id: str = "",
    turn_id: int | None = None,
) -> int:
    """Commit parsed thoughts to reflex_meta_thoughts with source='model'.

    Returns count of rows actually written.  Never raises.
    """
    if not thoughts:
        return 0
    try:
        from agent.threads.reflex.schema import add_meta_thought
    except Exception:
        return 0
    n = 0
    for t in thoughts:
        try:
            rid = add_meta_thought(
                kind=t.get("kind", ""),
                content=t.get("content", ""),
                session_id=session_id or None,
                turn_id=turn_id,
                source="model",
                weight=float(t.get("weight", 0.5)),
                confidence=0.6,  # model-authored: default slightly above system
            )
            if rid:
                n += 1
        except Exception:
            continue
    return n


__all__ = [
    "RECOGNIZED_KINDS",
    "MAX_PER_KIND",
    "MAX_TOTAL",
    "MAX_CONTENT_LEN",
    "parse_response_tags",
    "commit_thoughts",
]
