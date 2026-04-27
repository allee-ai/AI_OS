"""Find candidate arXiv endorsers for the substrate-invariant paper.

Pulls recent cs.AI submissions from the public arXiv API, scores each by
topical overlap with our abstract, then surfaces authors as candidate
endorsers ranked by:
  - how many qualifying recent cs.AI submissions they have (eligibility)
  - average topical-overlap score across those submissions (relevance)
  - recency of latest submission

Writes ranked candidates to research/papers/substrate_invariant/endorsers.md.

The arXiv API does NOT return author email addresses — only author names
and affiliations parsed from the PDF metadata. We surface those names + the
arxiv abstract page URL so a human can look up each candidate's lab page
and find an email. We do not fabricate addresses.

Run: .venv/bin/python scripts/find_endorser.py
"""
from __future__ import annotations

import re
import sys
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

REPO = Path(__file__).resolve().parent.parent
PAPER_DIR = REPO / "research" / "papers" / "substrate_invariant"
ABSTRACT_PATH = PAPER_DIR / "paper.md"
OUT_PATH = PAPER_DIR / "endorsers.md"

ARXIV_API = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

# Topical keyword anchors derived from the paper. Each anchor is a regex
# pattern matched against title + abstract; weights reflect how
# diagnostic the term is for our specific framework.
TOPIC_ANCHORS: list[tuple[str, float]] = [
    (r"\bmemgpt\b",                              5.0),
    (r"\bcoala\b",                               5.0),
    (r"cognitive architecture",                  4.0),
    (r"language agent",                          4.0),
    (r"persistent memory",                       4.0),
    (r"long[- ]?term memory",                    3.5),
    (r"external memory",                         3.5),
    (r"memory[- ]augmented",                     3.0),
    (r"\bagent\b.*\b(state|memory|persistent)\b", 3.0),
    (r"react\b.*language model",                 2.5),
    (r"chain[- ]of[- ]thought",                  2.0),
    (r"self[- ]reflect",                         3.0),
    (r"reflexion",                               3.0),
    (r"working memory",                          2.5),
    (r"identity",                                2.5),
    (r"continual learning",                      2.0),
    (r"in[- ]context learning",                  1.5),
    (r"retrieval[- ]augmented",                  2.0),
    (r"scratchpad",                              2.5),
    (r"meta[- ]cognition",                       2.5),
    (r"theory of mind",                          1.5),
    (r"small[- ]?language[- ]?model",            2.0),
    (r"compute[- ]optimal",                      1.5),
    (r"scaling law",                             1.5),
    (r"falsifiable|preregister",                 2.5),
    (r"substrate",                               4.0),
    (r"iteration[- ]rate",                       4.0),
    (r"clocked",                                 3.0),
    (r"introspect",                              2.5),
    (r"self[- ]model",                           3.0),
    (r"dynamical[- ]systems? cognition",         3.0),
    (r"global workspace",                        2.5),
    (r"predictive processing",                   2.0),
]

# Search queries to fan out across cs.AI for likely-relevant papers.
SEARCH_QUERIES = [
    'cat:cs.AI AND (abs:"language agent" OR abs:"cognitive architecture")',
    'cat:cs.AI AND (abs:"persistent memory" OR abs:"long-term memory")',
    'cat:cs.AI AND (abs:"MemGPT" OR abs:"CoALA" OR abs:"external memory")',
    'cat:cs.AI AND (abs:"self-reflection" OR abs:"reflexion")',
    'cat:cs.AI AND (abs:"agent" AND abs:"memory" AND abs:"LLM")',
    'cat:cs.AI AND (abs:"small language model" AND abs:"agent")',
]
PER_QUERY = 50  # arXiv API: max_results
SLEEP_BETWEEN = 3  # arXiv asks for ≥3s between calls


def fetch_query(query: str) -> list[dict]:
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": str(PER_QUERY),
    }
    with httpx.Client(timeout=30.0, follow_redirects=True,
                      headers={"User-Agent": "AI_OS/find_endorser"}) as client:
        r = client.get(f"{ARXIV_API}?{urllib.parse.urlencode(params)}")
        r.raise_for_status()
        body = r.text
        body = r.read().decode("utf-8", errors="replace")
    root = ET.fromstring(body)
    out: list[dict] = []
    for entry in root.findall("a:entry", NS):
        arxiv_id_full = (entry.findtext("a:id", "", NS) or "").strip()
        # id form: http://arxiv.org/abs/2401.12345v1
        m = re.search(r"abs/([\w\.\-/]+?)(?:v\d+)?$", arxiv_id_full)
        arxiv_id = m.group(1) if m else arxiv_id_full
        title = re.sub(r"\s+", " ", (entry.findtext("a:title", "", NS) or "")).strip()
        summary = re.sub(r"\s+", " ", (entry.findtext("a:summary", "", NS) or "")).strip()
        published = (entry.findtext("a:published", "", NS) or "").strip()
        authors = []
        for a in entry.findall("a:author", NS):
            name = (a.findtext("a:name", "", NS) or "").strip()
            if name:
                authors.append(name)
        out.append({
            "id": arxiv_id,
            "url": f"https://arxiv.org/abs/{arxiv_id}",
            "title": title,
            "summary": summary,
            "published": published,
            "authors": authors,
        })
    return out


def score_paper(paper: dict) -> tuple[float, list[str]]:
    blob = (paper["title"] + " " + paper["summary"]).lower()
    score = 0.0
    hits: list[str] = []
    for pattern, weight in TOPIC_ANCHORS:
        if re.search(pattern, blob):
            score += weight
            hits.append(pattern)
    return score, hits


def collect() -> list[dict]:
    seen: dict[str, dict] = {}
    for q in SEARCH_QUERIES:
        print(f"  querying: {q[:80]}…", flush=True)
        try:
            papers = fetch_query(q)
        except Exception as e:
            print(f"  ! query failed: {e}")
            continue
        for p in papers:
            if p["id"] not in seen:
                seen[p["id"]] = p
        time.sleep(SLEEP_BETWEEN)
    return list(seen.values())


def rank_authors(papers: list[dict]) -> list[dict]:
    by_author: dict[str, dict] = defaultdict(lambda: {
        "papers": [],
        "total_score": 0.0,
        "max_score": 0.0,
        "latest": "",
        "n_qualifying": 0,
    })
    for p in papers:
        sc, hits = score_paper(p)
        if sc <= 0:
            continue
        for a in p["authors"]:
            row = by_author[a]
            row["papers"].append({
                "id": p["id"], "url": p["url"], "title": p["title"],
                "score": sc, "hits": hits, "published": p["published"],
            })
            row["total_score"] += sc
            row["max_score"] = max(row["max_score"], sc)
            if p["published"] > row["latest"]:
                row["latest"] = p["published"]
            row["n_qualifying"] += 1
    ranked = []
    for name, row in by_author.items():
        # Composite ranking: must have ≥1 qualifying paper. Weight by total
        # topical score, with a small bonus for multi-paper presence (proxy
        # for cs.AI eligibility) and recency.
        recency_bonus = 1.0 if row["latest"] >= "2025" else 0.5
        eligibility = min(row["n_qualifying"], 5) / 5.0
        composite = row["total_score"] * (0.5 + 0.5 * eligibility) * recency_bonus
        ranked.append({
            "name": name,
            "composite": composite,
            "n_papers": row["n_qualifying"],
            "total_score": row["total_score"],
            "max_score": row["max_score"],
            "latest": row["latest"][:10],
            "papers": sorted(row["papers"], key=lambda x: -x["score"])[:3],
        })
    ranked.sort(key=lambda x: -x["composite"])
    return ranked


def write_report(ranked: list[dict], n_papers: int) -> None:
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# arXiv cs.AI Endorser Candidates")
    lines.append("")
    lines.append(f"Generated by `scripts/find_endorser.py` over **{n_papers} recent cs.AI papers** "
                 "fetched from the public arXiv API and scored against the substrate-invariant "
                 "abstract's topical anchors.")
    lines.append("")
    lines.append("**arXiv endorsement rules (as of 2026):** any author with ≥2 cs.AI submissions "
                 "in the last 5 years, where each submission is ≥3 months old, is eligible to "
                 "endorse a first-time submitter. The composite ranking below proxies eligibility "
                 "by counting qualifying recent papers; verify on each candidate's arXiv author "
                 "page before contacting.")
    lines.append("")
    lines.append("**No email addresses are listed.** arXiv does not expose them. For each "
                 "candidate, look up their lab page or institutional directory.")
    lines.append("")
    lines.append("## Top candidates")
    lines.append("")
    for i, r in enumerate(ranked[:25], 1):
        lines.append(f"### {i}. {r['name']}")
        lines.append(f"- composite: **{r['composite']:.1f}** "
                     f"(papers: {r['n_papers']}, total topical score: {r['total_score']:.1f}, "
                     f"max single-paper score: {r['max_score']:.1f}, latest: {r['latest']})")
        lines.append("- top relevant papers:")
        for p in r["papers"]:
            lines.append(f"  - [{p['title']}]({p['url']}) "
                         f"({p['published'][:10]}, score {p['score']:.1f})")
        lines.append("")
    lines.append("## How to use this list")
    lines.append("")
    lines.append("1. Pick the highest-ranked candidate whose work you can name a specific "
                 "intellectual debt to.")
    lines.append("2. Open that candidate's institutional page (university directory, lab site, "
                 "or Google Scholar profile) and find their email.")
    lines.append("3. Open `Drafts` in Proton, edit the saved endorsement-request email — fill "
                 "the `To:` field, optionally add one sentence referencing the candidate's "
                 "specific paper that informed your framing — and send.")
    lines.append("4. If no reply within a week, try the next candidate. Endorsement asks are "
                 "low-stakes; people decline silently rather than rudely.")
    lines.append("")
    OUT_PATH.write_text("\n".join(lines))
    print(f"\nwrote {OUT_PATH} ({len(ranked)} authors ranked)")


def main() -> None:
    print("[1/3] fetching recent cs.AI papers from arXiv API …")
    papers = collect()
    print(f"  collected {len(papers)} unique papers")
    print("[2/3] scoring + ranking authors …")
    ranked = rank_authors(papers)
    print(f"  ranked {len(ranked)} authors with ≥1 topical hit")
    print("[3/3] writing report …")
    write_report(ranked, len(papers))


if __name__ == "__main__":
    main()
