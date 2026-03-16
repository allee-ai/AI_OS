#!/usr/bin/env python3
"""
Run training data generation for all 17 modules using kimi-k2 teacher model.
Each module generates 5 synthetic training examples from actual source code.

Usage: python3 scripts/run_training_gen.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AIOS_TRAINING_GEN_MODEL", "kimi-k2:1t-cloud")

from agent.subconscious.loops.training_gen import TrainingGenLoop, MODULES, GENERATED_DIR

# Files too large for module-level budget that deserve dedicated passes
EXTRA_FILES = [
    ("agent/core/mcp_client.py", "agent_core"),
    ("agent/core/models_api.py", "agent_core"),
    ("agent/core/secrets.py", "agent_core"),
]

def main():
    loop = TrainingGenLoop(enabled=True)
    print(f"Generating for {len(MODULES)} modules using {loop.model}")
    print(f"Output: {GENERATED_DIR}")
    print("---")

    # Count existing before
    existing = {}
    for m in MODULES:
        f = GENERATED_DIR / f"{m}.jsonl"
        existing[m] = sum(1 for _ in open(f)) if f.exists() else 0

    total = 0
    for i, module in enumerate(MODULES, 1):
        print(f"[{i}/{len(MODULES)}] {module}...", end=" ", flush=True)
        try:
            count = loop._generate_for_module(module)
            total += count
            print(f"{count} examples generated")
        except Exception as e:
            print(f"ERROR: {e}")

    # File-level passes for large modules with important files outside budget
    for rel_path, module in EXTRA_FILES:
        full = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel_path)
        if os.path.exists(full):
            print(f"[file] {rel_path}...", end=" ", flush=True)
            try:
                count = loop.generate_for_file(rel_path, module)
                total += count
                print(f"{count} examples generated")
            except Exception as e:
                print(f"ERROR: {e}")

    print("---")
    print(f"Total new examples: {total}")
    for m in MODULES:
        f = GENERATED_DIR / f"{m}.jsonl"
        now = sum(1 for _ in open(f)) if f.exists() else 0
        delta = now - existing[m]
        print(f"  {m}: {existing[m]} -> {now} (+{delta})")

if __name__ == "__main__":
    main()
