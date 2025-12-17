# utils.py - Utility functions for logging, conversation management, and LLM generation

import json
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# JSON Helpers (reusable across all modules)
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    """Load JSON file, return {} on error or missing."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_json(path: Path, data: dict) -> None:
    """Write dict to JSON file with pretty formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Ollama Client
# ─────────────────────────────────────────────────────────────────────────────

_ollama_client = None


def get_ollama_client():
    """Return a global Ollama client, initialize lazily and safely."""
    global _ollama_client
    if _ollama_client is not None:
        return _ollama_client
    try:
        import ollama as _ollama  # type: ignore
        _ollama_client = _ollama.Client()
        return _ollama_client
    except Exception as e:
        log(f"ollama client init failed: {e}")
        _ollama_client = None
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def log(message: str):
    """Append message to LOG.txt with timestamp."""
    with open("LOG.txt", "a") as log_file:
        log_file.write(f"{datetime.now().isoformat()} - {message}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Conversation Management
# ─────────────────────────────────────────────────────────────────────────────

def append_to_conversation(entry: str, convo_id: str):
    """Append a JSON record to a conversation file."""
    record = {
        "timestamp": datetime.now().isoformat(),
        "entry": entry,
        "convo_id": convo_id,
    }
    with open(f"Stimuli/{convo_id}.txt", "a") as convo_file:
        convo_file.write(json.dumps(record) + "\n")


def load_conversation(convo_id: str) -> list:
    """Load all records for a conversation by ID."""
    conversation = []
    try:
        with open(f"Stimuli/{convo_id}.txt", "r") as convo_file:
            for line in convo_file:
                record = json.loads(line)
                conversation.append(record)
    except FileNotFoundError:
        pass
    return conversation
