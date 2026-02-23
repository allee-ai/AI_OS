"""
web_search — Search the web via DuckDuckGo (no API key needed)
===============================================================

Actions:
    search(query, max_results)   → search results with title/url/snippet
    get_results()                → cached results from last search

Uses duckduckgo-search package. Falls back gracefully if not installed.
No API key needed — aligns with local-first philosophy.
"""

_last_results = []


def run(action: str, params: dict) -> str:
    """Execute a web_search action."""
    actions = {
        "search": _search,
        "get_results": _get_results,
    }
    
    fn = actions.get(action)
    if not fn:
        return f"Unknown action: {action}. Available: {', '.join(actions)}"
    
    return fn(params)


def _search(params: dict) -> str:
    global _last_results
    
    query = params.get("query", "")
    max_results = int(params.get("max_results", "5"))
    
    if not query:
        return "No query provided"
    
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "Web search unavailable — install: pip install duckduckgo-search"
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        _last_results = results
        
        if not results:
            return f"No results found for: {query}"
        
        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.get('title', '')}")
            lines.append(f"   {r.get('href', '')}")
            lines.append(f"   {r.get('body', '')}")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Search error: {e}"


def _get_results(params: dict) -> str:
    if not _last_results:
        return "No previous search results"
    
    lines = []
    for i, r in enumerate(_last_results, 1):
        lines.append(f"{i}. {r.get('title', '')} — {r.get('href', '')}")
    
    return "\n".join(lines)
