#!/usr/bin/env python3
"""
Build the Layer 2 self-knowledge SFT dataset.

Combines all self-referential training data:
  - Thread-specific JSOLNs (identity, philosophy, form, log, reflex, linking_core, chat, docs)
  - Reasoning examples
  - Gold examples
  - Filtered conversations where we discuss the system (first/second person)

Output: experiments/self_sft/train.jsonl + valid.jsonl (90/10 split)
"""
import json
import os
import re
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "experiments", "self_sft")
CONVO_DIR = os.path.join(ROOT, "Feeds", "conversations")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Self-knowledge signal filter ────────────────────────────────────────
# A turn qualifies if it mentions enough architecture/design terms.

_SIGNAL_WORDS = {
    "STATE", "thread", "introspect", "orchestrator", "subconscious",
    "linking_core", "identity", "philosophy", "reflex", "spread_activate",
    "concept_graph", "unified_events", "temp_memory", "consolidation",
    "adapter", "schema", "migration", "log_event", "polling",
    "BackgroundLoop", "LoopManager", "workspace", "tool_traces",
    "Layer 1", "Layer 2", "Layer 3", "self-SFT", "pretrain",
    "finetune", "MLX", "LoRA", "training pipeline",
    "NameError", "TypeError", "OperationalError", "schema_drift",
    "signature_mismatch", "model_routing", "db_lock",
    "silent failure", "silently", "bug", "breakage",
    "proprioception", "self-model", "self-knowledge", "consciousness",
    "interoception", "Hebbian",
}

_SIGNAL_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in _SIGNAL_WORDS) + r')\b',
    re.IGNORECASE,
)
_MIN_SIGNAL_HITS = 3
_MAX_TOKENS_ESTIMATE = 2048


def _is_self_knowledge_turn(user_text: str, assistant_text: str) -> bool:
    combined = f"{user_text} {assistant_text}"
    hits = len(set(m.lower() for m in _SIGNAL_PATTERN.findall(combined)))
    return hits >= _MIN_SIGNAL_HITS

# ── Collect all self-knowledge examples ─────────────────────────────────

all_examples = []

# Thread-specific training data
thread_files = [
    "identity_train", "philosophy_train", "form_train", "log_train",
    "reflex_train", "linking_core_train", "chat_train", "docs_train",
    "reasoning_train",
]

for fname in thread_files:
    path = os.path.join(ROOT, "finetune", f"{fname}.jsonl")
    if not os.path.exists(path):
        print(f"  SKIP {fname} (not found)")
        continue
    with open(path) as fh:
        lines = [json.loads(l) for l in fh if l.strip()]
    all_examples.extend(lines)
    print(f"  + {fname}: {len(lines)} examples")

# Gold examples
try:
    from finetune.gold_examples import get_reasoning_examples
    gold = get_reasoning_examples()
    all_examples.extend(gold)
    print(f"  + gold_examples: {len(gold)} examples")
except Exception as e:
    print(f"  SKIP gold_examples: {e}")

# Conversations — filtered for self-knowledge content
print(f"\nScanning conversations in {CONVO_DIR}...")
convo_examples = []
convo_files_hit = 0
EXCLUDE_IDS = {"a4bd5e26", "8858ad09", "bbfb2a1f"}

if os.path.isdir(CONVO_DIR):
    for fname in sorted(os.listdir(CONVO_DIR)):
        if not fname.endswith(".json"):
            continue
        if any(eid in fname for eid in EXCLUDE_IDS):
            continue
        fpath = os.path.join(CONVO_DIR, fname)
        data = json.loads(open(fpath).read())
        turns = data.get("turns", [])
        title = data.get("name", "untitled")

        # Find consecutive runs of self-knowledge turns
        current_run = []
        runs = []
        for t in turns:
            u = (t.get("user") or "").strip()
            a = (t.get("assistant") or "").strip()
            if not u or not a:
                if current_run:
                    runs.append(current_run)
                    current_run = []
                continue
            if _is_self_knowledge_turn(u, a):
                current_run.append(t)
            else:
                if current_run:
                    runs.append(current_run)
                    current_run = []
        if current_run:
            runs.append(current_run)

        # Window runs into training examples
        for run in runs:
            convo_files_hit += 1
            i = 0
            while i < len(run):
                window = run[i:i + 3]
                msgs = [{"role": "system", "content": f"[conversation: {title}]"}]
                for t in window:
                    msgs.append({"role": "user", "content": t["user"].strip()})
                    msgs.append({"role": "assistant", "content": t["assistant"].strip()})
                # Trim if too long
                while len(msgs) > 3 and len(" ".join(m["content"] for m in msgs)) // 4 > _MAX_TOKENS_ESTIMATE:
                    msgs = msgs[:-2]
                if len(msgs) >= 3:
                    convo_examples.append({"messages": msgs})
                i += 2  # stride

all_examples.extend(convo_examples)
print(f"  + conversations: {len(convo_examples)} examples from {convo_files_hit} runs")

print(f"\nTotal self-knowledge examples: {len(all_examples)}")

# ── Deduplicate by user message ─────────────────────────────────────────

seen = set()
deduped = []
for ex in all_examples:
    if "messages" not in ex:
        continue
    # Get user message for dedup key
    user_msgs = [m["content"] for m in ex["messages"] if m["role"] == "user"]
    key = tuple(user_msgs)
    if key in seen:
        continue
    seen.add(key)
    deduped.append(ex)

print(f"After dedup: {len(deduped)} examples (removed {len(all_examples) - len(deduped)} dupes)")

# ── Split 90/10 ─────────────────────────────────────────────────────────

random.seed(42)
random.shuffle(deduped)

split = int(len(deduped) * 0.9)
train = deduped[:split]
valid = deduped[split:]

# ── Write output ────────────────────────────────────────────────────────

train_path = os.path.join(OUT_DIR, "train.jsonl")
valid_path = os.path.join(OUT_DIR, "valid.jsonl")

with open(train_path, "w") as f:
    for ex in train:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")

with open(valid_path, "w") as f:
    for ex in valid:
        f.write(json.dumps(ex, ensure_ascii=False) + "\n")

print(f"\nWritten:")
print(f"  train: {len(train)} examples -> {train_path}")
print(f"  valid: {len(valid)} examples -> {valid_path}")
print(f"  train size: {os.path.getsize(train_path):,} bytes")
print(f"  valid size: {os.path.getsize(valid_path):,} bytes")
