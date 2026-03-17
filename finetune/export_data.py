#!/usr/bin/env python3
"""Quick export: combine all train files + generated into aios_base.jsonl"""
import json
from pathlib import Path

FT = Path(__file__).parent
GEN = FT / "generated"
out_path = FT / "aios_base.jsonl"

total = 0
gen_count = 0

with open(out_path, "w") as out:
    for f in sorted(FT.glob("*_train.jsonl")):
        for line in open(f):
            if line.strip():
                out.write(line if line.endswith("\n") else line + "\n")
                total += 1
    for f in sorted(GEN.glob("*.jsonl")):
        for line in open(f):
            if line.strip():
                out.write(line if line.endswith("\n") else line + "\n")
                total += 1
                gen_count += 1

print(f"Exported {total} examples ({gen_count} generated) to {out_path.name}")
