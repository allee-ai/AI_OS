"""Merge hardcoded fallback data for endpoints that timed out."""
import json

with open("frontend/public/demo-data.json") as f:
    data = json.load(f)

print(f"Current keys: {len(data)}")

fallbacks = {
    "GET /api/services/": [
        {"id": "memory", "name": "Memory", "description": "Fact extraction and storage", "icon": "\U0001f9e0", "status": "running", "message": "OK", "config": {"enabled": True, "settings": {}}},
        {"id": "subconscious", "name": "Subconscious", "description": "Background processing loops", "icon": "\U0001f300", "status": "running", "message": "10 loops active", "config": {"enabled": True, "settings": {}}},
        {"id": "feeds", "name": "Feeds", "description": "RSS and notification polling", "icon": "\U0001f4e1", "status": "running", "message": "OK", "config": {"enabled": True, "settings": {}}},
        {"id": "kernel", "name": "Kernel", "description": "MCP tool server connections", "icon": "\u2699\ufe0f", "status": "stopped", "message": "No active connections", "config": {"enabled": False, "settings": {}}}
    ],
    "GET /api/services/kernel/status": {"connected": False, "sessions": 0},
    "GET /api/services/memory/stats": {"total_facts": 60, "short_term": 18, "long_term": 42},
    "GET /api/services/consolidation/pending": {"count": 0, "facts": []},
    "GET /api/settings": {
        "groups": {
            "server": [
                {"key": "HOST", "default": "0.0.0.0", "group": "server", "label": "Host", "type": "text", "value": "0.0.0.0", "display": "0.0.0.0"},
                {"key": "PORT", "default": "8000", "group": "server", "label": "Port", "type": "text", "value": "8000", "display": "8000"}
            ],
            "provider": [
                {"key": "LLM_PROVIDER", "default": "ollama", "group": "provider", "label": "LLM Provider", "type": "select", "value": "ollama", "display": "ollama"},
                {"key": "OLLAMA_MODEL", "default": "qwen2.5:7b", "group": "provider", "label": "Ollama Model", "type": "text", "value": "qwen2.5:7b", "display": "qwen2.5:7b"}
            ],
            "kernel": [
                {"key": "MCP_ENABLED", "default": "false", "group": "kernel", "label": "MCP Enabled", "type": "toggle", "value": "false", "display": "false"}
            ]
        }
    },
    "GET /api/mcp/servers": {"servers": []},
    "GET /api/mcp/catalog": {"servers": [
        {"name": "filesystem", "description": "Read and write files", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem"], "category": "files", "installed": False},
        {"name": "web-search", "description": "Search the web", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-web-search"], "category": "research", "installed": False}
    ]},
    "GET /api/mcp/connections": {"connections": []},
    "GET /api/finetune/unified": {"examples": [], "total": 0, "pages": 0},
    "GET /api/database/tables": {"tables": []},
    "GET /api/database/threads-summary": {"threads": []},
    "GET /api/database/identity-hea": {"modules": []},
    "GET /api/feeds/integrations": {"integrations": []}
}

# Only add if not already present (don't overwrite real data)
added = 0
for key, value in fallbacks.items():
    if key not in data:
        data[key] = value
        added += 1
        print(f"  + {key}")
    else:
        print(f"  = {key} (already exists)")

with open("frontend/public/demo-data.json", "w") as f:
    json.dump(data, f, indent=2, default=str, ensure_ascii=False)

print(f"\nAdded {added} fallbacks. Total: {len(data)} keys")
print(f"File size: {len(json.dumps(data, indent=2, default=str)):,} bytes")
