"""Sanitize demo-data.json — replace real personal data with demo content."""
import json
import re

with open("frontend/public/demo-data.json") as f:
    data = json.load(f)

# ── Identity table: replace real facts with demo ones ──
data["GET /api/identity/table"] = {
    "columns": ["key", "metadata_type", "metadata_desc", "l1", "l2", "l3", "weight"],
    "rows": [
        {"key": "name", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "Alex Demo", "l2": None, "l3": None, "weight": 0.7, "profile_id": "primary_user"},
        {"key": "occupation", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "Software Engineer", "l2": "Works on AI tools and developer productivity", "l3": None, "weight": 0.7, "profile_id": "primary_user"},
        {"key": "location", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "San Francisco, CA", "l2": None, "l3": None, "weight": 0.6, "profile_id": "primary_user"},
        {"key": "preferred_language", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "Python", "l2": "Also uses TypeScript for frontend", "l3": None, "weight": 0.8, "profile_id": "primary_user"},
        {"key": "editor", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "VS Code", "l2": None, "l3": None, "weight": 0.7, "profile_id": "primary_user"},
        {"key": "communication_style", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "Direct and concise", "l2": "Prefers bullet points over paragraphs", "l3": None, "weight": 0.75, "profile_id": "primary_user"},
        {"key": "interests", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "AI/ML, cognitive science, open source", "l2": "Reads arxiv papers on memory architectures", "l3": None, "weight": 0.65, "profile_id": "primary_user"},
        {"key": "os", "metadata_type": "user", "metadata_desc": "Primary User", "l1": "macOS", "l2": "M-series MacBook", "l3": None, "weight": 0.6, "profile_id": "primary_user"},
        {"key": "coffee", "metadata_type": "user", "metadata_desc": "Preferences", "l1": "Black, no sugar", "l2": None, "l3": None, "weight": 0.5, "profile_id": "preferences"},
        {"key": "work_hours", "metadata_type": "user", "metadata_desc": "Preferences", "l1": "Night owl — most productive after 10pm", "l2": None, "l3": None, "weight": 0.55, "profile_id": "preferences"},
        {"key": "music", "metadata_type": "user", "metadata_desc": "Preferences", "l1": "Lo-fi beats while coding", "l2": None, "l3": None, "weight": 0.45, "profile_id": "preferences"},
        {"key": "current_project", "metadata_type": "user", "metadata_desc": "Goals", "l1": "Building AI OS", "l2": "Local-first personal AI agent", "l3": None, "weight": 0.9, "profile_id": "goals"},
        {"key": "learning_goal", "metadata_type": "user", "metadata_desc": "Goals", "l1": "Fine-tuning small language models", "l2": "MLX on Apple Silicon", "l3": None, "weight": 0.7, "profile_id": "goals"},
    ]
}

# ── Identity profiles ──
data["GET /api/identity"] = [
    {"profile_id": "primary_user", "type_name": "self", "display_name": "Primary User", "trust_level": 1.0, "context_priority": 10, "can_edit": True, "protected": False, "fact_count": 8},
    {"profile_id": "preferences", "type_name": "self", "display_name": "Preferences", "trust_level": 0.9, "context_priority": 8, "can_edit": True, "protected": False, "fact_count": 3},
    {"profile_id": "goals", "type_name": "self", "display_name": "Goals", "trust_level": 0.85, "context_priority": 7, "can_edit": True, "protected": False, "fact_count": 2},
]

# ── Identity introspect ──
data["GET /api/identity/introspect"] = {
    "summary": "The user is a software engineer building AI OS, a local-first personal AI system. They prefer Python and TypeScript, work on macOS, and are interested in AI, cognitive science, and memory architectures. Communication style is direct and concise. Night owl who codes with lo-fi music.",
    "confidence": 0.85,
    "fact_count": 13,
    "profile_count": 3
}

# ── Philosophy table ──
data["GET /api/philosophy/table"] = {
    "columns": ["key", "metadata_type", "metadata_desc", "l1", "l2", "l3", "weight"],
    "rows": [
        {"key": "privacy", "metadata_type": "belief", "metadata_desc": "Ethics", "l1": "Privacy is a fundamental right, not a feature", "l2": "Data should stay on device by default", "l3": None, "weight": 0.95, "profile_id": "ethics"},
        {"key": "open_source", "metadata_type": "belief", "metadata_desc": "Ethics", "l1": "Open source is a public good", "l2": "Contributing back is important", "l3": None, "weight": 0.9, "profile_id": "ethics"},
        {"key": "simplicity", "metadata_type": "belief", "metadata_desc": "Design", "l1": "Simplicity over cleverness", "l2": "Code should be readable first", "l3": None, "weight": 0.85, "profile_id": "design"},
        {"key": "local_first", "metadata_type": "belief", "metadata_desc": "Design", "l1": "Local-first > cloud-first", "l2": "Users should own their data and compute", "l3": None, "weight": 0.92, "profile_id": "design"},
        {"key": "iteration", "metadata_type": "belief", "metadata_desc": "Process", "l1": "Ship early, iterate fast", "l2": "Perfect is the enemy of good", "l3": None, "weight": 0.8, "profile_id": "process"},
    ]
}

# ── Philosophy profiles ──
data["GET /api/philosophy"] = [
    {"profile_id": "ethics", "type_name": "philosophy", "display_name": "Ethics", "trust_level": 0.9, "context_priority": 6, "can_edit": True, "protected": False, "fact_count": 2},
    {"profile_id": "design", "type_name": "philosophy", "display_name": "Design Philosophy", "trust_level": 0.85, "context_priority": 5, "can_edit": True, "protected": False, "fact_count": 2},
    {"profile_id": "process", "type_name": "philosophy", "display_name": "Process", "trust_level": 0.8, "context_priority": 4, "can_edit": True, "protected": False, "fact_count": 1},
]

# ── Temp facts: replace with demo extractions ──
data["GET /api/subconscious/temp-facts"] = {
    "recent": [
        {"id": 1, "text": "User prefers dark mode interfaces", "status": "pending", "source": "conversation", "session_id": "demo-001", "confidence_score": 0.82, "hier_key": None, "timestamp": "2025-06-15T10:30:10Z"},
        {"id": 2, "text": "Interested in running models under 8GB RAM", "status": "pending", "source": "conversation", "session_id": "demo-001", "confidence_score": 0.78, "hier_key": None, "timestamp": "2025-06-15T10:31:05Z"},
        {"id": 3, "text": "Uses SQLite for local data storage", "status": "approved", "source": "conversation", "session_id": "demo-002", "confidence_score": 0.91, "hier_key": None, "timestamp": "2025-06-14T15:05:00Z"},
        {"id": 4, "text": "Prefers FastAPI for Python web servers", "status": "approved", "source": "conversation", "session_id": "demo-002", "confidence_score": 0.88, "hier_key": None, "timestamp": "2025-06-14T15:10:00Z"},
        {"id": 5, "text": "Watches 3Blue1Brown for math intuition", "status": "rejected", "source": "conversation", "session_id": "demo-003", "confidence_score": 0.55, "hier_key": None, "timestamp": "2025-06-13T09:20:00Z"},
    ],
    "by_status": {"pending": 2, "approved": 15, "rejected": 3}
}

# ── Linking core graph: trim to reasonable demo size ──
data["GET /api/linking_core/graph"] = {
    "nodes": [
        {"id": "python", "label": "Python", "weight": 20},
        {"id": "typescript", "label": "TypeScript", "weight": 15},
        {"id": "ai", "label": "AI", "weight": 18},
        {"id": "privacy", "label": "Privacy", "weight": 12},
        {"id": "local-first", "label": "Local-first", "weight": 14},
        {"id": "memory", "label": "Memory", "weight": 11},
        {"id": "identity", "label": "Identity", "weight": 9},
        {"id": "cognitive-science", "label": "Cognitive Science", "weight": 8},
        {"id": "sqlite", "label": "SQLite", "weight": 7},
        {"id": "fine-tuning", "label": "Fine-tuning", "weight": 10},
        {"id": "open-source", "label": "Open Source", "weight": 13},
        {"id": "macos", "label": "macOS", "weight": 6},
    ],
    "edges": [
        {"source": "python", "target": "ai", "weight": 0.92},
        {"source": "python", "target": "typescript", "weight": 0.65},
        {"source": "ai", "target": "memory", "weight": 0.85},
        {"source": "ai", "target": "cognitive-science", "weight": 0.78},
        {"source": "privacy", "target": "local-first", "weight": 0.95},
        {"source": "memory", "target": "identity", "weight": 0.80},
        {"source": "local-first", "target": "sqlite", "weight": 0.72},
        {"source": "ai", "target": "fine-tuning", "weight": 0.75},
        {"source": "open-source", "target": "privacy", "weight": 0.68},
        {"source": "fine-tuning", "target": "macos", "weight": 0.60},
    ]
}

# ── Linking core cooccurrence ──
data["GET /api/linking_core/cooccurrence"] = {
    "pairs": [
        {"concept_a": "privacy", "concept_b": "local-first", "count": 14, "strength": 0.95},
        {"concept_a": "python", "concept_b": "ai", "count": 11, "strength": 0.92},
        {"concept_a": "memory", "concept_b": "identity", "count": 8, "strength": 0.80},
        {"concept_a": "ai", "concept_b": "cognitive-science", "count": 6, "strength": 0.78},
        {"concept_a": "fine-tuning", "concept_b": "macos", "count": 5, "strength": 0.60},
    ]
}

# ── Conversations: replace with demo conversations ──
data["GET /api/conversations"] = [
    {"session_id": "demo-001", "title": "Getting started with AI OS", "message_count": 6, "created_at": "2025-06-15T10:30:00Z", "updated_at": "2025-06-15T10:35:00Z", "archived": False, "source": "chat"},
    {"session_id": "demo-002", "title": "How the memory system works", "message_count": 4, "created_at": "2025-06-14T15:00:00Z", "updated_at": "2025-06-14T15:15:00Z", "archived": False, "source": "chat"},
    {"session_id": "demo-003", "title": "Setting up feeds and sources", "message_count": 8, "created_at": "2025-06-13T09:00:00Z", "updated_at": "2025-06-13T09:25:00Z", "archived": False, "source": "chat"},
    {"session_id": "demo-004", "title": "Fine-tuning on Apple Silicon", "message_count": 5, "created_at": "2025-06-12T20:00:00Z", "updated_at": "2025-06-12T20:20:00Z", "archived": False, "source": "chat"},
]

# ── Chat history: add demo messages ──
data["GET /api/chat/history"] = [
    {"id": "msg-001", "role": "user", "content": "What is AI OS?", "timestamp": "2025-06-15T10:30:00Z", "session_id": "demo-001"},
    {"id": "msg-002", "role": "assistant", "content": "AI OS is a local-first cognitive operating system. It gives you a personal AI agent that runs entirely on your machine \u2014 your data never leaves your device.\n\nIt has identity threads, memory consolidation, feeds integration, and subconscious loops that learn from your conversations over time.", "timestamp": "2025-06-15T10:30:05Z", "session_id": "demo-001"},
    {"id": "msg-003", "role": "user", "content": "How does the memory system work?", "timestamp": "2025-06-15T10:31:00Z", "session_id": "demo-001"},
    {"id": "msg-004", "role": "assistant", "content": "Three layers:\n\n1. **Short-term** \u2014 recent conversation turns in a buffer\n2. **Temporary facts** \u2014 extracted insights awaiting your approval\n3. **Long-term** \u2014 approved facts consolidated into identity threads\n\nThe subconscious loop processes conversations in the background, extracting facts and strengthening pathways through a potentiation system inspired by biological memory.", "timestamp": "2025-06-15T10:31:08Z", "session_id": "demo-001"},
    {"id": "msg-005", "role": "user", "content": "Can I fine-tune a model on my own data?", "timestamp": "2025-06-15T10:32:00Z", "session_id": "demo-001"},
    {"id": "msg-006", "role": "assistant", "content": "Yes! The Training page generates examples from every module \u2014 identity, philosophy, reflex, and more. It exports to JSONL format for MLX training on Apple Silicon.\n\nYou can fine-tune Qwen, Llama, or other supported models. The whole pipeline runs locally.", "timestamp": "2025-06-15T10:32:10Z", "session_id": "demo-001"},
]

# ── Subconscious state: sanitize any personal content ──
data["GET /api/subconscious/state"] = {
    "identity": {
        "profiles": 3,
        "total_facts": 13,
        "top_facts": [
            "Software engineer building AI OS",
            "Prefers Python and TypeScript",
            "Values privacy and local-first design",
            "Direct communication style",
            "Interested in cognitive science and memory architectures"
        ]
    },
    "philosophy": {
        "profiles": 3,
        "total_facts": 5,
        "top_facts": [
            "Privacy is a fundamental right",
            "Open source is a public good",
            "Simplicity over cleverness"
        ]
    },
    "memory": {
        "short_term": 6,
        "pending_facts": 2,
        "long_term": 18
    }
}

# ── Subconscious context ──
data["GET /api/subconscious/context"] = {
    "identity_summary": "Alex is a software engineer building AI OS, a local-first personal AI system. Prefers Python/TypeScript, works on macOS, interested in AI and cognitive science.",
    "philosophy_summary": "Values privacy, open source, simplicity, and local-first design. Ships early and iterates.",
    "recent_topics": ["memory system", "fine-tuning", "feeds integration"],
    "active_goals": ["Build comprehensive AI OS", "Fine-tune custom models"],
    "memory_stats": {"short_term": 6, "pending": 2, "long_term": 18}
}

# ── Log events: sanitize ──
data["GET /api/log/events"] = {
    "events": [
        {"id": 1, "type": "chat", "message": "Conversation started: Getting started with AI OS", "timestamp": "2025-06-15T10:30:00Z", "source": "chat"},
        {"id": 2, "type": "memory", "message": "Fact extracted: prefers Python for backend development", "timestamp": "2025-06-15T10:30:10Z", "source": "memory"},
        {"id": 3, "type": "subconscious", "message": "Memory consolidation loop completed — 3 facts promoted", "timestamp": "2025-06-15T10:35:00Z", "source": "subconscious"},
        {"id": 4, "type": "feeds", "message": "RSS poll: 5 new items from arxiv.org/cs.AI", "timestamp": "2025-06-15T08:00:00Z", "source": "feeds"},
        {"id": 5, "type": "system", "message": "Agent status: awake", "timestamp": "2025-06-15T07:00:00Z", "source": "system"},
        {"id": 6, "type": "eval", "message": "Eval run: identity_recall scored 0.90", "timestamp": "2025-06-14T16:30:00Z", "source": "eval"},
        {"id": 7, "type": "finetune", "message": "Training run nola-v1 completed — 320 examples", "timestamp": "2025-06-14T12:00:00Z", "source": "finetune"},
    ],
    "total": 7
}

# ── Docs content: use generic README ──
data["GET /api/docs/content"] = {
    "content": "# AI OS\n\nA local-first cognitive operating system.\n\n## Overview\n\nAI OS gives you a personal AI agent that runs entirely on your machine. Your data never leaves your device.\n\n## Features\n\n- **Identity Threads** \u2014 Build a persistent self-model across conversations\n- **Memory System** \u2014 Short-term, temporary, and long-term memory layers\n- **Subconscious Loops** \u2014 Background processing that learns while you're away\n- **Feeds Integration** \u2014 RSS, email, and GitHub notifications in one place\n- **Eval Framework** \u2014 Test and benchmark your agent's capabilities\n- **Fine-tuning** \u2014 Train custom models on your conversation data\n- **Workspace** \u2014 File management with AI-powered summaries\n\n## Getting Started\n\n```bash\npip install -r requirements.txt\npython cli.py serve\n```\n\nThen open http://localhost:5173 in your browser."
}

# ── Clean up finetune/generate/targets paths ──
targets = data.get("GET /api/finetune/generate/targets", {})
if isinstance(targets, dict) and "targets" in targets:
    for t in targets["targets"]:
        if "source_file" in t and "/Users/" in str(t.get("source_file", "")):
            t["source_file"] = t["source_file"].replace("/Users/cade/Desktop/AI_OS/", "")

# ── Clean subconscious loops of local paths ──
loops = data.get("GET /api/subconscious/loops", {})
if isinstance(loops, dict) and "loops" in loops:
    for loop in loops["loops"]:
        if "generated_dir" in loop:
            loop["generated_dir"] = "finetune/generated"
        # Strip verbose prompt text to save space
        if "prompts" in loop:
            for key in loop["prompts"]:
                if len(loop["prompts"][key]) > 200:
                    loop["prompts"][key] = loop["prompts"][key][:200] + "..."

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
