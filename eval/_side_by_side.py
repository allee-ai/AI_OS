#!/usr/bin/env python3
"""
Side-by-side comparison of BARE vs STATIC vs STATE responses.
Reads existing results JSON — no LLM calls needed.
Outputs a clean markdown file for human judging.
"""
import json

data = json.load(open("eval/baseline_comparison_results.json"))

out = []
out.append("# Baseline Comparison — Side by Side")
out.append(f"**Model:** {data['model']}  |  **Run:** {data['timestamp']}\n")

# ── Identity Battery ──
out.append("---\n## Battery 1: Identity Persistence (20 prompts)\n")
out.append("Score each response: ✅ maintains identity | ❌ loses identity | ⚠️ ambiguous\n")

bare_id = data["identity"]["bare"]["turns"]
static_id = data["identity"]["static"]["turns"]
state_id = data["identity"]["state"]["turns"]

for i in range(len(bare_id)):
    b, s, st = bare_id[i], static_id[i], state_id[i]
    out.append(f"### Prompt {i+1} [{b['category']}]")
    out.append(f"> {b['prompt']}\n")
    
    out.append(f"**BARE** ({b['elapsed']}s)")
    out.append(f"```\n{b['response'].strip()}\n```\n")
    
    out.append(f"**STATIC** ({s['elapsed']}s)")
    out.append(f"```\n{s['response'].strip()}\n```\n")
    
    out.append(f"**STATE** ({st['elapsed']}s)")
    out.append(f"```\n{st['response'].strip()}\n```\n")
    
    out.append("| | BARE | STATIC | STATE |")
    out.append("|---|---|---|---|")
    out.append("| Score | | | |\n")
    out.append("---\n")

# ── Memory Battery ──
out.append("## Battery 2: Memory Switching (10 prompts)\n")
out.append("Score each response: ✅ correct recall | ❌ wrong/missing | ⚠️ partial\n")

bare_mem = data["memory"]["bare"]["turns"]
static_mem = data["memory"]["static_with_facts"]["turns"]
state_mem = data["memory"]["state"]["turns"]

for i in range(len(bare_mem)):
    b, s, st = bare_mem[i], static_mem[i], state_mem[i]
    out.append(f"### Prompt {i+1} [{b['category']}]")
    out.append(f"> {b['prompt']}\n")
    
    out.append(f"**BARE** ({b['elapsed']}s)")
    out.append(f"```\n{b['response'].strip()}\n```\n")
    
    out.append(f"**STATIC+FACTS** ({s['elapsed']}s)")
    out.append(f"```\n{s['response'].strip()}\n```\n")
    
    out.append(f"**STATE** ({st['elapsed']}s)")
    out.append(f"```\n{st['response'].strip()}\n```\n")
    
    out.append("| | BARE | STATIC | STATE |")
    out.append("|---|---|---|---|")
    out.append("| Score | | | |\n")
    out.append("---\n")

# ── Summary table ──
out.append("## Final Scores\n")
out.append("| Prompt | BARE | STATIC | STATE | Notes |")
out.append("|--------|------|--------|-------|-------|")
for i in range(20):
    out.append(f"| ID-{i+1:02d} | | | | |")
for i in range(10):
    out.append(f"| MEM-{i+1:02d} | | | | |")
out.append("")

path = "eval/baseline_side_by_side.md"
with open(path, "w") as f:
    f.write("\n".join(out))
print(f"Written to {path} ({len(out)} lines)")
