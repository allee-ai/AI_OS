#!/usr/bin/env python3
"""Diagnostic: test generation quality + teacher-forced loss on known examples."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlx.core as mx
import mlx.nn as nn
from nola_net import NolaNET, NolaNETConfig
from train_nola import get_tokenizer

MODEL_DIR = os.path.join(os.path.dirname(__file__), "runs", "nola-0655da76", "final")

config = NolaNETConfig.load(os.path.join(MODEL_DIR, "config.json"))
model = NolaNET(config)
weights = mx.load(os.path.join(MODEL_DIR, "model.safetensors"))
model.load_weights(list(weights.items()))
tokenizer = get_tokenizer()
print(f"Loaded {config.param_count:,} params", flush=True)


def gen_with_penalty(prompt, max_tok=50, temp=0.7, rep_penalty=1.3):
    """Generate with repetition penalty and top-k."""
    ids = tokenizer.encode(prompt)
    if len(ids) > 64:
        ids = ids[:64]
    input_ids = mx.array([ids])
    generated = []
    seen = set()
    for _ in range(max_tok):
        logits = model(input_ids)
        next_logits = logits[0, -1, :]
        mx.eval(next_logits)
        
        # Repetition penalty
        logits_np = next_logits.tolist()
        for tok in seen:
            if logits_np[tok] > 0:
                logits_np[tok] /= rep_penalty
            else:
                logits_np[tok] *= rep_penalty
        
        next_logits = mx.array(logits_np) / temp
        
        # Top-k: only keep top 50 tokens
        top_k = 50
        sorted_indices = mx.argsort(next_logits)
        cutoff = next_logits[sorted_indices[-top_k]]
        mx.eval(cutoff)
        next_logits = mx.where(next_logits < cutoff, mx.array(float('-inf')), next_logits)
        
        next_token = mx.random.categorical(next_logits.reshape(1, -1))
        mx.eval(next_token)
        tok_id = next_token.item()
        if tok_id in (0, 1, 2):
            break
        generated.append(tok_id)
        seen.add(tok_id)
        
        # Sliding window
        all_ids = ids + generated
        if len(all_ids) > 80:
            all_ids = all_ids[-80:]
        input_ids = mx.array([all_ids])
    
    out = tokenizer.decode(generated)
    for stop in ["<|user|>", "<|system|>", "<|end"]:
        if stop in out:
            out = out[:out.index(stop)]
    return out.strip()


def teacher_forced_loss(text):
    """Compute loss when the model is given the right answer."""
    ids = tokenizer.encode(text)
    if len(ids) > 256:
        ids = ids[:256]
    x = mx.array([ids[:-1]])
    y = mx.array([ids[1:]])
    logits = model(x)
    loss = nn.losses.cross_entropy(logits, y).mean()
    mx.eval(loss)
    return loss.item()


# ── Part 1: Teacher-forced evaluation ──
print("\n" + "=" * 60)
print("TEACHER-FORCED LOSS (lower = better, <2 = memorized)")
print("=" * 60, flush=True)

# Read a few actual training examples
sft_path = os.path.join(os.path.dirname(__file__), "self_sft", "train.jsonl")
with open(sft_path) as f:
    lines = f.readlines()

for i in [0, 100, 500, 800]:
    if i >= len(lines):
        continue
    data = json.loads(lines[i])
    msgs = data.get("messages", [])
    text = ""
    for m in msgs:
        role = m["role"]
        content = m["content"]
        if role == "system":
            text += f"<|system|>\n{content}\n"
        elif role == "user":
            text += f"<|user|>\n{content}\n"
        elif role == "assistant":
            text += f"<|assistant|>\n{content}\n"
    loss = teacher_forced_loss(text)
    preview = text.replace("\n", " ")[:80]
    print(f"  Example {i}: loss={loss:.3f}  |  {preview}...", flush=True)

# Also test on completely unseen text
print(f"\n  Unseen random text: loss={teacher_forced_loss('The quick brown fox jumped over the lazy dog and ran away.'):.3f}", flush=True)
print(f"  Unseen code: loss={teacher_forced_loss('function hello() { return 42; }'):.3f}", flush=True)

# ── Part 2: Generation with repetition penalty ──
print("\n" + "=" * 60)
print("GENERATION (temp=0.7, rep_penalty=1.3, top_k=50)")
print("=" * 60, flush=True)

prompts = [
    "<|user|>\nWho are you?\n<|assistant|>\n",
    "<|user|>\nWhat is STATE?\n<|assistant|>\n",
    "<|user|>\nWhat threads do you have?\n<|assistant|>\n",
    "I am Nola. ",
    "STATE is ",
    "The identity thread ",
]

for p in prompts:
    label = p.replace("\n", " ").strip()[:50]
    print(f"\n> {label}", flush=True)
    out = gen_with_penalty(p, max_tok=50, temp=0.7, rep_penalty=1.3)
    print(f"  {out[:300]}", flush=True)

print("\nDone.", flush=True)
