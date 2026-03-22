#!/usr/bin/env python3
"""
Combine all AIOS training data into final train.jsonl / valid.jsonl

Merges:
  1. Existing system knowledge (finetune/train.jsonl, valid.jsonl)
  2. Curated README pairs (finetune/readme_pairs/*.jsonl)
  3. Conversation chunks (finetune/convo_chunks/train.jsonl, valid.jsonl)

Outputs combined files ready for MLX training.
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FT_DIR = ROOT / "finetune"

def load_jsonl(path):
    """Load a JSONL file, return list of dicts."""
    if not path.exists():
        return []
    examples = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            examples.append(json.loads(line))
    return examples


def tag_source(examples, source_tag):
    """Add source tag to metadata if missing."""
    for ex in examples:
        if "metadata" not in ex or ex["metadata"] is None:
            ex["metadata"] = {}
        if "pipeline_source" not in ex["metadata"]:
            ex["metadata"]["pipeline_source"] = source_tag
    return examples


def main():
    print("=== AIOS Combined Data Pipeline ===")
    print()

    # ── 1. Load existing system knowledge ──
    existing_train = load_jsonl(FT_DIR / "train.jsonl")
    existing_valid = load_jsonl(FT_DIR / "valid.jsonl")
    tag_source(existing_train, "system_knowledge")
    tag_source(existing_valid, "system_knowledge")
    print(f"System knowledge: {len(existing_train)} train, {len(existing_valid)} valid")

    # ── 2. Load curated README pairs ──
    readme_dir = FT_DIR / "readme_pairs"
    curated = []
    if readme_dir.exists():
        for f in sorted(readme_dir.glob("*.jsonl")):
            curated.extend(load_jsonl(f))
    tag_source(curated, "curated_pairs")
    # Split curated 90/10
    random.seed(42)
    random.shuffle(curated)
    split_idx = max(1, int(len(curated) * 0.9))
    curated_train = curated[:split_idx]
    curated_valid = curated[split_idx:]
    print(f"Curated pairs:    {len(curated_train)} train, {len(curated_valid)} valid")

    # ── 3. Load conversation chunks ──
    convo_dir = FT_DIR / "convo_chunks"
    convo_train = load_jsonl(convo_dir / "train.jsonl")
    convo_valid = load_jsonl(convo_dir / "valid.jsonl")
    tag_source(convo_train, "conversations")
    tag_source(convo_valid, "conversations")
    print(f"Conversations:    {len(convo_train)} train, {len(convo_valid)} valid")

    # ── 4. Combine everything ──
    all_train = existing_train + curated_train + convo_train
    all_valid = existing_valid + curated_valid + convo_valid

    # Shuffle training data (mix sources for better generalization)
    random.seed(42)
    random.shuffle(all_train)
    random.shuffle(all_valid)

    print()
    print(f"COMBINED: {len(all_train)} train, {len(all_valid)} valid")
    print(f"  Total: {len(all_train) + len(all_valid)} examples")

    # Source breakdown
    sources = {}
    for ex in all_train + all_valid:
        src = (ex.get("metadata") or {}).get("pipeline_source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    print()
    print("Source breakdown:")
    for src, count in sorted(sources.items()):
        print(f"  {src}: {count}")

    # ── 5. Write combined output ──
    runs_dir = FT_DIR / "runs" / "full-v1"
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Write to the runs directory (training reads from here)
    train_path = runs_dir / "train.jsonl"
    valid_path = runs_dir / "valid.jsonl"

    with open(train_path, "w") as f:
        for ex in all_train:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(valid_path, "w") as f:
        for ex in all_valid:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print()
    print(f"Written to:")
    print(f"  {train_path}  ({len(all_train)} examples)")
    print(f"  {valid_path}  ({len(all_valid)} examples)")

    # Quick stats
    print()
    print("=== Ready to train ===")
    print(f"  python3 -m mlx_lm.lora \\")
    print(f"    --model mlx-community/Qwen2.5-1.5B-Instruct-4bit \\")
    print(f"    --data {runs_dir} \\")
    print(f"    --train --iters 2000 \\")
    print(f"    --batch-size 1 --grad-checkpoint \\")
    print(f"    --num-layers 8 \\")
    print(f"    --adapter-path {runs_dir}/adapters \\")
    print(f"    --learning-rate 1e-5 \\")
    print(f"    --steps-per-report 50 --steps-per-eval 200 --save-every 200 \\")
    print(f"    --max-seq-length 2048 --seed 42")


if __name__ == "__main__":
    main()
