#!/usr/bin/env python3
"""
Capture real API responses from the running server to build demo-data.json.
Hits every GET endpoint the frontend uses and saves the actual responses.
"""

import json
import requests
import sys

BASE = "http://127.0.0.1:8000"

# All GET endpoints the frontend fetches.
# For parameterized routes, we provide one concrete example.
ENDPOINTS = [
    # App / setup
    ("GET", "/api/db-mode/mode"),
    ("GET", "/api/models/setup/status"),

    # Chat
    ("GET", "/api/chat/agent-status"),
    ("GET", "/api/chat/history?limit=100"),
    ("GET", "/api/conversations?limit=50&archived=false"),
    ("GET", "/api/conversations?limit=50&archived=true"),
    ("GET", "/api/conversations/summary/prompt"),

    # Models
    ("GET", "/api/models"),
    ("GET", "/api/models/library"),
    ("GET", "/api/models/providers"),
    ("GET", "/api/models/current"),

    # Threads page
    ("GET", "/api/subconscious/threads"),

    # Identity
    ("GET", "/api/identity"),
    ("GET", "/api/identity/types"),
    ("GET", "/api/identity/fact-types"),
    ("GET", "/api/identity/table"),
    ("GET", "/api/identity/introspect"),

    # Philosophy
    ("GET", "/api/philosophy"),
    ("GET", "/api/philosophy/types"),
    ("GET", "/api/philosophy/fact-types"),
    ("GET", "/api/philosophy/table"),

    # Reflex
    ("GET", "/api/reflex/all"),
    ("GET", "/api/reflex/stats"),
    ("GET", "/api/reflex/triggers"),
    ("GET", "/api/reflex/protocols"),

    # Form / tools
    ("GET", "/api/form/tools"),
    ("GET", "/api/form/categories"),

    # Linking core
    ("GET", "/api/linking_core/cooccurrence"),
    ("GET", "/api/linking_core/graph"),

    # Log
    ("GET", "/api/log/tables"),
    ("GET", "/api/log/events?limit=20"),

    # Subconscious
    ("GET", "/api/subconscious/loops"),
    ("GET", "/api/subconscious/temp-facts"),
    ("GET", "/api/subconscious/potentiation"),
    ("GET", "/api/subconscious/queue"),
    ("GET", "/api/subconscious/loops/custom"),
    ("GET", "/api/subconscious/goals"),
    ("GET", "/api/subconscious/notifications?limit=20"),
    ("GET", "/api/subconscious/improvements"),
    ("GET", "/api/subconscious/health"),
    ("GET", "/api/subconscious/state"),
    ("GET", "/api/subconscious/context"),

    # Feeds
    ("GET", "/api/feeds/sources"),
    ("GET", "/api/feeds/templates"),
    ("GET", "/api/feeds/events/triggers"),
    ("GET", "/api/feeds/integrations"),

    # Docs
    ("GET", "/api/docs"),
    ("GET", "/api/docs/content?path=README.md"),

    # Workspace
    ("GET", "/api/workspace/files"),
    ("GET", "/api/workspace/stats"),
    ("GET", "/api/workspace/recent?limit=10"),
    ("GET", "/api/workspace/pinned"),
    ("GET", "/api/workspace/notes"),
    ("GET", "/api/workspace/summary/prompt"),

    # Eval
    ("GET", "/api/eval/benchmarks"),
    ("GET", "/api/eval/models"),
    ("GET", "/api/eval/evals"),
    ("GET", "/api/eval/runs?limit=20"),
    ("GET", "/api/eval/comparisons?limit=20"),

    # Finetune
    ("GET", "/api/finetune/modules"),
    ("GET", "/api/finetune/models"),
    ("GET", "/api/finetune/runs"),
    ("GET", "/api/finetune/load/status"),
    ("GET", "/api/finetune/generate/targets"),
    ("GET", "/api/finetune/unified?page=1&per_page=10"),

    # Services / Settings
    ("GET", "/api/services/"),
    ("GET", "/api/services/kernel/status"),
    ("GET", "/api/services/memory/stats"),
    ("GET", "/api/services/consolidation/pending"),
    ("GET", "/api/settings"),

    # MCP
    ("GET", "/api/mcp/servers"),
    ("GET", "/api/mcp/catalog"),
    ("GET", "/api/mcp/connections"),
]

# Also capture some POST responses that the frontend uses inline
POST_ENDPOINTS = [
    ("POST", "/api/chat/message", {"message": "Hello, this is a demo.", "session_id": None}),
]


def make_key(method: str, path: str, keep_query: bool = False) -> str:
    """Build the service-worker lookup key. Strip query params unless keep_query."""
    if keep_query:
        return f"{method} {path}"
    clean = path.split("?")[0]
    return f"{method} {clean}"


def capture():
    results = {}
    errors = []

    print(f"Capturing {len(ENDPOINTS)} GET endpoints...\n")

    for method, path in ENDPOINTS:
        key = make_key(method, path)
        url = f"{BASE}{path}"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    results[key] = data
                    size = len(json.dumps(data))
                    print(f"  ✓ {key}  ({size:,} bytes)")
                except json.JSONDecodeError:
                    # Text response
                    results[key] = resp.text
                    print(f"  ✓ {key}  (text, {len(resp.text)} bytes)")
            else:
                errors.append((key, resp.status_code))
                print(f"  ✗ {key}  → {resp.status_code}")
        except requests.RequestException as e:
            errors.append((key, str(e)))
            print(f"  ✗ {key}  → {e}")

    # Also grab parameterized routes using real IDs from collected data

    # Identity profiles → grab ALL profiles' facts (each gets its own key)
    identity_profiles = results.get("GET /api/identity")
    if isinstance(identity_profiles, list) and identity_profiles:
        for profile in identity_profiles:
            pid = profile.get("profile_id") or profile.get("id")
            if not pid:
                continue
            url = f"{BASE}/api/identity/{pid}/facts"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    results[f"GET /api/identity/{pid}/facts"] = resp.json()
                    print(f"  ✓ GET /api/identity/{pid}/facts")
            except Exception:
                pass

    # Philosophy profiles → grab ALL profiles' facts
    phil_profiles = results.get("GET /api/philosophy")
    if isinstance(phil_profiles, list) and phil_profiles:
        for profile in phil_profiles:
            pid = profile.get("profile_id") or profile.get("id")
            if not pid:
                continue
            url = f"{BASE}/api/philosophy/{pid}/facts"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    results[f"GET /api/philosophy/{pid}/facts"] = resp.json()
                    print(f"  ✓ GET /api/philosophy/{pid}/facts")
            except Exception:
                pass

    # Conversations → grab first conversation
    convos = results.get("GET /api/conversations")
    if isinstance(convos, list) and convos:
        sid = convos[0].get("session_id") or convos[0].get("id")
        if sid:
            url = f"{BASE}/api/conversations/{sid}?limit=20"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    results["GET /api/conversations/:id"] = resp.json()
                    print(f"  ✓ GET /api/conversations/:id  (sample: {sid})")
            except Exception:
                pass

    # Finetune module sections
    ft_modules = results.get("GET /api/finetune/modules")
    if isinstance(ft_modules, dict) and ft_modules.get("modules"):
        mod_name = ft_modules["modules"][0].get("name", "identity")
        url = f"{BASE}/api/finetune/modules/{mod_name}/sections"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                results["GET /api/finetune/modules/:name/sections"] = resp.json()
                print(f"  ✓ GET /api/finetune/modules/:name/sections  (sample: {mod_name})")
        except Exception:
            pass

    # Feeds sources → grab first source detail
    feeds_sources = results.get("GET /api/feeds/sources")
    if isinstance(feeds_sources, list) and feeds_sources:
        src_name = feeds_sources[0].get("name")
        if src_name:
            url = f"{BASE}/api/feeds/sources/{src_name}"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    results["GET /api/feeds/sources/:name"] = resp.json()
                    print(f"  ✓ GET /api/feeds/sources/:name  (sample: {src_name})")
            except Exception:
                pass

    # Thread readmes
    for thread in ["identity", "philosophy", "reflex", "form", "log", "linking_core"]:
        url = f"{BASE}/api/{thread}/readme"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                results[f"GET /api/{thread}/readme"] = resp.json()
                print(f"  ✓ GET /api/{thread}/readme")
        except Exception:
            pass

    # Docs — capture all individual doc pages with query-param keys
    docs_tree = results.get("GET /api/docs")
    if isinstance(docs_tree, dict) and docs_tree.get("tree"):
        def collect_paths(node):
            paths = []
            if not node.get("is_folder"):
                paths.append(node["path"])
            for child in node.get("children", []):
                paths.extend(collect_paths(child))
            return paths

        doc_paths = collect_paths(docs_tree["tree"])
        print(f"\n  Capturing {len(doc_paths)} individual docs...")
        for dp in doc_paths:
            from urllib.parse import quote
            url = f"{BASE}/api/docs/content?path={quote(dp)}"
            qkey = f"GET /api/docs/content?path={quote(dp)}"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    results[qkey] = data
                    size = len(json.dumps(data))
                    print(f"    ✓ {dp}  ({size:,} bytes)")
            except Exception as e:
                print(f"    ✗ {dp} → {e}")

    # Add static POST responses the demo needs
    results["POST /api/chat/message"] = {
        "id": "msg-demo",
        "role": "assistant",
        "content": "This is a demo — chat is view-only in this mode. Try exploring the other pages to see how AI OS works!",
        "timestamp": "2025-01-15T12:00:00Z"
    }
    results["POST /api/chat/start-session"] = {"session_id": "demo-session", "created": True}
    results["POST /api/chat/clear"] = {"cleared": True}
    results["POST /api/db-mode/mode"] = {"mode": "demo"}

    # Write output
    out_path = "frontend/public/demo-data.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    total = len(results)
    print(f"\n{'='*50}")
    print(f"Captured {total} endpoints → {out_path}")
    if errors:
        print(f"{len(errors)} errors:")
        for key, err in errors:
            print(f"  {key} → {err}")
    print(f"File size: {len(json.dumps(results, indent=2)):,} bytes")


if __name__ == "__main__":
    # Quick check server is up
    try:
        r = requests.get(f"{BASE}/api/chat/agent-status", timeout=3)
        r.raise_for_status()
    except Exception:
        print("Server not running at localhost:8000. Start it first:")
        print("  python cli.py serve")
        sys.exit(1)

    capture()
