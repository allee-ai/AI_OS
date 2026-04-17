#!/usr/bin/env python3
"""Fix chat STATE sidebar + conversation dates in demo-data.json."""
import json

with open("frontend/public/demo-data.json") as f:
    data = json.load(f)

# ── 1. Add build_state endpoint ──
STATE_BLOCK = (
    "== STATE ==\n"
    "\n"
    "[self] My internal structure\n"
    "  | Thread | Question | What I Store |\n"
    "  |--------|----------||--------------|\n"
    "  | identity | WHO | My self-model, my user, our relationship |\n"
    "  | form | WHAT | My tools, my actions, my capabilities |\n"
    "  | philosophy | WHY | My values, my ethics, my reasoning style |\n"
    "  | reflex | HOW | My learned patterns, my shortcuts |\n"
    "  | log | WHEN/WHERE | My event timeline, my session history |\n"
    "  | linking_core | WHICH | My concept graph, my relevance scoring |\n"
    "  | Module | | |\n"
    "  | chat | RECALL | Past conversations, discussion history |\n"
    "  | workspace | CONTEXT | Files, documents, project state |\n"
    "  graph: 847 links, ~126 concepts, avg_strength=0.42\n"
    "\n"
    "[identity] Who I am (machine), who you are (user), and who we know\n"
    "  context_level: 3\n"
    "  fact_count: 8\n"
    "identity.machine.name: Nola\n"
    "identity.machine.role: AI assistant and cognitive companion\n"
    "identity.machine.architecture: AI OS \u2014 modular cognitive architecture with six threads\n"
    "identity.machine.version: 0.2.0\n"
    "identity.primary_user.name: Jamie\n"
    "identity.primary_user.location: Portland, OR\n"
    "identity.primary_user.interests: AI research, music production, local-first software\n"
    "identity.primary_user.projects: Building AI OS as a personal cognitive OS\n"
    "\n"
    "[philosophy] My values, ethics, and reasoning style\n"
    "  context_level: 2\n"
    "  fact_count: 5\n"
    "philosophy.values.core: Curiosity, honesty, growth, helpfulness\n"
    "philosophy.ethics.privacy: User data never leaves the local machine\n"
    "philosophy.ethics.autonomy: User always has final say over memory and behavior\n"
    "philosophy.reasoning.style: Think step-by-step, show reasoning, admit uncertainty\n"
    "philosophy.identity.persistence: Consistent self across conversations via STATE injection\n"
    "\n"
    "[form] Tool use, actions, and capabilities\n"
    "  context_level: 2\n"
    "  fact_count: 4\n"
    "form.tools.memory_identity: Read and update identity facts (get_profile, set_fact, list_facts)\n"
    "form.tools.memory_philosophy: Read and update beliefs and values\n"
    "form.tools.linking_core: Concept graph operations (fire_link, query_similar, get_graph)\n"
    "form.tools.subconscious: Background loops, temp facts, potentiation\n"
    "\n"
    "[reflex] Learned patterns and shortcuts\n"
    "  context_level: 1\n"
    "  fact_count: 2\n"
    "reflex.greeting: Open with warmth, reference recent context if available\n"
    "reflex.safety: Never fabricate facts about the user; say \"I don't know\" when uncertain\n"
    "\n"
    "[log] Temporal awareness and history\n"
    "  context_level: 2\n"
    "  fact_count: 3\n"
    "log.session.start: 2026-03-21T10:00:00Z\n"
    "log.session.duration: Session active for 5m\n"
    "log.recent.topic: Exploring the AI OS demo\n"
    "\n"
    "[linking_core] Concept graph and relevance scoring\n"
    "  context_level: 1\n"
    "  fact_count: 2\n"
    "linking_core.stats: 126 concepts, 847 links, avg_strength 0.42\n"
    "linking_core.top_concepts: identity, memory, curiosity, growth, architecture\n"
    "\n"
    "== END STATE =="
)

data["GET /api/subconscious/build_state"] = {
    "state": STATE_BLOCK,
    "char_count": len(STATE_BLOCK),
    "query": "",
}

# ── 2. Fix conversation dates to March 2026 ──
convos = data.get("GET /api/conversations", [])
new_dates = [
    ("2026-03-21T10:30:00Z", "2026-03-21T10:35:00Z"),
    ("2026-03-20T15:00:00Z", "2026-03-20T15:15:00Z"),
    ("2026-03-19T09:00:00Z", "2026-03-19T09:25:00Z"),
    ("2026-03-18T20:00:00Z", "2026-03-18T20:20:00Z"),
]
for i, convo in enumerate(convos):
    if i < len(new_dates):
        convo["created_at"] = new_dates[i][0]
        convo["updated_at"] = new_dates[i][1]

# Add sorted query-param variants (SW sorts alphabetically: archived < limit)
data["GET /api/conversations?archived=false&limit=50"] = convos
data["GET /api/conversations?archived=true&limit=50"] = []

# ── 3. Fix chat history message timestamps ──
history = data.get("GET /api/chat/history", [])
base_times = [
    "2026-03-21T10:30:00Z",
    "2026-03-21T10:30:05Z",
    "2026-03-21T10:31:00Z",
    "2026-03-21T10:31:08Z",
    "2026-03-21T10:32:00Z",
    "2026-03-21T10:32:10Z",
]
for i, msg in enumerate(history):
    if i < len(base_times):
        msg["timestamp"] = base_times[i]

# Add limit variant
data["GET /api/chat/history?limit=100"] = history

with open("frontend/public/demo-data.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"build_state: {len(STATE_BLOCK)} chars")
print(f"Conversations: {len(convos)} updated to March 2026")
print(f"Chat history: {len(history)} messages timestamped")
