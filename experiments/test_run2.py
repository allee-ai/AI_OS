#!/usr/bin/env python3
"""Quick test of Run 2 model with bigger context window."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mlx.core as mx
from nola_net import NolaNET, NolaNETConfig
from train_nola import get_tokenizer

MODEL_DIR = os.path.join(os.path.dirname(__file__), "runs", "nola-f911a41e", "final")

config = NolaNETConfig.load(os.path.join(MODEL_DIR, "config.json"))
model = NolaNET(config)
weights = mx.load(os.path.join(MODEL_DIR, "model.safetensors"))
model.load_weights(list(weights.items()))
tokenizer = get_tokenizer()
print(f"Loaded: {config.param_count:,} params, vocab={config.vocab_size}")

def gen(prompt, max_tokens=80, temp=0.3):
    text = f"<|user|>\n{prompt}\n<|assistant|>\n"
    ids = tokenizer.encode(text)
    prompt_len = len(ids)
    for i in range(max_tokens):
        input_ids = mx.array([ids[-256:]])
        logits = model(input_ids)
        next_logits = logits[:, -1, :] / temp
        next_token = mx.random.categorical(next_logits)
        mx.eval(next_token)
        tok_id = next_token.item()
        if tok_id in (0, 1, 2):
            break
        ids.append(tok_id)
        partial = tokenizer.decode(ids[prompt_len:])
        for stop in ["<|user|>", "<|system|>"]:
            if stop in partial:
                return partial[:partial.index(stop)].strip()
    return tokenizer.decode(ids[prompt_len:]).strip()

prompts = [
    "What is STATE?",
    "Who are you?",
    "What threads do you have?",
    "What is linking_core?",
    "What is the subconscious?",
    "How does the agent work?",
]

for p in prompts:
    print(f"\n> {p}")
    print(f"  {gen(p)}")
