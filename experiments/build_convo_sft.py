#!/usr/bin/env python3
"""
Mine Feeds/conversations/ into SFT training data for NolaNET.

Reads the 261 imported conversation JSON files, filters for relevant
technical/architecture/self-knowledge conversations, normalizes naming,
and outputs messages-format JSONL for the training pipeline.

Strategy:
  - Each conversation turn → one SFT example (system + user + assistant)
  - System message includes conversation topic for context
  - Filter out short/empty turns
  - Filter out off-topic convos (recipes, personal finance, etc.)
  - Normalize naming: "Nola" → "the system" where it's used as product name
  - Multi-turn: also create windowed multi-turn examples (2-3 turns)
"""
import json
import glob
import re
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONVO_DIR = ROOT / "Feeds" / "conversations"
OUT_DIR = ROOT / "experiments" / "self_sft"

# Keywords indicating relevant conversations
RELEVANT_KEYWORDS = {
    "thread", "identity", "subconscious", "reflex", "linking", "state",
    "architecture", "agent", "whitepaper", "aligned os", "cognitive",
    "training", "model", "nola", "philosophy", "memory", "prediction",
    "kernel", "form", "log", "brain", "consciousness", "agi",
    "inference", "neural", "token", "finetune", "fine-tune",
    "readme", "code", "python", "api", "frontend", "backend",
    "database", "profile", "config", "deploy", "docker",
    "eval", "benchmark", "test", "debug", "error", "fix", "refactor",
    "implement", "feature", "function", "class", "module",
    "import", "build", "run", "repo", "github", "copilot",
    "recursive", "self-referential", "metacognition", "awareness",
    "symmetry", "substrate", "resolution", "scaffold",
    "feed", "polling", "event", "router", "intelligence",
    "chat", "response", "prompt", "context", "conversation",
}

# Titles that indicate off-topic conversations to exclude
EXCLUDE_PATTERNS = [
    r"budget.*meal",
    r"recipe",
    r"hourly income",
    r"real estate",
    r"survival strategies within law",
    r"history of trans",
    r"7 habits",
    r"superconductors explained",
    r"limitless invest",
    r"dota",
    r"hacking basics",
    r"visio agent",           # Solsten/Elaris product, not AI_OS
    r"market research agent", # Solsten/Elaris product
]


def is_relevant(convo: dict) -> bool:
    """Check if a conversation is relevant for training."""
    name = (convo.get("name") or "").lower()
    
    # Exclude known off-topic patterns
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return False
    
    # Check title for relevant keywords
    for kw in RELEVANT_KEYWORDS:
        if kw in name.lower():
            return True
    
    # Check first few turns for relevant content
    turns = convo.get("turns", [])[:5]
    combined = " ".join(
        (t.get("user", "") + " " + t.get("assistant", ""))[:500]
        for t in turns
    ).lower()
    
    relevant_hits = sum(1 for kw in RELEVANT_KEYWORDS if kw in combined)
    return relevant_hits >= 3


def clean_text(text: str) -> str:
    """Normalize naming and clean up text."""
    if not text:
        return ""
    # Don't replace "Nola" when it's clearly referring to the demo identity
    # But normalize "Elaris" references (different product entirely)
    text = re.sub(r'\bElaris\b', 'the system', text)
    # Clean excessive whitespace
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    return text.strip()


def make_single_turn_examples(convo: dict) -> list:
    """Create one SFT example per conversation turn."""
    name = convo.get("name", "conversation")
    turns = convo.get("turns", [])
    examples = []
    
    for turn in turns:
        user_msg = clean_text(turn.get("user", ""))
        asst_msg = clean_text(turn.get("assistant", ""))
        
        if not user_msg or not asst_msg:
            continue
        # Skip very short responses (likely just acknowledgements)
        if len(asst_msg) < 50:
            continue
        # Skip very short prompts that lack context
        if len(user_msg) < 5:
            continue
        
        example = {
            "messages": [
                {"role": "system", "content": f"[conversation: {name}]"},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": asst_msg},
            ]
        }
        examples.append(example)
    
    return examples


def make_multi_turn_examples(convo: dict, window: int = 3) -> list:
    """Create windowed multi-turn SFT examples (2-3 turns of context)."""
    name = convo.get("name", "conversation")
    turns = convo.get("turns", [])
    examples = []
    
    for i in range(len(turns)):
        # Create a sliding window of turns
        start = max(0, i - window + 1)
        window_turns = turns[start:i + 1]
        
        # Need at least 2 viable turns for multi-turn
        viable = [t for t in window_turns 
                  if t.get("user", "").strip() and t.get("assistant", "").strip()]
        if len(viable) < 2:
            continue
        
        messages = [{"role": "system", "content": f"[conversation: {name}]"}]
        
        total_len = 0
        for t in viable:
            user_msg = clean_text(t.get("user", ""))
            asst_msg = clean_text(t.get("assistant", ""))
            if not user_msg or not asst_msg:
                continue
            # Budget: keep total under ~3000 chars to fit in 1024 tokens
            if total_len + len(user_msg) + len(asst_msg) > 3000:
                break
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": asst_msg})
            total_len += len(user_msg) + len(asst_msg)
        
        # Only keep if we got at least 2 user-assistant pairs
        user_count = sum(1 for m in messages if m["role"] == "user")
        if user_count >= 2:
            examples.append({"messages": messages})
    
    return examples


def main():
    convo_files = sorted(glob.glob(str(CONVO_DIR / "*.json")))
    print(f"Found {len(convo_files)} conversation files")
    
    relevant = []
    skipped = []
    
    for path in convo_files:
        with open(path) as f:
            convo = json.load(f)
        if is_relevant(convo):
            relevant.append(convo)
        else:
            skipped.append(convo.get("name", "?"))
    
    print(f"Relevant: {len(relevant)}, Skipped: {len(skipped)}")
    
    if skipped:
        print(f"\nSkipped conversations:")
        for name in sorted(skipped):
            print(f"  - {name}")
    
    # Generate examples
    single_examples = []
    multi_examples = []
    
    for convo in relevant:
        single_examples.extend(make_single_turn_examples(convo))
        multi_examples.extend(make_multi_turn_examples(convo))
    
    print(f"\nGenerated:")
    print(f"  Single-turn examples: {len(single_examples)}")
    print(f"  Multi-turn examples:  {len(multi_examples)}")
    
    # Deduplicate multi-turn examples (many overlaps from sliding window)
    # Use hash of user messages as dedup key
    seen = set()
    unique_multi = []
    for ex in multi_examples:
        key = tuple(m["content"][:100] for m in ex["messages"] if m["role"] == "user")
        if key not in seen:
            seen.add(key)
            unique_multi.append(ex)
    
    print(f"  Multi-turn (deduped):  {len(unique_multi)}")
    
    # Combine all
    all_examples = single_examples + unique_multi
    print(f"  Total:                 {len(all_examples)}")
    
    # Split: 90% train, 10% valid
    import random
    random.seed(42)
    random.shuffle(all_examples)
    
    split = int(len(all_examples) * 0.9)
    train = all_examples[:split]
    valid = all_examples[split:]
    
    # Write merged output — append to existing self_sft or write new convo_sft
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    convo_train_path = OUT_DIR / "convo_train.jsonl"
    convo_valid_path = OUT_DIR / "convo_valid.jsonl"
    
    with open(convo_train_path, "w") as f:
        for ex in train:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    with open(convo_valid_path, "w") as f:
        for ex in valid:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    print(f"\nWritten:")
    print(f"  {convo_train_path}: {len(train)} examples")
    print(f"  {convo_valid_path}: {len(valid)} examples")
    
    # Stats
    total_chars = sum(
        sum(len(m["content"]) for m in ex["messages"])
        for ex in all_examples
    )
    print(f"\nEstimated tokens: ~{total_chars // 4:,} (chars/4 heuristic)")


if __name__ == "__main__":
    main()
