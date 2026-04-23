"""
Trend sources — fetchers that pull fresh items into trends_items.

Every fetcher is stdlib-only (urllib + json). No external deps. Each
returns a list of dicts with keys: source, url, title, summary, score,
tags, published_at. Callers pass them to schema.upsert_item.

Sources chosen for "what the agent world is actually doing right now":
- hackernews: top stories, filtered for ai/ml/llm/agent keywords
- arxiv: recent cs.AI/cs.LG submissions
- github: trending repos by topic
- papers_with_code: (skipped — no stable public API)

Add more sources by dropping a new fetcher below and listing it in
FETCHERS.
"""
from __future__ import annotations

import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List

UA = "AIOS-trends/1.0 (+github.com/cadeaiwebdev/AI_OS)"
TIMEOUT = 15


def _build_ssl_context() -> ssl.SSLContext:
    """Build an SSL context with CA bundle.

    macOS python.org Python ships without a usable CA store. `certifi`
    is the portable fix and is already in .venv for almost every python
    project. Fall back to the stdlib default otherwise.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_CTX = _build_ssl_context()


def _get(url: str, accept: str = "application/json") -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": accept}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
        return resp.read()


AI_KEYWORDS = re.compile(
    r"\b(ai|llm|gpt|claude|gemini|agent|rag|mcp|transformer|diffusion|"
    r"fine.?tune|prompt|embedding|vector|ollama|mistral|qwen|deepseek|"
    r"anthropic|openai|inference|training|codex|copilot|cursor|devin)\b",
    re.IGNORECASE,
)


# ─── HackerNews (top stories, filtered) ───

def fetch_hackernews(limit: int = 30) -> List[Dict[str, Any]]:
    """Top HN stories that mention AI/LLM/agent keywords."""
    try:
        top_ids = json.loads(_get(
            "https://hacker-news.firebaseio.com/v0/topstories.json"
        ))[:80]
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for item_id in top_ids:
        if len(out) >= limit:
            break
        try:
            data = json.loads(_get(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            ))
        except Exception:
            continue
        title = data.get("title") or ""
        url = data.get("url") or f"https://news.ycombinator.com/item?id={item_id}"
        if not AI_KEYWORDS.search(title):
            continue
        ts = data.get("time")
        published = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            if ts else None
        )
        out.append({
            "source": "hackernews",
            "url": url,
            "title": title,
            "summary": data.get("text", "")[:500] if data.get("text") else "",
            "score": float(data.get("score", 0)),
            "tags": ["hn", "ai"],
            "published_at": published,
        })
    return out


# ─── arXiv (recent cs.AI + cs.LG) ───

def fetch_arxiv(categories: List[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
    """Recent arXiv submissions in AI/ML categories."""
    categories = categories or ["cs.AI", "cs.LG", "cs.CL"]
    query = "+OR+".join(f"cat:{c}" for c in categories)
    url = (
        f"http://export.arxiv.org/api/query?search_query={query}"
        f"&sortBy=submittedDate&sortOrder=descending&max_results={limit}"
    )
    try:
        body = _get(url, accept="application/atom+xml")
    except Exception:
        return []
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out: List[Dict[str, Any]] = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    for entry in root.findall("a:entry", ns):
        title = (entry.findtext("a:title", "", ns) or "").strip().replace("\n", " ")
        summary = (entry.findtext("a:summary", "", ns) or "").strip().replace("\n", " ")
        link = entry.findtext("a:id", "", ns) or ""
        published = entry.findtext("a:published", None, ns)
        cats = [
            c.get("term", "") for c in entry.findall("a:category", ns)
        ]
        if not title or not link:
            continue
        out.append({
            "source": "arxiv",
            "url": link,
            "title": title,
            "summary": summary[:600],
            # arxiv has no hotness signal; use recency as a proxy later
            "score": 1.0,
            "tags": ["arxiv"] + [c for c in cats if c.startswith("cs.")][:3],
            "published_at": published,
        })
    return out


# ─── GitHub trending (via search API, stdlib only) ───

def fetch_github_trending(limit: int = 20,
                          topics: List[str] = None) -> List[Dict[str, Any]]:
    """Repos created/pushed recently, ranked by stars.

    Uses the public search API (no auth needed; rate-limited to 10/min
    unauth). Pulls the top N repos pushed in the last week.
    """
    topics = topics or ["ai-agent", "llm", "agents"]
    # Simple query: pushed in last 7 days, filter by topic OR in description
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    q = f"(agent OR llm OR mcp) pushed:>={since}"
    url = (
        "https://api.github.com/search/repositories?"
        f"q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page={limit}"
    )
    try:
        data = json.loads(_get(url))
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for repo in data.get("items", [])[:limit]:
        full = repo.get("full_name") or ""
        html = repo.get("html_url") or ""
        if not full or not html:
            continue
        out.append({
            "source": "github",
            "url": html,
            "title": f"{full} — {repo.get('description','')[:120]}",
            "summary": (repo.get("description") or "")[:500],
            "score": float(repo.get("stargazers_count", 0)),
            "tags": ["github"] + [t for t in repo.get("topics", [])][:5],
            "published_at": repo.get("pushed_at"),
        })
    return out


FETCHERS: Dict[str, Callable[..., List[Dict[str, Any]]]] = {
    "hackernews": fetch_hackernews,
    "arxiv": fetch_arxiv,
    "github": fetch_github_trending,
}


def run_all(verbose: bool = False) -> Dict[str, int]:
    """Pull from every source; upsert into trends_items; return counts.

    Returns {source: new_count}.
    """
    from .store import upsert_item, init_research_tables
    init_research_tables()
    counts: Dict[str, int] = {}
    for name, fn in FETCHERS.items():
        new_rows = 0
        t0 = time.time()
        try:
            items = fn()
        except Exception as e:
            if verbose:
                print(f"[trends:{name}] fetch error: {e}")
            counts[name] = 0
            continue
        for it in items:
            try:
                if upsert_item(
                    source=it["source"],
                    url=it["url"],
                    title=it["title"],
                    summary=it.get("summary", ""),
                    score=float(it.get("score", 0)),
                    tags=it.get("tags", []),
                    published_at=it.get("published_at"),
                ):
                    new_rows += 1
            except Exception as e:
                if verbose:
                    print(f"[trends:{name}] upsert error: {e}")
        counts[name] = new_rows
        if verbose:
            print(f"[trends:{name}] fetched={len(items)} new={new_rows} "
                  f"in {time.time()-t0:.1f}s")
    return counts
