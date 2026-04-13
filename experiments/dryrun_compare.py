#!/usr/bin/env python3
"""Test multiple model/seq_len combos to find what fits."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlx.core as mx
import mlx.nn as nn
from nola_net import NolaNET, NOLA_350M, NOLA_250M

def get_mem():
    try:
        return mx.get_active_memory() / 1e9, mx.get_peak_memory() / 1e9
    except Exception:
        try:
            return mx.metal.get_active_memory() / 1e9, mx.metal.get_peak_memory() / 1e9
        except Exception:
            return -1, -1

def test(label, config, seq):
    print(f"\n{'='*50}")
    print(f"{label}: {config.param_count/1e6:.0f}M, {config.num_layers}L, seq={seq}")
    
    # Reset memory tracking
    try:
        mx.reset_peak_memory()
    except Exception:
        pass
    
    model = NolaNET(config)
    
    # Forward
    dummy = mx.array([[1] * seq])
    logits = model(dummy)
    mx.eval(logits)
    a, p = get_mem()
    print(f"  Forward:  active={a:.1f}GB, peak={p:.1f}GB")
    
    # Backward
    def loss_fn(m, x, y):
        out = m(x)
        return nn.losses.cross_entropy(out[:, :-1, :], y[:, 1:]).mean()
    
    loss_and_grad = nn.value_and_grad(model, loss_fn)
    x = mx.array([[1] * seq])
    y = mx.array([[1] * seq])
    loss, grads = loss_and_grad(model, x, y)
    mx.eval(loss, grads)
    a, p = get_mem()
    print(f"  Backward: active={a:.1f}GB, peak={p:.1f}GB, loss={loss.item():.2f}")
    print(f"  PASSED")
    
    del model, logits, grads, loss
    mx.eval(mx.array([0]))  # flush

# Test 250M at 2048 first (most likely to work)
test("250M @ 2048", NOLA_250M, 2048)
# Then confirm 350M at 1024
test("350M @ 1024", NOLA_350M, 1024)
