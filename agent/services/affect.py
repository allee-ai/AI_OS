"""
Affect Store & Registry
========================

Central machinery for the per-thread affect-tag system.

Architecture
------------
- Each thread owns a `feelings.py` that registers its tag namespace
  via `register_thread()` at import time.
- Each registry entry declares:
    * tag_name    — the XML-ish tag the model emits (e.g. "log_affect")
    * thread      — owning thread name (e.g. "log")
    * schema      — closed dict of {key: (allowed_values, default_weight)}
    * model_emit  — bool; if False, only host-side code may write
                    (e.g. machine.* from heartbeat, log.* from clock)
- All affect lives in ONE table `affect_state(thread, key, value, weight,
  source, updated_at)` so adapters and STATE consumers have a uniform
  read API.
- The model emits `<thread_affect>key=value</thread_affect>` tags at the
  end of its response; `parse_all_affect()` extracts them, drops anything
  not in the registry, commits to `affect_state`.
- Each thread's adapter calls `read_thread_affect(thread)` to surface its
  current values in STATE.

Design choices
--------------
- Single shared table: simpler than 7 schema migrations, and current
  affect is by definition "now-only" — no history needed in the substrate.
  History naturally lives in `convo_turns.state_snapshot_json`.
- Closed schemas: same defense as response_tags — the model cannot
  invent keys or values that pollute STATE.
- Per-thread caps: bounded mutation surface per turn.
- Never raises: failures degrade silently. Affect is decoration, not
  load-bearing.

This module is intentionally small and dependency-light. Each thread's
feelings.py just imports it and calls `register_thread(...)`.
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AffectSchema:
    """Closed schema for one thread's affect namespace."""
    thread: str
    tag_name: str
    keys: Dict[str, Tuple[Tuple[str, ...], float]]  # key -> (values, weight)
    model_emit: bool = True
    description: str = ""

    def validate(self, key: str, value: str) -> Optional[float]:
        """Return the registered weight if (key, value) is valid, else None."""
        entry = self.keys.get(key)
        if not entry:
            return None
        allowed, weight = entry
        if value not in allowed:
            return None
        return weight


# Module-level registry. Threads register at import time.
_REGISTRY: Dict[str, AffectSchema] = {}      # tag_name -> schema
_BY_THREAD: Dict[str, AffectSchema] = {}     # thread   -> schema

# Per-turn caps (apply across all threads combined too).
MAX_PER_THREAD: int = 4
MAX_TOTAL: int = 16
MAX_CONTENT_LEN: int = 120


def register_thread(schema: AffectSchema) -> None:
    """Register a thread's affect namespace.  Idempotent on re-register."""
    _REGISTRY[schema.tag_name] = schema
    _BY_THREAD[schema.thread] = schema


def get_schema(thread: str) -> Optional[AffectSchema]:
    return _BY_THREAD.get(thread)


def all_schemas() -> List[AffectSchema]:
    return list(_BY_THREAD.values())


# ---------------------------------------------------------------------------
# Storage — single shared table
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS affect_state (
    thread       TEXT NOT NULL,
    key          TEXT NOT NULL,
    value        TEXT NOT NULL,
    weight       REAL NOT NULL DEFAULT 0.5,
    source       TEXT NOT NULL DEFAULT 'model',  -- 'model' | 'host' | 'system'
    session_id   TEXT,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (thread, key)
);

CREATE INDEX IF NOT EXISTS idx_affect_state_thread ON affect_state(thread);
"""

_initialized = False


def _get_conn(readonly: bool = False) -> sqlite3.Connection:
    from data.db import get_connection
    return get_connection(readonly=readonly)


def init_affect_state() -> None:
    """Create the affect_state table.  Idempotent."""
    global _initialized
    if _initialized:
        return
    try:
        with closing(_get_conn()) as conn:
            with conn:
                conn.executescript(_DDL)
        _initialized = True
    except Exception:
        # Best-effort.  If init fails, every other call will silently no-op.
        pass


def _ensure_init() -> None:
    if not _initialized:
        init_affect_state()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Build a single regex that matches any registered tag.
def _build_tag_re() -> re.Pattern:
    if not _REGISTRY:
        # Match nothing if no threads registered yet.
        return re.compile(r"(?!x)x")
    names = "|".join(re.escape(t) for t in _REGISTRY.keys())
    return re.compile(
        rf"<(?P<tag>{names})>(?P<content>.*?)</(?P=tag)>",
        re.DOTALL | re.IGNORECASE,
    )


_KV_RE = re.compile(
    r"^\s*(?P<key>[a-z_][a-z0-9_]*)\s*=\s*(?P<value>[a-z_][a-z0-9_\-]*)\s*$",
    re.IGNORECASE,
)


@dataclass
class ParsedAffect:
    thread: str
    key: str
    value: str
    weight: float


def parse_all_affect(response_text: str) -> Tuple[str, List[ParsedAffect]]:
    """Extract all registered affect tags from a model response.

    Returns (stripped_text, parsed_list).  Never raises.
    """
    if not response_text or not isinstance(response_text, str):
        return response_text or "", []
    if not _REGISTRY:
        return response_text, []

    try:
        tag_re = _build_tag_re()
        parsed: List[ParsedAffect] = []
        per_thread: Dict[str, int] = {}

        for m in tag_re.finditer(response_text):
            if len(parsed) >= MAX_TOTAL:
                break
            tag = m.group("tag").lower()
            schema = _REGISTRY.get(tag)
            if not schema or not schema.model_emit:
                continue
            content = (m.group("content") or "").strip()
            if not content or len(content) > MAX_CONTENT_LEN:
                continue
            kv = _KV_RE.match(content)
            if not kv:
                continue
            key = kv.group("key").lower()
            value = kv.group("value").lower()
            weight = schema.validate(key, value)
            if weight is None:
                continue
            count = per_thread.get(schema.thread, 0)
            if count >= MAX_PER_THREAD:
                continue
            parsed.append(ParsedAffect(
                thread=schema.thread,
                key=key,
                value=value,
                weight=weight,
            ))
            per_thread[schema.thread] = count + 1

        # Strip ALL registered tags (even those over caps — they shouldn't
        # leak to the user even when uncommitted).
        stripped = tag_re.sub("", response_text)
        stripped = re.sub(r"\n{3,}", "\n\n", stripped).rstrip()
        return stripped, parsed
    except Exception:
        return response_text, []


# ---------------------------------------------------------------------------
# Commit / read
# ---------------------------------------------------------------------------

def commit_affect(
    parsed: List[ParsedAffect],
    *,
    session_id: str = "",
    source: str = "model",
) -> int:
    """Upsert parsed affect rows into affect_state.  Returns rows written."""
    if not parsed:
        return 0
    _ensure_init()
    n = 0
    try:
        with closing(_get_conn()) as conn:
            with conn:
                for p in parsed:
                    try:
                        conn.execute(
                            """
                            INSERT INTO affect_state
                                (thread, key, value, weight, source, session_id, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(thread, key) DO UPDATE SET
                                value = excluded.value,
                                weight = excluded.weight,
                                source = excluded.source,
                                session_id = excluded.session_id,
                                updated_at = CURRENT_TIMESTAMP
                            """,
                            (p.thread, p.key, p.value, float(p.weight),
                             source, session_id or None),
                        )
                        n += 1
                    except Exception:
                        continue
    except Exception:
        return n
    return n


def push_thread_affect(
    thread: str,
    values: Dict[str, str],
    *,
    source: str = "host",
    session_id: str = "",
) -> int:
    """Host-side write path for non-model affect (e.g. heartbeat→machine).

    Validates each (key, value) against the registered schema for *thread*.
    Unknown thread, unknown key, or unknown value are silently dropped.
    """
    if not values:
        return 0
    schema = _BY_THREAD.get(thread)
    if not schema:
        return 0
    parsed: List[ParsedAffect] = []
    for k, v in values.items():
        try:
            key = str(k).lower()
            value = str(v).lower()
            w = schema.validate(key, value)
            if w is None:
                continue
            parsed.append(ParsedAffect(
                thread=thread, key=key, value=value, weight=w,
            ))
        except Exception:
            continue
    return commit_affect(parsed, session_id=session_id, source=source)


def read_thread_affect(thread: str) -> Dict[str, str]:
    """Return current {key: value} for a single thread.  Empty on miss."""
    _ensure_init()
    out: Dict[str, str] = {}
    try:
        with closing(_get_conn(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT key, value FROM affect_state WHERE thread = ? "
                "ORDER BY key",
                (thread,),
            )
            for row in cur.fetchall():
                key = row["key"] if isinstance(row, sqlite3.Row) else row[0]
                value = row["value"] if isinstance(row, sqlite3.Row) else row[1]
                if key and value:
                    out[str(key)] = str(value)
    except Exception:
        return {}
    return out


def read_all_affect() -> Dict[str, Dict[str, str]]:
    """Return current affect for every thread.  {thread: {key: value}}."""
    _ensure_init()
    out: Dict[str, Dict[str, str]] = {}
    try:
        with closing(_get_conn(readonly=True)) as conn:
            cur = conn.execute(
                "SELECT thread, key, value FROM affect_state ORDER BY thread, key"
            )
            for row in cur.fetchall():
                thread = row[0]
                key = row[1]
                value = row[2]
                if not (thread and key and value):
                    continue
                out.setdefault(str(thread), {})[str(key)] = str(value)
    except Exception:
        return {}
    return out


# ---------------------------------------------------------------------------
# Prompt block — concatenated from every registered, model-emitting schema
# ---------------------------------------------------------------------------

def build_affect_prompt_block() -> str:
    """Render the optional system-prompt section teaching the model
    every registered affect tag.  Caller decides when to include it.
    """
    if not _BY_THREAD:
        return ""
    lines: List[str] = []
    lines.append("\n\n== AFFECT TAGS (optional) ==")
    lines.append(
        "You may emit affect tags at the END of your response. They describe "
        "your current internal state for each thread. The user does NOT see "
        "them; they are written to your own state for future turns."
    )
    lines.append(
        f"Limits: max {MAX_PER_THREAD} per thread, {MAX_TOTAL} total. "
        "Unknown keys/values silently dropped."
    )
    lines.append("")
    lines.append("Available tags:")
    for schema in sorted(_BY_THREAD.values(), key=lambda s: s.thread):
        if not schema.model_emit:
            continue
        lines.append(f"  <{schema.tag_name}>  — {schema.description}")
        for key, (values, _w) in schema.keys.items():
            lines.append(f"    {key} ∈ {{{', '.join(values)}}}")
        lines.append("")
    lines.append("Format: <tag>key=value</tag>  (one tag per affect, at END only)")
    return "\n".join(lines)


def import_all_feelings() -> None:
    """Trigger import of every thread's feelings.py so they register.

    Called once at startup (or first parse) to populate the registry.
    """
    threads = ("identity", "log", "reflex", "philosophy",
               "form", "linking_core", "field")
    for t in threads:
        try:
            __import__(f"agent.threads.{t}.feelings")
        except Exception:
            # A thread without a feelings.py is fine; it just won't
            # contribute to affect.
            continue


__all__ = [
    "AffectSchema",
    "ParsedAffect",
    "MAX_PER_THREAD",
    "MAX_TOTAL",
    "register_thread",
    "get_schema",
    "all_schemas",
    "init_affect_state",
    "parse_all_affect",
    "commit_affect",
    "push_thread_affect",
    "read_thread_affect",
    "read_all_affect",
    "build_affect_prompt_block",
    "import_all_feelings",
]
