"""
Docs Training Data Exporter
============================
Exports architectural knowledge, feature documentation, and roadmap
context as training data. Teaches the model about its own design.

Sections: data (feature knowledge), api (docs API), cli (none), schema (none)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from finetune.sections import build_api_examples

TRAINING_DIR = Path(__file__).parents[1] / "finetune" / "auto_generated"
TRAINING_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────
# Self-knowledge: API, CLI, Schema
# ─────────────────────────────────────────────────────

API_ENDPOINTS = [
    ("GET",  "/api/docs",           "List all markdown documentation files as a nested tree"),
    ("GET",  "/api/docs/content",   "Get the content of a specific markdown file by path"),
    ("GET",  "/api/docs/search",    "Full-text search across all documentation"),
    ("POST", "/api/docs/aggregate", "Aggregate module docs into root documentation"),
]

CLI_COMMANDS = []  # Docs has no CLI commands

SCHEMA_TABLES = []  # Docs has no database tables


# ─────────────────────────────────────────────────────
# Top Features per Module — from Roadmap + Architecture
# ─────────────────────────────────────────────────────

MODULE_FEATURES: Dict[str, Dict[str, Any]] = {
    "linking_core": {
        "purpose": "Relevance Engine (Thalamus) — WHICH concepts matter NOW?",
        "top_features": [
            "Hebbian learning: concepts that co-occur strengthen links (asymptotic formula)",
            "Spread activation: multi-hop graph traversal with threshold gating",
            "SHORT → LONG potentiation: links promoted after fire_count≥5 and strength≥0.5",
            "Co-occurrence scoring: fact keys that appear together get boosted (log formula, capped 0.3)",
            "Multi-dimensional scoring: identity, log, form, philosophy, reflex, cooccurrence dimensions",
            "ConsolidationLoop: background daemon promotes SHORT→LONG every 5 minutes",
            "3D graph visualization with concept nodes and weighted edges",
            "Structural mind map of entire agent's knowledge graph",
        ],
        "roadmap": [
            "Universal linking: create_link(row, row) for any database row",
            "Graph density improvements: dynamic scaling, hover info, zoom levels",
            "Decay tuning: configurable decay rates per category",
            "Concept merging: deduplicate similar concepts",
            "Activation history: track what surfaced over time",
        ],
    },
    "identity": {
        "purpose": "Self-Model — WHO am I? WHO are you? WHO do we know?",
        "top_features": [
            "Profile types with trust levels: user(10), machine(8), family(7), friend(4)",
            "Hierarchical dot-notation fact keys: sarah.likes.coffee, machine.os.version",
            "Three verbosity levels per fact: L1(~10 tokens), L2(~50), L3(~200)",
            "Protected profiles: user and machine profiles cannot be deleted",
            "vCard import pipeline: upload → parse → preview → commit",
            "Weight-based scoring: frequently accessed facts rise in priority",
            "Preset contact facts: name, email, phone, location, occupation, organization",
        ],
        "roadmap": [
            "Family/contacts UI: add/edit family members from dashboard",
            "Relationship graph: D3 visualization of social network",
            "Profile photos: avatar upload and display",
            "Batch fact updates: currently one-at-a-time",
            "Fact history/versioning",
        ],
    },
    "philosophy": {
        "purpose": "Values & Alignment — WHY should I do this?",
        "top_features": [
            "Profile-based value storage with L1/L2/L3 verbosity",
            "Profile types: value_system(10), ethical_framework(9), reasoning_style(8), worldview(7), aesthetic(6)",
            "Weight-based inclusion in STATE: high-weight values always present",
            "Values as operating parameters: injected into system prompt, not suggestions",
            "Core values: honesty, curiosity, harm_reduction, evidence_based",
            "Same schema pattern as identity but for internal beliefs",
        ],
        "roadmap": [
            "Ethics module: detect_harm(), preserve_dignity(), respect_boundary()",
            "Awareness module: situational, emotional, self-awareness",
            "Curiosity module: ask_better(), follow_threads(), spark_wonder()",
            "Value conflicts UI: when two values clash, show reasoning",
            "Resolve module: purpose alignment, goal persistence",
        ],
    },
    "log": {
        "purpose": "Event Timeline — WHEN did this happen?",
        "top_features": [
            "Three tables: unified_events (main timeline), log_system (infra), log_server (HTTP)",
            "Event types with importance weights: convo(8), memory(7), user_action(6), file(4), system(2)",
            "Session grouping: events tagged with session_id for coherent episodes",
            "Immutable history: events represent what actually happened",
            "related_key + related_table: trace events back to the facts they created",
            "Context levels: L1(10 events), L2(100 events), L3(1000 events)",
        ],
        "roadmap": [
            "Timeline visualization: interactive event timeline in UI",
            "Session analytics: duration, message count, topic clusters",
            "Event search: full-text search across event history",
            "Export/import: JSON/CSV export of event history",
        ],
    },
    "reflex": {
        "purpose": "Pattern Automata (Basal Ganglia) — HOW do I respond automatically?",
        "top_features": [
            "Reflex cascade: system(0.9+) → shortcuts(0.6-0.8) → greetings(0.3-0.5) → triggers → LLM",
            "Feed triggers: connect feed events to tool actions without LLM",
            "Trigger types: webhook, poll (interval-based), schedule (cron)",
            "Response modes: tool (direct execute), agent (LLM reasoning), notify (surface in UI)",
            "condition_json filtering: only trigger when conditions match",
            "Priority-based execution: higher priority triggers checked first",
            "Four tables: reflex_greetings, reflex_shortcuts, reflex_system, reflex_triggers",
        ],
        "roadmap": [
            "10x auto-promotion: patterns repeating 10+ times auto-promote to reflex",
            "Reflex editor: visual pattern builder in UI",
            "Reflex analytics: usage frequency, match rates",
            "Feed trigger builder UI",
        ],
    },
    "form": {
        "purpose": "Embodiment & Capabilities — WHAT can I do?",
        "top_features": [
            "Tool registry with allowed/enabled/exists checks (defense-in-depth)",
            ":::execute::: block protocol parsed by scanner.py",
            "Tool loop: up to 5 rounds of call → result → re-call",
            "Hebbian weight updates: success increases weight, failure decreases",
            "Tool traces: every call logged with success/failure and weight delta",
            "Safety allowlist: SAFE_ACTIONS / BLOCKED_ACTIONS gating",
            "Core executables: file_read, file_write, terminal (30s timeout), web_search",
            "Environment validation: checks required env vars before execution",
            "Context levels: L1(tool names), L2(descriptions+weights), L3(source code)",
        ],
        "roadmap": [
            "Tool editor UI: visual tool builder",
            "Tool marketplace: shareable tool definitions",
            "Action chaining: multi-step tool workflows",
            "Usage analytics: track success/failure rates",
        ],
    },
    "chat": {
        "purpose": "Conversation Management — interface to the user",
        "top_features": [
            "Two tables: convos (metadata) and convo_turns (messages)",
            "Auto-naming: generates 3-6 word title via llama3.2:1b",
            "Weight mechanics: view +0.02, bookmark +0.1",
            "Import from ChatGPT, Claude, Gemini, VS Code Copilot",
            "Format-specific parsers for each platform",
            "Message ratings: thumbs up/down for training signal",
            "state_snapshot_json: captures STATE at conversation start",
            "Channel tracking: react, cli, import",
        ],
        "roadmap": [
            "Import pipeline repair: fix and improve reliability",
            "Conversation branching: create conversation forks",
            "Export: markdown/JSON export",
            "Tags/categories: organize conversations",
            "Import directory organization by source",
        ],
    },
    "subconscious": {
        "purpose": "The Orchestrator — assembles reality from threads",
        "top_features": [
            "wake()/sleep() lifecycle management",
            "get_consciousness_context(level): assembles STATE from all threads",
            "ThreadRegistry: singleton managing all registered adapters",
            "Background loops: ConsolidationLoop(300s), SyncLoop(600s), HealthLoop(60s)",
            "ThoughtLoop: proactive agent reasoning in background",
            "TaskPlanner: context-aware multi-step task execution",
            "Custom loops: user-defined chain-of-thought loops from DB",
            "temp_memory: pending → pending_review → approved → consolidated lifecycle",
            "Token budgeting per thread via _budget_fill()",
        ],
        "roadmap": [
            "Implicit COT Loops: chain-of-thought background reasoning",
            "Priority queue: urgent facts surface first",
            "Dream mode: background processing during idle",
            "Attention visualization: show what's in context",
        ],
    },
    "workspace": {
        "purpose": "File Management — virtual filesystem for agent context",
        "top_features": [
            "File upload, folder organization, move/rename",
            "Full-text search (FTS5) within file contents",
            "Auto-summarization: LLM-powered summaries stored in DB",
            "Type-aware rendering: text, code, markdown, images",
            "Integrated in STATE via FTS hits",
        ],
        "roadmap": [
            "In-browser editing with syntax highlighting",
            "Agent file references in responses",
            "Version history: track changes over time",
            "Sharing: share files with external users",
        ],
    },
    "feeds": {
        "purpose": "Input & Awareness — external data sources",
        "top_features": [
            "Modular feed directories: gmail, discord, _template",
            "Event system: emit_event() with priority levels",
            "Encrypted secrets management for API keys and OAuth tokens",
            "OAuth2 flow for Gmail, bot token for Discord",
            "Router-based message bus",
            "Connects to reflex triggers for automated responses",
        ],
        "roadmap": [
            "Slack adapter: bot token auth, message polling",
            "SMS adapter: Twilio integration",
            "Feed status indicators in UI",
            "Feed viewer components (native dashboard)",
        ],
    },
    "finetune": {
        "purpose": "Training Studio — self-improvement pipeline",
        "top_features": [
            "Export pipeline: all modules → JSONL with section selection",
            "Sections: data, api, cli, schema, reasoning (curated)",
            "MLX LoRA config: 4-bit quantization, rank 8, Apple Silicon",
            "Adapter loading: create Ollama model from trained adapters",
            "Combined dataset: aios_combined.jsonl merges all sources",
            "Reasoning examples: 37 hand-crafted, deep-reasoning training pairs",
            "Per-module export with section toggles",
            "User-approved responses included in training",
        ],
        "roadmap": [
            "End-to-end test: export → train → load → verify",
            "Validation suite: test finetuned vs base on STATE obedience",
            "Synthetic data generator: auto-generate from schemas",
        ],
    },
    "eval": {
        "purpose": "Battle Arena — test and compare models",
        "top_features": [
            "Battle types: identity, memory, tool use, connections, speed",
            "LLM-as-a-Judge evaluation",
            "Leaderboard with win/loss stats",
            "Prompt injection resistance testing",
        ],
        "roadmap": [
            "Battle Arena UI: three-panel layout",
            "Auto-battle mode: watch battles run automatically",
            "Identity evaluator: prompt injection tests",
            "Memory evaluator: multi-session recall",
        ],
    },
}


def _build_feature_examples() -> List[Dict[str, Any]]:
    """Build training examples from module feature documentation."""
    examples = []
    
    for module, info in MODULE_FEATURES.items():
        purpose = info["purpose"]
        features = info["top_features"]
        roadmap = info["roadmap"]
        
        # Overview example
        feature_list = "\n".join(f"  • {f}" for f in features)
        examples.append({
            "messages": [
                {"role": "system", "content": f"== STATE ==\nModule: {module}\nPurpose: {purpose}"},
                {"role": "user", "content": f"What are the key features of the {module} module?"},
                {"role": "assistant", "content": f"The {module} module ({purpose}) has these key features:\n{feature_list}"},
            ],
            "metadata": {"source": "docs", "section": "data", "type": "features", "module": module},
        })
        
        # Purpose example
        examples.append({
            "messages": [
                {"role": "system", "content": f"== STATE ==\nModule: {module}"},
                {"role": "user", "content": f"What is the purpose of the {module} module?"},
                {"role": "assistant", "content": f"The {module} module answers: {purpose}"},
            ],
            "metadata": {"source": "docs", "section": "data", "type": "purpose", "module": module},
        })
        
        # Roadmap example
        if roadmap:
            roadmap_list = "\n".join(f"  • {r}" for r in roadmap)
            examples.append({
                "messages": [
                    {"role": "system", "content": f"== STATE ==\nModule: {module}"},
                    {"role": "user", "content": f"What's on the roadmap for {module}?"},
                    {"role": "assistant", "content": f"Planned features for {module}:\n{roadmap_list}"},
                ],
                "metadata": {"source": "docs", "section": "data", "type": "roadmap", "module": module},
            })
    
    return examples


def _build_architecture_examples() -> List[Dict[str, Any]]:
    """Build training examples from architecture documentation."""
    examples = []
    
    # System-level architecture knowledge
    arch_pairs = [
        (
            "How is the system organized?",
            "AI OS is organized in layers:\n"
            "  1. Feed Channels (React, CLI, Matrix, Email) — input sources\n"
            "  2. agent_service.py — classifies feed type, maps to context level\n"
            "  3. Subconscious — assembles STATE from all threads via introspect()\n"
            "  4. agent.py — receives STATE, calls LLM, returns response\n\n"
            "Each cognitive thread (identity, philosophy, log, form, reflex, linking_core) "
            "implements ThreadInterface with health() and introspect() methods. "
            "The subconscious orchestrator calls each thread's introspect() at the "
            "appropriate context level to build the STATE block."
        ),
        (
            "What are the context levels?",
            "Three HEA context levels control detail depth:\n"
            "  • L1 (~10 tokens): Brief — core identifiers only. For quick, casual exchanges.\n"
            "  • L2 (~50 tokens): Standard — key facts with moderate detail. Default for conversation.\n"
            "  • L3 (~200 tokens): Detailed — full biographical detail, relationships, nuance. For deep analysis.\n\n"
            "Each thread stores facts at all three levels (l1_value, l2_value, l3_value). "
            "The level is selected based on feed classification: realtime→L1, conversational→L2, analytical→L3."
        ),
        (
            "What is the memory pipeline?",
            "The memory pipeline flows through three stages:\n"
            "  1. Conversation → MemoryLoop extracts facts → stored in temp_memory as 'pending'\n"
            "  2. ConsolidationLoop scores and triages facts → moves to 'approved' or 'rejected'\n"
            "  3. Approved facts promoted to permanent storage in identity/philosophy threads\n\n"
            "Fact lifecycle: pending → pending_review → approved → consolidated.\n"
            "Low-confidence facts go to pending_review for human approval. "
            "High-confidence facts auto-approve. The consolidation loop runs every 300 seconds."
        ),
        (
            "How does tool calling work?",
            "Tool calling uses a text-native protocol:\n"
            "  1. LLM emits: :::execute::: tool_name.action {\"params\": ...} :::end:::\n"
            "  2. scanner.py parses the block from the response text\n"
            "  3. Safety checks: tool exists → tool allowed → tool enabled → env vars set\n"
            "  4. executor.py runs the tool with 30-second timeout\n"
            "  5. Result injected back into conversation as :::result::: block\n"
            "  6. LLM continues generating with the result in context\n\n"
            "The agent runs up to 5 tool call rounds per response. "
            "Each call updates the tool's Hebbian weight: success += (1-w)*0.1, failure -= 0.1."
        ),
        (
            "What background loops run?",
            "The subconscious runs these background loops:\n"
            "  • MemoryLoop — Extracts facts from conversations\n"
            "  • ConsolidationLoop (300s) — Scores and promotes temp facts to permanent storage\n"
            "  • SyncLoop (600s) — Syncs identity state across threads\n"
            "  • HealthLoop (60s) — Monitors thread health\n"
            "  • ThoughtLoop (120s) — Proactive agent background reasoning\n"
            "  • TaskPlanner (30s) — Context-aware multi-step task execution\n"
            "  • TrainingGenLoop (7200s) — Generates training examples using LLM\n"
            "  • Custom loops — User-defined chain-of-thought loops from database\n\n"
            "All loops use daemon threads with error backoff and graceful shutdown."
        ),
        (
            "What is the training pipeline?",
            "The self-training pipeline has four stages:\n"
            "  1. Export: Each module exports JSONL with sections (data, api, cli, schema, reasoning, generated, docs)\n"
            "  2. Combine: All exports merge into aios_combined.jsonl + user_approved.jsonl + reasoning_train.jsonl\n"
            "  3. Train: MLX LoRA fine-tuning on Apple Silicon (configurable rank, alpha, iterations)\n"
            "  4. Load: Trained adapter loaded into Ollama as new model\n\n"
            "Reasoning examples (37 curated) provide the baseline. "
            "Generated examples are produced by a background loop every 2 hours. "
            "The training loop is recursive: better responses → better training data → better model."
        ),
    ]
    
    for q, a in arch_pairs:
        examples.append({
            "messages": [
                {"role": "system", "content": "== STATE ==\nidentity.machine.name: Nola\narchitecture: AI OS Cognitive Operating System"},
                {"role": "user", "content": q},
                {"role": "assistant", "content": a},
            ],
            "metadata": {"source": "docs", "section": "data", "type": "architecture"},
        })
    
    return examples


def export_training_data(
    output_path: Optional[Path] = None,
    sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Export docs training data to JSONL.
    
    Sections: data (features + architecture), api (docs API endpoints)
    """
    if sections is None:
        sections = ["data", "api", "cli", "schema"]
    
    if output_path is None:
        output_path = Path(__file__).parents[1] / "finetune" / "docs_train.jsonl"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    examples: List[Dict[str, Any]] = []
    
    if "data" in sections:
        examples.extend(_build_feature_examples())
        examples.extend(_build_architecture_examples())
    
    if "api" in sections:
        examples.extend(build_api_examples("docs", API_ENDPOINTS))
    
    # cli and schema are empty for docs
    
    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")
    
    return {
        "path": str(output_path),
        "examples": len(examples),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def get_export_stats() -> Dict[str, Any]:
    """Get stats about exportable docs data."""
    feature_count = sum(
        2 + (1 if info["roadmap"] else 0)
        for info in MODULE_FEATURES.values()
    )
    arch_count = 6  # architecture examples
    return {
        "feature_examples": feature_count,
        "architecture_examples": arch_count,
        "exportable": feature_count + arch_count,
    }


def get_sections() -> Dict[str, Any]:
    """Return available training sections with counts."""
    from finetune.sections import count_api_examples
    stats = get_export_stats()
    return {
        "data":   {"description": "Module features, architecture knowledge, roadmap", "examples": stats["exportable"]},
        "api":    {"description": "Docs API endpoints", "examples": count_api_examples(API_ENDPOINTS)},
        "cli":    {"description": "No CLI commands", "examples": 0},
        "schema": {"description": "No database tables", "examples": 0},
    }
