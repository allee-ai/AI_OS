"""
General Knowledge — topic scanner + CRUD for self-referential training data.

Scans the AIOS codebase for CS/software topics, maps them to files,
and manages per-topic JSONL training examples that teach general
knowledge *through* the project's own architecture.
"""

from pathlib import Path
from typing import Optional
import json
import re
import os

BASE_DIR = Path(__file__).resolve().parent.parent          # AI_OS root
STORAGE_DIR = Path(__file__).resolve().parent / "general_knowledge"

# ── Topic definitions ────────────────────────────────────────

TOPICS = [
    {
        "id": "databases_sql",
        "name": "Databases & SQL",
        "icon": "🗄️",
        "description": "SQLite, schema, queries, migrations",
        "patterns": [r"sqlite", r"\.execute\(", r"CREATE TABLE", r"SELECT .* FROM", r"get_connection"],
        "aios_framing": "AIOS stores threads, concepts, and training state in SQLite — the same relational model that powers most of the world's software.",
    },
    {
        "id": "http_rest",
        "name": "HTTP & REST APIs",
        "icon": "🌐",
        "description": "FastAPI routes, request/response, endpoints",
        "patterns": [r"@router\.", r"APIRouter", r"HTTPException", r"async def .+\(.*request", r"fetch\("],
        "aios_framing": "Every AIOS capability is exposed as a REST endpoint — the same pattern that connects every service on the internet.",
    },
    {
        "id": "async_concurrency",
        "name": "Async & Concurrency",
        "icon": "⚡",
        "description": "asyncio, threads, background tasks, event loops",
        "patterns": [r"async def", r"await ", r"asyncio\.", r"threading\.", r"BackgroundTasks", r"\.start\(\)"],
        "aios_framing": "AIOS runs 8 subconscious loops concurrently — the same async patterns that let operating systems multitask.",
    },
    {
        "id": "machine_learning",
        "name": "Machine Learning",
        "icon": "🧠",
        "description": "Training, inference, loss, gradients, models",
        "patterns": [r"torch\.", r"mlx\.", r"model\.", r"loss", r"optimizer", r"forward\(", r"backward\(", r"train\("],
        "aios_framing": "AIOS fine-tunes its own base model — the same gradient descent loop behind every LLM.",
    },
    {
        "id": "design_patterns",
        "name": "Design Patterns",
        "icon": "🏗️",
        "description": "Singleton, factory, observer, strategy patterns",
        "patterns": [r"class .+:", r"def __init__", r"@staticmethod", r"@classmethod", r"_instance", r"registry"],
        "aios_framing": "AIOS uses registries, factories, and observers throughout — classical patterns that make software composable.",
    },
    {
        "id": "graphs_trees",
        "name": "Graphs & Trees",
        "icon": "🌳",
        "description": "Graph traversal, trees, DAGs, adjacency",
        "patterns": [r"graph", r"node", r"edge", r"adjacen", r"traverse", r"hebbian", r"concept_graph", r"spread_activation"],
        "aios_framing": "The Hebbian concept graph IS a weighted directed graph — spread activation is just BFS with decay.",
    },
    {
        "id": "event_systems",
        "name": "Event Systems",
        "icon": "📡",
        "description": "Pub/sub, hooks, callbacks, signals",
        "patterns": [r"on_event", r"emit\(", r"subscribe", r"callback", r"hook", r"listener", r"trigger"],
        "aios_framing": "Feeds trigger reflexes, reflexes call tools — AIOS is an event-driven system like any modern OS.",
    },
    {
        "id": "auth_security",
        "name": "Auth & Security",
        "icon": "🔐",
        "description": "API keys, tokens, hashing, access control",
        "patterns": [r"api_key", r"token", r"auth", r"secret", r"hash", r"password", r"encrypt"],
        "aios_framing": "AIOS manages API keys for multiple providers — the same credential management every cloud service needs.",
    },
    {
        "id": "caching",
        "name": "Caching",
        "icon": "💨",
        "description": "Memoization, LRU, TTL, cache invalidation",
        "patterns": [r"cache", r"_cache", r"memoize", r"lru_cache", r"TTL", r"invalidat"],
        "aios_framing": "STATE assembly caches thread content by mtime — the universal cache-invalidation pattern.",
    },
    {
        "id": "tokenization",
        "name": "Tokenization & NLP",
        "icon": "🔤",
        "description": "Tokenizers, BPE, text processing, embeddings",
        "patterns": [r"tokeniz", r"token_count", r"BPE", r"encode\(", r"decode\(", r"vocab"],
        "aios_framing": "AIOS counts tokens to fit context windows — the same subword tokenization that every LLM uses.",
    },
    {
        "id": "testing_eval",
        "name": "Testing & Evaluation",
        "icon": "🧪",
        "description": "Unit tests, assertions, eval harnesses, scoring",
        "patterns": [r"assert ", r"def test_", r"pytest", r"score", r"eval", r"judge", r"pass_rate"],
        "aios_framing": "The 8-eval behavioral suite IS a test harness — measuring AI behavior like unit tests measure code.",
    },
    {
        "id": "cli_tools",
        "name": "CLI & Argument Parsing",
        "icon": "⌨️",
        "description": "argparse, click, command-line interfaces",
        "patterns": [r"argparse", r"add_argument", r"\.parse_args", r"click\.", r"@click\.", r"sys\.argv"],
        "aios_framing": "AIOS has a full CLI layer — the same argument-parsing patterns behind every Unix tool.",
    },
    {
        "id": "serialization",
        "name": "Serialization & Formats",
        "icon": "📦",
        "description": "JSON, YAML, JSONL, Pydantic models",
        "patterns": [r"json\.", r"yaml\.", r"\.jsonl", r"BaseModel", r"\.model_dump", r"pydantic"],
        "aios_framing": "Training data is JSONL, config is YAML, APIs return JSON — AIOS uses every standard serialization format.",
    },
    {
        "id": "scheduling",
        "name": "Scheduling & Loops",
        "icon": "⏰",
        "description": "Cron, intervals, periodic tasks, loop timing",
        "patterns": [r"schedule", r"interval", r"sleep\(", r"periodic", r"cron", r"loop_interval", r"tick"],
        "aios_framing": "Subconscious loops run on configurable intervals — the same scheduling primitives as cron or systemd timers.",
    },
    {
        "id": "file_io",
        "name": "File I/O & Paths",
        "icon": "📁",
        "description": "Reading/writing files, Path operations, glob",
        "patterns": [r"open\(", r"Path\(", r"\.read_text", r"\.write_text", r"glob\(", r"os\.path"],
        "aios_framing": "Thread files, training data, logs — AIOS is built on the filesystem, the oldest storage abstraction.",
    },
    {
        "id": "error_handling",
        "name": "Error Handling",
        "icon": "🛡️",
        "description": "try/except, error classes, graceful degradation",
        "patterns": [r"try:", r"except ", r"raise ", r"Exception", r"Error\(", r"traceback"],
        "aios_framing": "Every subconscious loop catches its own errors — resilience through isolation, like process boundaries in an OS.",
    },
    {
        "id": "embeddings_vectors",
        "name": "Embeddings & Vectors",
        "icon": "📐",
        "description": "Vector similarity, cosine distance, semantic search",
        "patterns": [r"embed", r"vector", r"cosine", r"similarity", r"semantic_search", r"faiss", r"annoy"],
        "aios_framing": "Concept retrieval uses embedding similarity — the same vector math that powers every RAG system.",
    },
    {
        "id": "prompt_engineering",
        "name": "Prompt Engineering",
        "icon": "✍️",
        "description": "System prompts, few-shot, chain-of-thought, templates",
        "patterns": [r"system_prompt", r"system.*message", r"few.?shot", r"chain.?of.?thought", r"template", r"STATE"],
        "aios_framing": "STATE assembly IS dynamic prompt engineering — building the system prompt from live introspection.",
    },
    {
        "id": "data_pipelines",
        "name": "Data Pipelines",
        "icon": "🔄",
        "description": "ETL, data cleaning, transforms, batch processing",
        "patterns": [r"pipeline", r"transform", r"clean", r"preprocess", r"batch", r"export.*data"],
        "aios_framing": "The T3 training pipeline (REPEAT→UNDERSTAND→GENERALIZE) is a 3-stage ETL for knowledge.",
    },
    {
        "id": "websockets_streaming",
        "name": "WebSockets & Streaming",
        "icon": "🔌",
        "description": "SSE, WebSocket, streaming responses, real-time",
        "patterns": [r"websocket", r"WebSocket", r"stream", r"SSE", r"EventSource", r"yield.*\n"],
        "aios_framing": "Chat responses stream token-by-token over SSE — the same real-time pattern behind every chat interface.",
    },
]

TOPIC_MAP = {t["id"]: t for t in TOPICS}

# Files/dirs to skip during scan
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "runs",
              "adapters-behavioral", "adapters-llama3b-v2", "fused-behavioral",
              "pretrain_data", "convo_chunks", "assets", ".next", "dist", "build"}
_SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}


# ── Codebase scanner ─────────────────────────────────────────

def scan_codebase(max_files_per_topic: int = 10) -> list[dict]:
    """
    Walk the codebase and count pattern matches per topic.
    Returns topics list enriched with match_count and top_files.
    """
    # Collect all scannable files
    files: list[Path] = []
    for root, dirs, fnames in os.walk(BASE_DIR):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        rp = Path(root)
        for fn in fnames:
            fp = rp / fn
            if fp.suffix in _SCAN_EXTENSIONS:
                files.append(fp)

    results = []
    for topic in TOPICS:
        compiled = [re.compile(p, re.IGNORECASE) for p in topic["patterns"]]
        file_hits: list[dict] = []

        for fp in files:
            try:
                content = fp.read_text(errors="ignore")
            except Exception:
                continue

            count = sum(len(pat.findall(content)) for pat in compiled)
            if count > 0:
                rel = str(fp.relative_to(BASE_DIR))
                file_hits.append({"file": rel, "matches": count})

        file_hits.sort(key=lambda x: x["matches"], reverse=True)
        total = sum(h["matches"] for h in file_hits)

        results.append({
            **topic,
            "match_count": total,
            "file_count": len(file_hits),
            "top_files": file_hits[:max_files_per_topic],
            "example_count": _count_examples(topic["id"]),
        })

    results.sort(key=lambda x: x["match_count"], reverse=True)
    return results


def get_all_topics_summary() -> list[dict]:
    """Fast path: return topics with example counts only (no scan)."""
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "icon": t["icon"],
            "description": t["description"],
            "aios_framing": t["aios_framing"],
            "example_count": _count_examples(t["id"]),
        }
        for t in TOPICS
    ]


# ── CRUD for training examples ───────────────────────────────

def _topic_path(topic_id: str) -> Path:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return STORAGE_DIR / f"{topic_id}.jsonl"


def _count_examples(topic_id: str) -> int:
    p = _topic_path(topic_id)
    if not p.exists():
        return 0
    return sum(1 for line in open(p) if line.strip())


def get_topic_examples(topic_id: str) -> list[dict]:
    """Load all examples for a topic."""
    p = _topic_path(topic_id)
    if not p.exists():
        return []
    examples = []
    for i, line in enumerate(open(p)):
        line = line.strip()
        if not line:
            continue
        try:
            ex = json.loads(line)
            ex["_index"] = i
            examples.append(ex)
        except json.JSONDecodeError:
            continue
    return examples


def save_topic_example(topic_id: str, example: dict) -> dict:
    """Append a new example to a topic's JSONL file."""
    if topic_id not in TOPIC_MAP:
        raise ValueError(f"Unknown topic: {topic_id}")
    p = _topic_path(topic_id)
    clean = {k: v for k, v in example.items() if k != "_index"}
    with open(p, "a") as f:
        f.write(json.dumps(clean) + "\n")
    return {"status": "saved", "topic": topic_id, "count": _count_examples(topic_id)}


def delete_topic_example(topic_id: str, index: int) -> dict:
    """Delete an example by line index."""
    p = _topic_path(topic_id)
    if not p.exists():
        raise ValueError(f"No examples for topic: {topic_id}")
    lines = open(p).readlines()
    if index < 0 or index >= len(lines):
        raise ValueError(f"Index {index} out of range (0-{len(lines)-1})")
    lines.pop(index)
    with open(p, "w") as f:
        f.writelines(lines)
    return {"status": "deleted", "topic": topic_id, "count": _count_examples(topic_id)}


def update_topic_example(topic_id: str, index: int, example: dict) -> dict:
    """Update an example by line index."""
    p = _topic_path(topic_id)
    if not p.exists():
        raise ValueError(f"No examples for topic: {topic_id}")
    lines = open(p).readlines()
    if index < 0 or index >= len(lines):
        raise ValueError(f"Index {index} out of range (0-{len(lines)-1})")
    clean = {k: v for k, v in example.items() if k != "_index"}
    lines[index] = json.dumps(clean) + "\n"
    with open(p, "w") as f:
        f.writelines(lines)
    return {"status": "updated", "topic": topic_id, "count": _count_examples(topic_id)}
