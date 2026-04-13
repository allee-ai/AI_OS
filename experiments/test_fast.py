#!/usr/bin/env python3
"""Fast inference test — fewer tokens, fewer prompts."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlx.core as mx
from nola_net import NolaNET, NolaNETConfig
from train_nola import get_tokenizer
import time

MODEL_DIR = os.path.join(os.path.dirname(__file__), "runs", "nola-0655da76", "final")

config = NolaNETConfig.load(os.path.join(MODEL_DIR, "config.json"))
model = NolaNET(config)
weights = mx.load(os.path.join(MODEL_DIR, "model.safetensors"))
model.load_weights(list(weights.items()))
tokenizer = get_tokenizer()
print(f"Loaded {config.param_count:,} params")


def gen(prompt, max_tok=40, temp=0.3):
    ids = tokenizer.encode(prompt)
    # Truncate prompt to keep it short
    if len(ids) > 64:
        ids = ids[:64]
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
        input_ids = mx.concatenate([input_ids, next_token.reshape(1, 1)], axis=1)
    dt = time.time() - t0
    out = tokenizer.decode(generated)
    for stop in ["<|user|>", "<|system|>", "<|end"]:
        if stop in out:
            out = out[:out.index(stop)]
    print(f"  [{len(generated)} tok, {dt:.1f}s] {out.strip()[:200]}")


prompts = [
    ("CHAT", "<|system|>\nYou are Nola.\n<|user|>\nWho are you?\n<|assistant|>\n"),
    ("CHAT", "<|system|>\nYou are Nola.\n<|user|>\nWhat is STATE?\n<|assistant|>\n"),
    ("RAW", "I am Nola. My threads include "),
    ("RAW", "STATE is a "),
    ("RAW", "The subconscious thread "),
    ("RAW", "def generate(self, "),
    ("GREEDY", "I am Nola. "),
]

for label, p in prompts:
    temp = 0.01 if label == "GREEDY" else 0.3
    short = p.replace("\n", " ").strip()[:50]
    print(f"\n[{label}] > {short}")
    gen(p, max_tok=40, temp=temp)
