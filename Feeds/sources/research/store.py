"""
Research feed store — outside-world items pulled by the fetchers.

One table: `research_items`. Deduped by url. Each row has source, title,
summary, score (source-specific hotness), tags, published_at, fetched_at.
Callers: Feeds/sources/research/fetchers.py writes; Feeds API + any
consumer (evolve loop, mobile panel, STATE if ever wanted) reads.
"""
from __future__ import annotations

import json
from contextlib import closing
from typing import Any, Dict, List, Optional


def _conn():
    from data.db import get_connection
    return get_connection()


def init_research_tables() -> None:
    """Create the research_items table if it doesn't exist. Idempotent."""
    with closing(_conn()) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS research_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                score REAL NOT NULL DEFAULT 0,
                tags_json TEXT NOT NULL DEFAULT '[]',
                published_at TEXT,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS ix_research_source ON research_items(source)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_research_fetched ON research_items(fetched_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_research_score ON research_items(score DESC)")
        c.commit()


def upsert_item(source: str, url: str, title: str, summary: str = "",
                score: float = 0.0, tags: Optional[List[str]] = None,
                published_at: Optional[str] = None) -> bool:
    """Insert or refresh a trend item. Returns True if new row, False if updated."""
    from data.db import get_connection
    tags_json = json.dumps(tags or [])
    with closing(get_connection()) as c:
        cur = c.execute(
            "SELECT id FROM research_items WHERE url = ?", (url,)
        ).fetchone()
        if cur is None:
            c.execute(
                """INSERT INTO research_items
                    (source, url, title, summary, score, tags_json, published_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (source, url, title, summary, score, tags_json, published_at),
            )
            c.commit()
            return True
        c.execute(
            """UPDATE research_items
                  SET source=?, title=?, summary=?, score=?, tags_json=?,
                      published_at=COALESCE(?, published_at),
                      fetched_at=datetime('now')
                WHERE url=?""",
            (source, title, summary, score, tags_json, published_at, url),
        )
        c.commit()
        return False


def get_recent(limit: int = 30, source: Optional[str] = None,
               min_score: float = 0.0) -> List[Dict[str, Any]]:
    """Most-recently-fetched items, optionally filtered by source."""
    from data.db import get_connection
    where = ["score >= ?"]
    params: List[Any] = [min_score]
    if source:
        where.append("source = ?")
        params.append(source)
    sql = (
        "SELECT id, source, url, title, summary, score, tags_json, "
        "       published_at, fetched_at "
        "FROM research_items WHERE " + " AND ".join(where) +
        " ORDER BY fetched_at DESC LIMIT ?"
    )
    params.append(limit)
    with closing(get_connection(readonly=True)) as c:
        rows = c.execute(sql, params).fetchall()
    out = []
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {
            "id": r[0], "source": r[1], "url": r[2], "title": r[3],
            "summary": r[4], "score": r[5], "tags_json": r[6],
            "published_at": r[7], "fetched_at": r[8],
        }
        try:
            d["tags"] = json.loads(d.pop("tags_json") or "[]")
        except Exception:
            d["tags"] = []
        out.append(d)
    return out


def get_top_by_score(limit: int = 10, hours: int = 48) -> List[Dict[str, Any]]:
    """Highest-scoring items from the last N hours."""
    from data.db import get_connection
    with closing(get_connection(readonly=True)) as c:
        rows = c.execute(
            """SELECT id, source, url, title, summary, score, tags_json,
                      published_at, fetched_at
               FROM research_items
               WHERE fetched_at >= datetime('now', ?)
               ORDER BY score DESC LIMIT ?""",
            (f"-{int(hours)} hours", limit),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r) if hasattr(r, "keys") else {
            "id": r[0], "source": r[1], "url": r[2], "title": r[3],
            "summary": r[4], "score": r[5], "tags_json": r[6],
            "published_at": r[7], "fetched_at": r[8],
        }
        try:
            d["tags"] = json.loads(d.pop("tags_json") or "[]")
        except Exception:
            d["tags"] = []
        out.append(d)
    return out


def counts_by_source() -> Dict[str, int]:
    from data.db import get_connection
    with closing(get_connection(readonly=True)) as c:
        rows = c.execute(
            "SELECT source, COUNT(*) FROM research_items GROUP BY source"
        ).fetchall()
    return {r[0]: r[1] for r in rows}


def total_count() -> int:
    from data.db import get_connection
    with closing(get_connection(readonly=True)) as c:
        r = c.execute("SELECT COUNT(*) FROM research_items").fetchone()
    return int(r[0]) if r else 0
