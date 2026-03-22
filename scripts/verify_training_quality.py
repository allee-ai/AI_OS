#!/usr/bin/env python3
"""Verify training data quality after generator rewrite."""
import json

OLD_MARKERS = ["Based on what I know:", "Based on your philosophy:", "The {", "When {"]
NEW_MARKERS = [
    "identity.", "philosophy.", "form.", "reflex.", "linking_core.", "log.",
    "my identity thread", "my form thread", "my philosophy thread",
    "my reflex thread", "my linking_core", "my log thread",
    "dot-notation", "Hebbian", "introspect", "orchestrator",
    "context_level", "token budget", "spread activation",
]

old_style = 0
new_style = 0
arch_knowledge = 0
real_state = 0
fake_state = 0
thread_reference = 0

for line in open("finetune/aios_combined.jsonl"):
    d = json.loads(line)
    msgs = d["messages"]
    sys_msg = msgs[0]["content"] if msgs[0]["role"] == "system" else ""
    asst_msg = msgs[-1]["content"] if msgs[-1]["role"] == "assistant" else ""

    # Check system prompt format
    if "[self]" in sys_msg or "context_level:" in sys_msg or "fact_count:" in sys_msg:
        real_state += 1
    elif "== STATE ==" in sys_msg and "Module:" in sys_msg:
        fake_state += 1
    elif "== STATE ==" in sys_msg:
        real_state += 1  # Could be either but likely real

    # Check assistant response style
    is_old = any(m in asst_msg for m in ["Based on what I know:", "Based on your philosophy:"])
    is_new = any(m in asst_msg.lower() for m in [
        "my identity thread", "my form thread", "my philosophy thread",
        "my reflex thread", "my linking_core", "my log thread",
        "identity.", "philosophy.", "form.tools", "reflex.triggers",
    ])

    if is_old:
        old_style += 1
    if is_new:
        new_style += 1

    # Architectural knowledge (long-term memory in weights)
    if any(m in asst_msg.lower() for m in [
        "hebbian", "introspect", "orchestrator", "context_level",
        "token budget", "spread activation", "potentiation",
        "my architecture", "my threads", "my concept graph",
    ]):
        arch_knowledge += 1

    # Thread references
    if any(t in asst_msg for t in [
        "identity thread", "form thread", "philosophy thread",
        "reflex thread", "linking_core", "log thread",
        "identity.", "philosophy.", "form.", "reflex.",
    ]):
        thread_reference += 1

total = sum(1 for _ in open("finetune/aios_combined.jsonl"))

print("=== Training Data Quality Report ===\n")
print(f"  Total examples:           {total}")
print(f"  Real STATE format:        {real_state} ({real_state*100//total}%)")
print(f"  Fake STATE format:        {fake_state} ({fake_state*100//total}%)")
print(f"  Old-style responses:      {old_style} ({old_style*100//total}%)")
print(f"  New-style responses:      {new_style} ({new_style*100//total}%)")
print(f"  Architectural knowledge:  {arch_knowledge} ({arch_knowledge*100//total}%)")
print(f"  Thread references:        {thread_reference} ({thread_reference*100//total}%)")

# Check for the key behavioral pattern: assistant uses dot-notation paths
dot_path_count = 0
for line in open("finetune/aios_combined.jsonl"):
    d = json.loads(line)
    asst = d["messages"][-1]["content"] if d["messages"][-1]["role"] == "assistant" else ""
    # Look for patterns like identity.nola.name, form.tools.web_search, etc.
    import re
    if re.search(r'\b(identity|form|philosophy|reflex|linking_core|log)\.\w+', asst):
        dot_path_count += 1

print(f"  Dot-path in response:     {dot_path_count} ({dot_path_count*100//total}%)")
