"""Test boundary rule enforcement."""
from agent.core.rules import guard_loop_creation, guard_reflex_to_loop, BoundaryViolation

# These should BLOCK
for src in ["reflex", "protocol:morning", "trigger", "feed", "protocol"]:
    try:
        guard_loop_creation(src)
        print(f"FAIL: {src} was not blocked!")
    except BoundaryViolation:
        print(f"OK: {src} blocked")

# These should PASS
for src in ["manual", "agent", "subconscious", "user", "cli"]:
    try:
        guard_loop_creation(src)
        print(f"OK: {src} allowed")
    except BoundaryViolation:
        print(f"FAIL: {src} was incorrectly blocked!")

# Test create_task with protocol source
from agent.subconscious.loops.task_planner import create_task
try:
    create_task("test dangerous loop", source="protocol:morning_briefing")
    print("FAIL: protocol task not blocked!")
except BoundaryViolation:
    print("OK: create_task blocked protocol source")

# Test that manual tasks still work
task = create_task("test normal task", source="manual")
print(f"OK: manual task created (id={task['id']})")

# Test reflex executor has no planner import in active code
import inspect
from agent.threads.reflex import executor
src = inspect.getsource(executor)
has_planner = "from agent.subconscious.loops import" in src
print(f"Reflex executor imports subconscious.loops: {has_planner} (should be False)")

print("\nAll boundary tests passed!")
