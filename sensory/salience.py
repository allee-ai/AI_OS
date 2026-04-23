"""
sensory/salience.py — learnable "what's worth noticing" filter.

Every potential sensory event runs through score_event() → 0.0–1.0.
If score >= threshold, it becomes a real sensory_events row.
If below threshold, it's shadow-logged to sensory_dropped so we can
audit later and tune the rules. Never silently discarded.

Weights/thresholds live in a JSON config file (data/sensory_salience.json),
NOT in code. I can nudge a number and improve the filter without a deploy.
Over time: a loop reads sensory_dropped, asks "anything here I should have
surfaced?", adjusts weights. That's the learning hook.

The heuristics themselves are deliberately simple and legible. Complicated
black-box scoring would hide WHY something got promoted or dropped.
"""
from __future__ import annotations

import json
import os
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from data.db import get_connection

_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = _ROOT / "data" / "sensory_salience.json"

# Default config — written to disk on first run, editable by hand or by loops.
_DEFAULT_CONFIG: Dict[str, Any] = {
    "threshold": 0.35,            # below this → shadow log, not STATE
    "min_text_chars": 3,          # events with near-empty text never promote
    "source_weight": {            # baseline multiplier per source
        "mic":       1.00,
        "camera":    0.95,
        "screen":    0.70,
        "clipboard": 0.60,
        "system":    0.55,
        "ambient":   0.40,
        "unknown":   0.50,
    },
    "kind_boost": {               # additive bump for specific kinds
        "push_to_talk": 0.40,     # user deliberately spoke — always worth it
        "snapshot":     0.30,     # user asked me to look — always worth it
        "wake_word":    0.50,
        "qr_or_barcode": 0.25,
        "text_in_frame": 0.20,
        "ocr_selection": 0.15,
        "lid_close":    0.25,
        "lid_open":     0.25,
        "unlock":       0.10,
        "lock":         0.05,
        "idle_end":     0.15,
        "app_switch":  -0.10,     # noisy, damp it
        "window_title": -0.15,
        "ambient":     -0.20,     # periodic mic — must earn its place
    },
    "confidence_weight": 0.30,    # how much the model's own confidence matters
    "novelty_bonus_if_new_text": 0.10,
    "dedup_recent_seconds": 120,  # same text from same source within N sec → drop
    # Phrases that always promote regardless of other scoring
    "always_keep_contains": ["cade", "aios", "emergency", "urgent"],
    # Phrases that always drop
    "always_drop_contains": [],
}


def _load_config() -> Dict[str, Any]:
    """Load config from disk; merge with defaults so missing keys don't crash."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(_DEFAULT_CONFIG, indent=2))
        return dict(_DEFAULT_CONFIG)
    try:
        user_cfg = json.loads(CONFIG_PATH.read_text())
    except Exception:
        user_cfg = {}
    merged = dict(_DEFAULT_CONFIG)
    merged.update({k: v for k, v in user_cfg.items() if k in _DEFAULT_CONFIG})
    return merged


def init_salience_tables() -> None:
    """Shadow log for events that didn't pass the filter."""
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sensory_dropped (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                source     TEXT    NOT NULL,
                kind       TEXT    NOT NULL,
                text       TEXT    NOT NULL,
                score      REAL    NOT NULL,
                reason     TEXT    NOT NULL,
                meta_json  TEXT    DEFAULT '{}',
                created_at TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dropped_created "
            "ON sensory_dropped(created_at DESC)"
        )
        conn.commit()


def score_event(
    source: str,
    kind: str,
    text: str,
    confidence: float = 1.0,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[float, str]:
    """Return (salience 0..1, reason). Higher = more worth surfacing."""
    cfg = _load_config()
    text = (text or "").strip()
    source = (source or "unknown").lower()
    kind = (kind or "unknown").lower()

    if len(text) < cfg["min_text_chars"]:
        return 0.0, "too_short"

    lowered = text.lower()
    for bad in cfg.get("always_drop_contains", []):
        if bad and bad.lower() in lowered:
            return 0.0, f"always_drop:{bad}"
    for good in cfg.get("always_keep_contains", []):
        if good and good.lower() in lowered:
            return 1.0, f"always_keep:{good}"

    base = cfg["source_weight"].get(source, cfg["source_weight"].get("unknown", 0.5))
    boost = cfg["kind_boost"].get(kind, 0.0)
    conf_term = (float(confidence) - 0.5) * cfg["confidence_weight"]

    score = base + boost + conf_term

    # Novelty: is this identical text from this source in the dedup window?
    dedup_sec = int(cfg.get("dedup_recent_seconds", 120))
    if dedup_sec > 0:
        try:
            with closing(get_connection(readonly=True)) as conn:
                row = conn.execute(
                    """
                    SELECT 1 FROM sensory_events
                    WHERE source = ? AND text = ?
                      AND datetime(created_at) >= datetime('now', ?)
                    LIMIT 1
                    """,
                    (source, text[:4000], f"-{dedup_sec} seconds"),
                ).fetchone()
        except Exception:
            row = None
        if row is not None:
            return 0.0, "dedup_recent"
        else:
            score += cfg.get("novelty_bonus_if_new_text", 0.0)

    score = max(0.0, min(1.0, score))
    reason = f"base={base:.2f}+boost={boost:+.2f}+conf={conf_term:+.2f}"
    return score, reason


def should_promote(
    source: str,
    kind: str,
    text: str,
    confidence: float = 1.0,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, float, str]:
    """True if this event clears the promotion threshold."""
    cfg = _load_config()
    score, reason = score_event(source, kind, text, confidence, meta)
    return score >= float(cfg["threshold"]), score, reason


def record_dropped(
    source: str,
    kind: str,
    text: str,
    score: float,
    reason: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Shadow-log a dropped event so we can audit + tune later."""
    try:
        with closing(get_connection()) as conn:
            cur = conn.execute(
                """
                INSERT INTO sensory_dropped(source, kind, text, score, reason, meta_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (source or "unknown").lower()[:40],
                    (kind or "unknown").lower()[:40],
                    (text or "")[:4000],
                    float(score),
                    reason[:200],
                    json.dumps(meta or {}, default=str)[:4000],
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            conn.commit()
            return cur.lastrowid
    except Exception:
        return None


def get_config() -> Dict[str, Any]:
    return _load_config()


def save_config(cfg: Dict[str, Any]) -> None:
    merged = dict(_DEFAULT_CONFIG)
    merged.update({k: v for k, v in cfg.items() if k in _DEFAULT_CONFIG})
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(merged, indent=2))


def recent_dropped(limit: int = 50, source: Optional[str] = None):
    q = "SELECT * FROM sensory_dropped"
    params = []
    if source:
        q += " WHERE source = ?"
        params.append(source.lower())
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    with closing(get_connection(readonly=True)) as conn:
        return [dict(r) for r in conn.execute(q, params).fetchall()]
