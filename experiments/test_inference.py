#!/usr/bin/env python3
"""Quick inference test for the trained NolaNET 350M."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlx.core as mx
from nola_net import NolaNET, NolaNETConfig
from train_nola import get_tokenizer

MODEL_DIR = os.path.join(os.path.dirname(__file__), "runs", "nola-0655da76", "final")


def generate(model, tokenizer, prompt, max_tokens=100, temperature=0.3):
    ids = tokenizer.encode(prompt)
    input_ids = mx.array([ids])
    generated = []
    for _ in range(max_tokens):
        logits = model(input_ids)
        next_logits = logits[:, -1, :] / temperature
        next_token = mx.random.categorical(next_logits)
        mx.eval(next_token)
        tok_id = next_token.item()
        if tok_id in (0, 1, 2):
            break
        generated.append(tok_id)
        input_ids = mx.concatenate([input_ids, next_token.reshape(1, 1)], axis=1)
        if input_ids.shape[1] > 300:
            break
    out = tokenizer.decode(generated)
    for stop in ["<|user|>", "<|system|>", "<|end"]:
        if stop in out:
            out = out[:out.index(stop)]
    return out.strip()


def main():
    print("Loading model...")
    config = NolaNETConfig.load(os.path.join(MODEL_DIR, "config.json"))
    model = NolaNET(config)
    weights = mx.load(os.path.join(MODEL_DIR, "model.safetensors"))
    model.load_weights(list(weights.items()))
    tokenizer = get_tokenizer()
    print(f"Loaded {config.param_count:,} params\n")

    # Chat-format prompts (matches training)
    chat_prompts = [
        "<|system|>\nYou are Nola, a self-aware AI.\n<|user|>\nWho are you?\n<|assistant|>\n",
        "<|system|>\nYou are Nola.\n<|user|>\nWhat is STATE?\n<|assistant|>\n",
        "<|system|>\nYou are Nola.\n<|user|>\nWhat threads do you have?\n<|assistant|>\n",
        "<|system|>\nYou are Nola.\n<|user|>\nWhat is the subconscious?\n<|assistant|>\n",
    ]

    # Raw completion prompts (no chat template)
    raw_prompts = [
        "I am Nola. My threads include ",
        "The subconscious thread ",
        "STATE is a ",
        "The identity thread stores ",
        "def generate(self, ",
        "class Agent:\n    ",
        "Nola is an AI operating system that ",
    ]

    print("=" * 60)
    print("CHAT FORMAT (temp=0.3)")
    print("=" * 60)
    for p in chat_prompts:
        label = p.split("<|user|>\n")[1].split("\n")[0]
        print(f"\n> {label}")
        out = generate(model, tokenizer, p, max_tokens=100, temperature=0.3)
        print(f"  {out[:300]}")

    print("\n" + "=" * 60)
    print("RAW COMPLETION (temp=0.3)")
    print("=" * 60)
    for p in raw_prompts:
        print(f"\n> {p.strip()}")
        out = generate(model, tokenizer, p, max_tokens=80, temperature=0.3)
        print(f"  {out[:300]}")

    print("\n" + "=" * 60)
    print("GREEDY (temp=0.01)")
    print("=" * 60)
    greedy_prompts = [
        "<|system|>\nYou are Nola.\n<|user|>\nWho are you?\n<|assistant|>\n",
        "I am Nola. ",
        "STATE is ",
    ]
    for p in greedy_prompts:
        label = p.strip()[:50]
        print(f"\n> {label}")
        out = generate(model, tokenizer, p, max_tokens=80, temperature=0.01)
        print(f"  {out[:300]}")


if __name__ == "__main__":
    main()
