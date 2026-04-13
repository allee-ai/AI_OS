#!/usr/bin/env python3
"""Count all Phase 2 SFT data that will be loaded by train_nola.py."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from train_nola import get_tokenizer, load_sft_file, load_sft_data
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_SEQ = 1024

tokenizer = get_tokenizer()
sft_examples = []

# Self-SFT original
self_sft_dir = ROOT / "experiments" / "self_sft"
if (self_sft_dir / "train.jsonl").exists():
    convo_sft = load_sft_data(str(self_sft_dir), tokenizer, max_seq=MAX_SEQ)
    sft_examples.extend(convo_sft)
    print(f"Self-SFT original: {len(convo_sft)}")

# Conversation mining
convo_train = self_sft_dir / "convo_train.jsonl"
if convo_train.exists():
    convo_mined = load_sft_file(str(convo_train), tokenizer, max_seq=MAX_SEQ)
    sft_examples.extend(convo_mined)
    print(f"Conversation mining: {len(convo_mined)}")

# Gold demos
demo_gold = self_sft_dir / "demo_gold.jsonl"
if demo_gold.exists():
    gold = load_sft_file(str(demo_gold), tokenizer, max_seq=MAX_SEQ)
    sft_examples.extend(gold * 5)
    print(f"Demo gold: {len(gold)} x5 = {len(gold)*5}")

# Finetune files
extra_files = [
    ROOT / "finetune" / f"{n}_train.jsonl"
    for n in ["behavioral","identity","philosophy","form","reflex",
              "log","linking_core","docs","reasoning","chat"]
]
readme_dir = ROOT / "finetune" / "readme_pairs"
if readme_dir.exists():
    extra_files.extend(sorted(readme_dir.glob("*.jsonl")))
gen_dir = ROOT / "finetune" / "generated"
if gen_dir.exists():
    extra_files.extend(sorted(gen_dir.glob("*.jsonl")))
for p in extra_files:
    if p.exists():
        ex = load_sft_file(str(p), tokenizer, max_seq=MAX_SEQ)
        if ex:
            sft_examples.extend(ex)
            print(f"  + {len(ex):>5d} from {p.name}")

print(f"\n{'='*50}")
print(f"TOTAL Phase 2 examples: {len(sft_examples)}")
total_tokens = sum(len(e) for e in sft_examples)
print(f"Total tokens: {total_tokens:,}")
print(f"Avg tokens/example: {total_tokens/len(sft_examples):.0f}")
print(f"Est training tokens @ 5 epochs: {total_tokens * 5:,}")
