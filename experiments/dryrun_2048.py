#!/usr/bin/env python3
"""Dry run: can 350M fit seq_len=2048 on 16GB?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlx.core as mx
import mlx.nn as nn
from nola_net import NolaNET, NOLA_350M, NOLA_250M

for label, config, seq in [("250M @ 2048", NOLA_250M, 2048), ("350M @ 1024", NOLA_350M, 1024)]:
    print(f"\n{'='*50}")
    print(f"Testing: {label}")
    model = NolaNET(config)
    print(f"  {config.param_count/1e6:.0f}M params, {config.num_layers} layers, seq={seq}")

# Forward
dummy = mx.array([[1] * SEQ])
print(f"Forward pass at seq_len={SEQ}...")
logits = model(dummy)
mx.eval(logits)
print(f"Forward OK. Shape: {logits.shape}")

try:
    mem = mx.get_active_memory() / 1e9
    peak = mx.get_peak_memory() / 1e9
    print(f"Memory after forward: active={mem:.1f}GB, peak={peak:.1f}GB")
except Exception:
    try:
        mem = mx.metal.get_active_memory() / 1e9
        peak = mx.metal.get_peak_memory() / 1e9
        print(f"Memory after forward: active={mem:.1f}GB, peak={peak:.1f}GB")
    except Exception:
        pass

# Backward
print("Backward pass...")

def loss_fn(model, x, y):
    logits = model(x)
    return nn.losses.cross_entropy(logits[:, :-1, :], y[:, 1:]).mean()

loss_and_grad = nn.value_and_grad(model, loss_fn)
x = mx.array([[1] * SEQ])
y = mx.array([[1] * SEQ])
loss, grads = loss_and_grad(model, x, y)
mx.eval(loss, grads)
print(f"Backward OK. Loss: {loss.item():.3f}")

try:
    mem = mx.metal.get_active_memory() / 1e9
    peak = mx.metal.get_peak_memory() / 1e9
    print(f"Memory after backward: active={mem:.1f}GB, peak={peak:.1f}GB")
except Exception:
    pass

print(f"PASSED - seq_len={SEQ} fits!")
