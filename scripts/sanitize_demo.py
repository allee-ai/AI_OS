"""Sanitize demo-data.json — scrub local paths and PII, keep real structure."""
import json
import os
import re

with open("frontend/public/demo-data.json") as f:
    data = json.load(f)

# ── Helper: recursively scrub local paths from any value ──
def scrub_paths(obj):
    if isinstance(obj, str):
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/"
        _home = os.path.expanduser("~") + "/"
        return obj.replace(_root, "").replace(_home, "~/")
    if isinstance(obj, dict):
        return {k: scrub_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_paths(v) for v in obj]
    return obj

data = scrub_paths(data)

# ── Sanitize primary_user PII in identity facts ──
pu_facts = data.get("GET /api/identity/primary_user/facts", [])
if isinstance(pu_facts, list):
    for fact in pu_facts:
        key = fact.get("key", "")
        if key == "email":
            for lv in ["l1_value", "l2_value", "l3_value"]:
                if fact.get(lv):
                    fact[lv] = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'jamie@example.com', fact[lv])
        elif key == "phone":
            for lv in ["l1_value", "l2_value", "l3_value"]:
                if fact.get(lv):
                    fact[lv] = "(555) 555-0100"

# ── Sanitize identity table view ──
ident_table = data.get("GET /api/identity/table", {})
if isinstance(ident_table, dict) and "rows" in ident_table:
    for row in ident_table["rows"]:
        if row.get("profile_id") == "primary_user":
            if row.get("key") == "email" and row.get("l1"):
                row["l1"] = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'jamie@example.com', row["l1"])
            elif row.get("key") == "phone" and row.get("l1"):
                row["l1"] = "(555) 555-0100"

# ── Sanitize introspect summary (email redaction) ──
introspect = data.get("GET /api/identity/introspect")
if isinstance(introspect, dict) and "summary" in introspect:
    introspect["summary"] = re.sub(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        'user@example.com', introspect["summary"]
    )

# ── Conversations + chat: keep demo fakes since demo DB has no chat data ──
data["GET /api/conversations"] = [
    {"session_id": "demo-001", "title": "Getting started with AI OS", "message_count": 6, "created_at": "2025-06-15T10:30:00Z", "updated_at": "2025-06-15T10:35:00Z", "archived": False, "source": "chat"},
    {"session_id": "demo-002", "title": "How the memory system works", "message_count": 4, "created_at": "2025-06-14T15:00:00Z", "updated_at": "2025-06-14T15:15:00Z", "archived": False, "source": "chat"},
    {"session_id": "demo-003", "title": "Setting up feeds and sources", "message_count": 8, "created_at": "2025-06-13T09:00:00Z", "updated_at": "2025-06-13T09:25:00Z", "archived": False, "source": "chat"},
    {"session_id": "demo-004", "title": "Fine-tuning on Apple Silicon", "message_count": 5, "created_at": "2025-06-12T20:00:00Z", "updated_at": "2025-06-12T20:20:00Z", "archived": False, "source": "chat"},
]
data["GET /api/chat/history"] = [
    {"id": "msg-001", "role": "user", "content": "What is AI OS?", "timestamp": "2025-06-15T10:30:00Z", "session_id": "demo-001"},
    {"id": "msg-002", "role": "assistant", "content": "AI OS is a local-first cognitive operating system. It gives you a personal AI agent that runs entirely on your machine \u2014 your data never leaves your device.\n\nIt has identity threads, memory consolidation, feeds integration, and subconscious loops that learn from your conversations over time.", "timestamp": "2025-06-15T10:30:05Z", "session_id": "demo-001"},
    {"id": "msg-003", "role": "user", "content": "How does the memory system work?", "timestamp": "2025-06-15T10:31:00Z", "session_id": "demo-001"},
    {"id": "msg-004", "role": "assistant", "content": "Three layers:\n\n1. **Short-term** \u2014 recent conversation turns in a buffer\n2. **Temporary facts** \u2014 extracted insights awaiting your approval\n3. **Long-term** \u2014 approved facts consolidated into identity threads\n\nThe subconscious loop processes conversations in the background, extracting facts and strengthening pathways through a potentiation system inspired by biological memory.", "timestamp": "2025-06-15T10:31:08Z", "session_id": "demo-001"},
    {"id": "msg-005", "role": "user", "content": "Can I fine-tune a model on my own data?", "timestamp": "2025-06-15T10:32:00Z", "session_id": "demo-001"},
    {"id": "msg-006", "role": "assistant", "content": "Yes! The Training page generates examples from every module \u2014 identity, philosophy, reflex, and more. It exports to JSONL format for MLX training on Apple Silicon.\n\nYou can fine-tune Qwen, Llama, or other supported models. The whole pipeline runs locally.", "timestamp": "2025-06-15T10:32:10Z", "session_id": "demo-001"},
]

# ── Agent status: use demo name ──
data["GET /api/chat/agent-status"] = {
    "status": "awake",
    "name": "Nola",
    "uptime": 86400,
    "version": "0.9.0"
}

with open("frontend/public/demo-data.json", "w") as f:
    json.dump(data, f, indent=2, default=str, ensure_ascii=False)

print(f"Sanitized. Total: {len(data)} keys, {len(json.dumps(data, indent=2)):,} bytes")
