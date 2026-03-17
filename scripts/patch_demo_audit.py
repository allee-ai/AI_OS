"""Patch demo-data.json to include demo_audit loop, notifications, and audit temp facts."""
import json
from pathlib import Path

DEMO_DATA = Path(__file__).resolve().parent.parent / "frontend" / "public" / "demo-data.json"

data = json.loads(DEMO_DATA.read_text())

# ── 1. Add demo_audit to the loops list ──────────────────────────────
loops_obj = data["GET /api/subconscious/loops"]
loop_list = loops_obj["loops"]
loop_list = [l for l in loop_list if l.get("name") != "demo_audit"]
loop_list.append({
    "name": "demo_audit",
    "status": "running",
    "interval": 900.0,
    "enabled": True,
    "context_aware": False,
    "max_errors": 3,
    "error_backoff": 2.0,
    "last_run": "2026-03-17T04:15:00.000000+00:00",
    "run_count": 3,
    "error_count": 0,
    "consecutive_errors": 0,
    "model": "kimi-k2:1t-cloud",
    "demo_data_path": "frontend/public/demo-data.json",
    "last_issues": [
        "[MEDIUM] GET /api/database/tables: returns empty tables array",
        "[MEDIUM] GET /api/form/tools: returns empty array",
        "[HIGH] GET /api/services/kernel/status: kernel shows connected:false",
    ],
})
loops_obj["loops"] = loop_list
loops_obj["count"] = len(loop_list)

# ── 2. Add sample notifications ──────────────────────────────────────
data["GET /api/subconscious/notifications"] = [
    {
        "id": 1,
        "type": "alert",
        "message": "Demo audit found 14 issue(s) in demo-data.json",
        "priority": "normal",
        "read": False,
        "dismissed": False,
        "response": None,
        "created_at": "2026-03-17T04:15:00",
    },
    {
        "id": 2,
        "type": "info",
        "message": "Goal loop proposed: Improve conversational depth tracking",
        "priority": "low",
        "read": True,
        "dismissed": False,
        "response": None,
        "created_at": "2026-03-17T03:30:00",
    },
]

# ── 3. Add audit findings as temp facts ──────────────────────────────
tf_key = "GET /api/subconscious/temp-facts"
tf_obj = data.get(tf_key, {"facts": []})
facts = tf_obj.get("facts", [])
# Remove any prior audit facts
facts = [f for f in facts if f.get("source") != "loop:demo_audit"]
facts.extend([
    {
        "id": 9001,
        "text": "[MEDIUM] GET /api/database/tables: returns empty tables array when real data expected",
        "source": "loop:demo_audit",
        "session_id": "demo_audit",
        "status": "pending_review",
        "hier_key": "demo_audit./api/database/tables",
        "created_at": "2026-03-17T04:15:00",
    },
    {
        "id": 9002,
        "text": "[HIGH] GET /api/services/kernel/status: kernel shows connected:false and 0 sessions",
        "source": "loop:demo_audit",
        "session_id": "demo_audit",
        "status": "pending_review",
        "hier_key": "demo_audit./api/services/kernel/status",
        "created_at": "2026-03-17T04:15:01",
    },
    {
        "id": 9003,
        "text": "[MEDIUM] GET /api/form/tools: returns empty array while categories are populated",
        "source": "loop:demo_audit",
        "session_id": "demo_audit",
        "status": "pending_review",
        "hier_key": "demo_audit./api/form/tools",
        "created_at": "2026-03-17T04:15:02",
    },
])
tf_obj["facts"] = facts
tf_obj["count"] = len(facts)
data[tf_key] = tf_obj

# ── Write ─────────────────────────────────────────────────────────────
DEMO_DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False))

print(f"Loops: {loops_obj['count']}")
for l in loops_obj["loops"]:
    print(f"  {l['name']}: {l['status']}")
print(f"Notifications: {len(data['GET /api/subconscious/notifications'])}")
print(f"Temp facts: {tf_obj['count']} ({len([f for f in facts if f.get('source')=='loop:demo_audit'])} from demo_audit)")
