import json
d = json.load(open("frontend/public/demo-data.json"))
bs = d.get("GET /api/subconscious/build_state", {})
print("build_state chars:", bs.get("char_count", "MISSING"))
print("state preview:", repr(bs.get("state", "")[:50]))
for c in d.get("GET /api/conversations", []):
    print(f"  {c['title']}: {c['created_at']}")
# Check query-param variants exist
for k in ["GET /api/conversations?archived=false&limit=50", "GET /api/chat/history?limit=100"]:
    print(f"  {k}: {'YES' if k in d else 'MISSING'}")
