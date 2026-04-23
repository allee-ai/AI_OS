"""
Research Feed Module
====================

Scrapes high-signal external sources so the agent can compare its own
state and decisions against what's actually happening in the world.

Sources (all stdlib-only fetchers, see fetchers.py):
- hackernews: AI-filtered top stories
- arxiv: recent cs.AI / cs.LG / cs.CL submissions
- github: repos pushed in the last week matching agent/llm/mcp queries

Storage is the `research_items` SQLite table (see store.py). Items are
deduped by url. `research_item_new` events fire on first insert so
reflexes / evolve loop can react.

Unlike socials-style feeds, this one is pull-only, read-mostly, and
safe to run on a timer.
"""

from typing import Any, Dict, List, Optional

from Feeds.events import EventTypeDefinition, register_event_types, emit_event

from .fetchers import (
    run_all,
    fetch_hackernews,
    fetch_arxiv,
    fetch_github_trending,
    FETCHERS,
)
from .store import (
    init_research_tables,
    upsert_item,
    get_recent,
    get_top_by_score,
    counts_by_source,
    total_count,
)


# ============================================================================
# Event Types
# ============================================================================

RESEARCH_EVENT_TYPES = [
    EventTypeDefinition(
        name="research_item_new",
        description="A new item was scraped from a research source",
        payload_schema={
            "source": "str",
            "url": "str",
            "title": "str",
            "score": "float",
        },
        example_payload={
            "source": "hackernews",
            "url": "https://news.ycombinator.com/item?id=42000000",
            "title": "Show HN: a local agent OS",
            "score": 312.0,
        },
    ),
    EventTypeDefinition(
        name="research_poll_complete",
        description="A full research poll cycle finished",
        payload_schema={"counts": "dict"},
        example_payload={"counts": {"hackernews": 4, "arxiv": 10, "github": 3}},
    ),
]

register_event_types("research", RESEARCH_EVENT_TYPES)


# ============================================================================
# Config
# ============================================================================

RESEARCH_CONFIG = {
    "provider": "research",
    "auth_type": "none",
    "settings": {
        "enabled_sources": ["hackernews", "arxiv", "github"],
        "poll_interval_minutes": 60,
    },
}


# ============================================================================
# Public API
# ============================================================================

def poll(verbose: bool = False,
         sources: Optional[List[str]] = None) -> Dict[str, int]:
    """Pull from every enabled source and emit events for each new item.

    Returns {source: new_row_count}.
    """
    init_research_tables()
    counts: Dict[str, int] = {}
    for name, fn in FETCHERS.items():
        if sources and name not in sources:
            continue
        try:
            items = fn()
        except Exception as e:
            if verbose:
                print(f"[research:{name}] fetch error: {e}")
            counts[name] = 0
            continue
        new_rows = 0
        for it in items:
            try:
                is_new = upsert_item(
                    source=it["source"],
                    url=it["url"],
                    title=it["title"],
                    summary=it.get("summary", ""),
                    score=float(it.get("score", 0)),
                    tags=it.get("tags", []),
                    published_at=it.get("published_at"),
                )
            except Exception as e:
                if verbose:
                    print(f"[research:{name}] upsert error: {e}")
                continue
            if is_new:
                new_rows += 1
                try:
                    emit_event(
                        feed_name="research",
                        event_type="research_item_new",
                        payload={
                            "source": it["source"],
                            "url": it["url"],
                            "title": it["title"],
                            "score": float(it.get("score", 0)),
                        },
                    )
                except Exception:
                    pass  # event bus issues shouldn't kill the fetcher
        counts[name] = new_rows
        if verbose:
            print(f"[research:{name}] fetched={len(items)} new={new_rows}")
    try:
        emit_event(
            feed_name="research",
            event_type="research_poll_complete",
            payload={"counts": counts},
        )
    except Exception:
        pass
    return counts


__all__ = [
    "RESEARCH_EVENT_TYPES",
    "RESEARCH_CONFIG",
    "poll",
    "run_all",
    "fetch_hackernews",
    "fetch_arxiv",
    "fetch_github_trending",
    "init_research_tables",
    "get_recent",
    "get_top_by_score",
    "counts_by_source",
    "total_count",
]
