import ast, sys

files = [
    "agent/subconscious/loops/base.py",
    "agent/subconscious/loops/manager.py",
    "agent/subconscious/loops/memory.py",
    "agent/subconscious/loops/consolidation.py",
    "agent/subconscious/loops/thought.py",
    "agent/subconscious/loops/goals.py",
    "agent/subconscious/loops/task_planner.py",
    "agent/subconscious/loops/health.py",
    "agent/subconscious/loops/sync.py",
    "agent/subconscious/loops/convo_concepts.py",
    "agent/subconscious/loops/demo_audit.py",
    "agent/subconscious/loops/self_improve.py",
    "agent/subconscious/loops/workspace_qa.py",
    "agent/subconscious/loops/training_gen.py",
    "agent/subconscious/__init__.py",
    "agent/subconscious/api.py",
    "scripts/cleanup_facts.py",
]

errors = 0
for f in files:
    try:
        with open(f) as fh:
            ast.parse(fh.read())
        print(f"OK {f}")
    except SyntaxError as e:
        errors += 1
        print(f"FAIL {f}: {e}")

print(f"\n{len(files) - errors}/{len(files)} passed")
sys.exit(1 if errors else 0)
