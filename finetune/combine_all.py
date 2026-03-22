#!/usr/bin/env python3
"""Quick combine: merge all training sources into aios_combined.jsonl"""
import json
from pathlib import Path

FT = Path(__file__).parent
combined = FT / "aios_combined.jsonl"
total = 0

with open(combined, "w") as out:
    # 1. Module-exported training data
    for f in sorted(FT.glob("*_train.jsonl")):
        for line in open(f):
            if line.strip():
                out.write(line if line.endswith("\n") else line + "\n")
                total += 1

    # 2. Generated (synthetic) examples
    gen_dir = FT / "generated"
    gen_count = 0
    if gen_dir.exists():
        for f in sorted(gen_dir.glob("*.jsonl")):
            for line in open(f):
                if line.strip():
                    out.write(line if line.endswith("\n") else line + "\n")
                    total += 1
                    gen_count += 1

    # 3. User-approved responses
    approved = FT / "user_approved.jsonl"
    approved_count = 0
    if approved.exists():
        for line in open(approved):
            if line.strip():
                out.write(line if line.endswith("\n") else line + "\n")
                total += 1
                approved_count += 1

    # 4. Curated pairs
    curated_dir = FT / "readme_pairs"
    curated_count = 0
    if curated_dir.exists():
        for f in sorted(curated_dir.glob("*.jsonl")):
            for line in open(f):
                if line.strip():
                    out.write(line if line.endswith("\n") else line + "\n")
                    total += 1
                    curated_count += 1

print(f"Combined {total} examples -> {combined.name}")
print(f"  module exports: {total - gen_count - approved_count - curated_count}")
print(f"  generated: {gen_count}")
print(f"  user_approved: {approved_count}")
print(f"  curated: {curated_count}")
