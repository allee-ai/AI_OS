#!/usr/bin/env python3
"""Chat with the trained NolaNET model."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlx.core as mx
from nola_net import NolaNET, NolaNETConfig
from train_nola import get_tokenizer

MODEL_DIR = os.path.join(os.path.dirname(__file__), "runs", "nola-0655da76", "final")


def load_model():
    config = NolaNETConfig.load(os.path.join(MODEL_DIR, "config.json"))
    model = NolaNET(config)
    weights = mx.load(os.path.join(MODEL_DIR, "model.safetensors"))
    model.load_weights(list(weights.items()))
    return model, config


def chat(model, tokenizer, prompt, max_tokens=60, temperature=0.6):
    text = f"<|user|>\n{prompt}\n<|assistant|>\n"
    ids = tokenizer.encode(text)
    # Keep prompt short to speed up generation
    if len(ids) > 128:
        ids = ids[:128]
    generated = []
    input_ids = mx.array([ids])

    print("  ", end="", flush=True)
    for i in range(max_tokens):
        logits = model(input_ids)
        next_logits = logits[:, -1, :] / temperature
        next_token = mx.random.categorical(next_logits)
        mx.eval(next_token)
        tok_id = next_token.item()
        if tok_id in (0, 1, 2):  # pad/bos/eos
            break
        generated.append(tok_id)
        # Decode incrementally
        word = tokenizer.decode([tok_id])
        print(word, end="", flush=True)
        # Only keep last 64 tokens as context (sliding window)
        ids = ids[-63:] + [tok_id]
        input_ids = mx.array([ids])
        # Stop at special tokens in output
        partial = tokenizer.decode(generated)
        for stop in ["<|user|>", "<|system|>", "<|end"]:
            if stop in partial:
                print()
                return partial[:partial.index(stop)].strip()

    print()
    return tokenizer.decode(generated).strip()


def main():
    print("Loading NolaNET...")
    model, config = load_model()
    tokenizer = get_tokenizer()
    print(f"Loaded: {config.param_count:,} params, vocab={config.vocab_size}")
    print()

    prompts = [
        "What is STATE?",
        "What threads do you have?",
        "How does the concept graph work?",
        "What happens when a schema drifts?",
        "Who are you?",
        "What is linking_core?",
        "Explain how the training pipeline works.",
        "What is the subconscious?",
    ]

    for p in prompts:
        print(f"> {p}")
        r = chat(model, tokenizer, p)
        print(f"  {r}")
        print()


if __name__ == "__main__":
    main()
