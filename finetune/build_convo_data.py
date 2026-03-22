#!/usr/bin/env python3
"""
Conversation Data Pipeline for AIOS Training

Reads all imported conversations, filters by source, chunks into
sliding windows that fit max_seq_length, and outputs JSONL suitable
for MLX LoRA training.

Usage:
    python3 finetune/build_convo_data.py [--max-tokens 2048] [--window 6] [--stride 3]
"""

import json
import os
import sys
import hashlib
import random
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONVO_DIR = ROOT / "Feeds" / "conversations"
OUTPUT_DIR = ROOT / "finetune"

# ── Exclusions ──────────────────────────────────────────────────────
# Personal conversations to always skip (partial UUID match)
EXCLUDE_IDS = {
    "a4bd5e26",  # Documenting Recent Relationship Issues
    "8858ad09",  # Organizing Personal Legal Documents
    "bbfb2a1f",  # Need models for detecting DARVO behavior
}

# Skip ChatGPT convos by default (user's ex stuff)
SKIP_CHATGPT = True


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return len(text) // 4


def load_conversations():
    """Load all conversation JSON files, return filtered list."""
    convos = []
    skipped_chatgpt = 0
    skipped_personal = 0
    skipped_empty = 0

    for f in sorted(CONVO_DIR.iterdir()):
        if not f.name.endswith(".json"):
            continue

        data = json.loads(f.read_text())
        turns = data.get("turns", [])
        name = data.get("name", "untitled")
        ss = data.get("state_snapshot", {})
        src = ss.get("imported_from", "unknown")

        # Skip empty conversations
        if len(turns) < 2:
            skipped_empty += 1
            continue

        # Skip ChatGPT imports
        if SKIP_CHATGPT and src == "ChatGPT":
            skipped_chatgpt += 1
            continue

        # Skip personal exclusions
        if any(eid in f.name for eid in EXCLUDE_IDS):
            skipped_personal += 1
            continue

        convos.append({
            "file": f.name,
            "name": name,
            "source": src,
            "turns": turns,
            "started": data.get("started", ""),
        })

    print(f"Loaded {len(convos)} conversations")
    print(f"  Skipped: {skipped_chatgpt} ChatGPT, {skipped_personal} personal, {skipped_empty} empty")
    return convos


def chunk_conversation(convo, window_size=6, stride=3, max_tokens=2048):
    """
    Chunk a conversation into overlapping sliding windows.

    Each chunk becomes one training example with the format:
    system: context about the conversation
    Then alternating user/assistant turns.

    window_size: number of turns per chunk
    stride: how many turns to advance between chunks
    max_tokens: hard cap on estimated tokens per example
    """
    turns = convo["turns"]
    name = convo["name"]
    source = convo["source"]
    chunks = []

    # Build system context
    system_msg = f"[conversation: {name}]"

    i = 0
    while i < len(turns):
        window = turns[i:i + window_size]

        # Build messages for this chunk
        messages = [{"role": "system", "content": system_msg}]

        for turn in window:
            user_text = turn.get("user", "").strip()
            assistant_text = turn.get("assistant", "").strip()

            if user_text:
                messages.append({"role": "user", "content": user_text})
            if assistant_text:
                messages.append({"role": "assistant", "content": assistant_text})

        # Need at least a user + assistant message beyond system
        if len(messages) < 3:
            i += stride
            continue

        # Check token budget
        total_text = " ".join(m["content"] for m in messages)
        est_tokens = estimate_tokens(total_text)

        # If over budget, shrink the window for this chunk
        if est_tokens > max_tokens:
            # Try progressively smaller windows
            for shrink in range(1, window_size):
                smaller = turns[i:i + window_size - shrink]
                msgs = [{"role": "system", "content": system_msg}]
                for turn in smaller:
                    u = turn.get("user", "").strip()
                    a = turn.get("assistant", "").strip()
                    if u:
                        msgs.append({"role": "user", "content": u})
                    if a:
                        msgs.append({"role": "assistant", "content": a})
                total = " ".join(m["content"] for m in msgs)
                if estimate_tokens(total) <= max_tokens and len(msgs) >= 3:
                    messages = msgs
                    est_tokens = estimate_tokens(total)
                    break
            else:
                # Even a single turn is too long — take it and let MLX truncate
                pass

        # Create the training example
        example = {
            "messages": messages,
            "metadata": {
                "source": "conversation",
                "convo_name": name,
                "imported_from": source,
                "chunk_start": i,
                "chunk_turns": len(window),
                "est_tokens": est_tokens,
            }
        }
        chunks.append(example)
        i += stride

    return chunks


def build_all_chunks(convos, window_size=6, stride=3, max_tokens=2048):
    """Process all conversations into chunks."""
    all_chunks = []
    for convo in convos:
        chunks = chunk_conversation(convo, window_size, stride, max_tokens)
        all_chunks.extend(chunks)
    return all_chunks


def split_data(chunks, valid_ratio=0.1, seed=42):
    """Split chunks into train/valid sets. Deterministic by content hash."""
    random.seed(seed)
    random.shuffle(chunks)

    split_idx = max(1, int(len(chunks) * (1 - valid_ratio)))
    train = chunks[:split_idx]
    valid = chunks[split_idx:]
    return train, valid


def write_jsonl(examples, path):
    """Write examples to JSONL file."""
    with open(path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(examples)} examples to {path}")


def main():
    parser = argparse.ArgumentParser(description="Build conversation training data")
    parser.add_argument("--max-tokens", type=int, default=2048, help="Max tokens per chunk")
    parser.add_argument("--window", type=int, default=6, help="Turns per chunk window")
    parser.add_argument("--stride", type=int, default=3, help="Stride between windows")
    parser.add_argument("--valid-ratio", type=float, default=0.1, help="Validation split ratio")
    parser.add_argument("--include-chatgpt", action="store_true", help="Include ChatGPT convos")
    args = parser.parse_args()

    global SKIP_CHATGPT
    SKIP_CHATGPT = not args.include_chatgpt

    print(f"=== AIOS Conversation Data Pipeline ===")
    print(f"Window: {args.window} turns, stride: {args.stride}, max tokens: {args.max_tokens}")
    print()

    # Step 1: Load conversations
    convos = load_conversations()
    total_turns = sum(len(c["turns"]) for c in convos)
    total_chars = sum(
        sum(len(t.get("user", "")) + len(t.get("assistant", "")) for t in c["turns"])
        for c in convos
    )
    print(f"  Total turns: {total_turns:,}")
    print(f"  Est tokens: {total_chars // 4:,}")
    print()

    # Step 2: Chunk
    print("Chunking conversations...")
    chunks = build_all_chunks(convos, args.window, args.stride, args.max_tokens)
    print(f"  Generated {len(chunks):,} training chunks")

    # Token stats
    token_counts = [c["metadata"]["est_tokens"] for c in chunks]
    print(f"  Avg tokens/chunk: {sum(token_counts) // len(token_counts)}")
    print(f"  Max tokens/chunk: {max(token_counts)}")
    print(f"  Total est tokens: {sum(token_counts):,}")
    print()

    # Step 3: Split
    print("Splitting train/valid...")
    train_chunks, valid_chunks = split_data(chunks, args.valid_ratio)
    print(f"  Train: {len(train_chunks):,} chunks")
    print(f"  Valid: {len(valid_chunks):,} chunks")
    print()

    # Step 4: Write conversation-only files
    convo_dir = OUTPUT_DIR / "convo_chunks"
    convo_dir.mkdir(exist_ok=True)
    write_jsonl(train_chunks, convo_dir / "train.jsonl")
    write_jsonl(valid_chunks, convo_dir / "valid.jsonl")

    print()
    print("Done! Conversation chunks ready.")
    print(f"  {convo_dir / 'train.jsonl'}")
    print(f"  {convo_dir / 'valid.jsonl'}")

    return train_chunks, valid_chunks


if __name__ == "__main__":
    main()
