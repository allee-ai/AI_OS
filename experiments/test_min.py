#!/usr/bin/env python3
"""Minimal inference test — 3 prompts, 30 tokens each."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlx.core as mx
from nola_net import NolaNET, NolaNETConfig
from train_nola import get_tokenizer

MODEL_DIR = os.path.join(os.path.dirname(__file__), "runs", "nola-0655da76", "final")

config = NolaNETConfig.load(os.path.join(MODEL_DIR, "config.json"))
model = NolaNET(config)
weights = mx.load(os.path.join(MODEL_DIR, "model.safetensors"))
model.load_weights(list(weights.items()))
tokenizer = get_tokenizer()
print(f"Loaded {config.param_count:,} params", flush=True)


def gen(prompt, max_tok=30, temp=0.3):
    ids = tokenizer.encode(prompt)
    if len(ids) > 48:
        ids = ids[:48]
    input_ids = mx.array([ids])
    generated = []
    t0 = time.time()
    for _ in range(max_tok):
        logits = model(input_ids)
        next_logits = logits[:, -1, :] / temp
        next_token = mx.random.categorical(next_logits)
        mx.eval(next_token)
        tok_id = next_token.item()
        if tok_id in (0, 1, 2):
            break
        generated.append(tok_id)
        # Use sliding window like chat_nola.py to keep it fast
        all_ids = ids + generated
        if len(all_ids) > 64:
            all_ids = all_ids[-64:]
        input_ids = mx.array([all_ids])
    dt = time.time() - t0
    out = tokenizer.decode(generated)
    for stop in ["<|user|>", "<|system|>", "<|end"]:
        if stop in out:
            out = out[:out.index(stop)]
    return out.strip(), len(generated), dt


tests = [
    "<|user|>\nWho are you?\n<|assistant|>\n",
    "<|user|>\nWhat is STATE?\n<|assistant|>\n",
    "I am Nola. My threads include ",
    "STATE is a ",
    "The subconscious thread ",
    "def generate(self, ",
]

for p in tests:
    label = p.replace("\n", " ").strip()[:50]
    print(f"\n> {label}", flush=True)
    out, ntok, dt = gen(p)
    print(f"  [{ntok} tok, {dt:.1f}s] {out[:250]}", flush=True)

print("\nDone.", flush=True)
