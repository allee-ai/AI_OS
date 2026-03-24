#!/usr/bin/env python3
"""Live Kimi K2 workspace sorting test.

Run: .venv/bin/python tests/live_kimi_test.py
"""
import os
import sys

# Force schema tool mode and Kimi K2
os.environ["AIOS_TOOL_MODE"] = "schema"
os.environ["AIOS_MODEL_NAME"] = "kimi-k2:1t-cloud"
os.environ["AIOS_MODEL_PROVIDER"] = "ollama"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import Agent
from agent.threads.form.tools.executables.workspace_read import run as ws_read

# Show workspace state before
print("=== BEFORE: /unsorted/ ===")
print(ws_read("list_directory", {"path": "/unsorted"}))
print()

# Create agent and run
agent = Agent()

events = []
def on_tool(ev):
    events.append(ev)
    t = ev.get("type", "?")
    tool = ev.get("tool", "?")
    action = ev.get("action", "?")
    r = ev.get("round", "?")
    print(f"  [TOOL r{r}] {t}: {tool}.{action}")

prompt = (
    "I need you to organize files in my workspace. Here is what I need:\n"
    "1. First, list the contents of /unsorted/ to see what files are there\n"
    "2. Create organized directories: /code, /config, /docs\n"
    "3. Move each file to the right folder:\n"
    "   - .py files go to /code\n"
    "   - .yaml files go to /config\n"
    "   - .txt and .md files go to /docs\n"
    "   - .css files go to /code\n\n"
    "Use the workspace_read and workspace_write tools. Start by listing /unsorted/."
)

print("=== Calling Kimi K2 with workspace tools ===")
print()
response = agent.generate(prompt, on_tool_event=on_tool)
print()
print("=== RESPONSE ===")
print(response[:3000])
print()
print(f"=== Tool events: {len(events)} ===")
for e in events:
    print(f"  {e}")

# Show workspace state after
print()
print("=== AFTER: checking results ===")
for d in ["/unsorted", "/code", "/config", "/docs"]:
    try:
        out = ws_read("list_directory", {"path": d})
        print(out)
    except Exception as ex:
        print(f"{d}: {ex}")
    print()

# Summary
print("=== SUMMARY ===")
if len(events) > 0:
    tool_actions = [f"{e.get('tool')}.{e.get('action')}" for e in events if e.get("type") == "tool_executing"]
    print(f"Tools called: {len(tool_actions)}")
    for ta in tool_actions:
        print(f"  - {ta}")
else:
    print("No tool calls were made (LLM may not have used schema tools)")
