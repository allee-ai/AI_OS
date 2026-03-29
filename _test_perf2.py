"""Quick perf test for training data endpoints — delete after use."""
import time, json

# Test 1: _get_all_examples_for_module
from finetune.api import _get_all_examples_for_module, ALL_MODULES

print("=== _get_all_examples_for_module ===")
for name in ALL_MODULES:
    t0 = time.perf_counter()
    exs = _get_all_examples_for_module(name)
    t1 = time.perf_counter()
    print(f"  {name}: {len(exs)} examples in {(t1-t0)*1000:.0f}ms")

# Test 2: module sections (counts only)
print("\n=== get_module_sections simulation ===")
for name in ALL_MODULES:
    t0 = time.perf_counter()
    from finetune.api import _import_train_module, _get_curated_count
    mod = _import_train_module(name)
    sections = mod.get_sections()
    try:
        from agent.subconscious.loops.training_gen import get_generated_counts_by_type
        ds, nd = get_generated_counts_by_type(name)
    except Exception:
        ds, nd = {}, 0
    curated = _get_curated_count(name)
    t1 = time.perf_counter()
    print(f"  {name}: {(t1-t0)*1000:.0f}ms  sections={list(sections.keys())} gen_ds={ds} gen_other={nd} curated={curated}")

# Test 3: unified page 1
print("\n=== /unified page 1 simulation ===")
from finetune.api import _count_lines_cached, FINETUNE_DIR
from agent.subconscious.loops.training_gen import get_generated_count
from finetune.gold_examples import get_reasoning_count_for_module

t0 = time.perf_counter()
total = 0
for name in ALL_MODULES:
    c = _count_lines_cached(FINETUNE_DIR / f"{name}_train.jsonl")
    c += get_reasoning_count_for_module(name)
    c += get_generated_count(name)
    c += _get_curated_count(name)
    c += _count_lines_cached(FINETUNE_DIR / "approved" / f"{name}.jsonl")
    total += c
t1 = time.perf_counter()
print(f"  Count total: {total} in {(t1-t0)*1000:.0f}ms")

# Load just first module page
t0 = time.perf_counter()
exs = _get_all_examples_for_module(ALL_MODULES[0])[:50]
t1 = time.perf_counter()
print(f"  Load page 1 (first module): {len(exs)} in {(t1-t0)*1000:.0f}ms")
