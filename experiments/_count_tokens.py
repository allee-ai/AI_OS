#!/usr/bin/env python3
"""Count total available tokens across all data sources."""
import sqlite3, os

conn = sqlite3.connect("data/db/state.db")
turns = conn.execute("SELECT COALESCE(SUM(LENGTH(user_message)),0) + COALESCE(SUM(LENGTH(assistant_message)),0) FROM convo_turns").fetchone()[0] or 0
thoughts = conn.execute("SELECT COALESCE(SUM(LENGTH(thought)),0) FROM thought_log").fetchone()[0] or 0
events = conn.execute("SELECT COALESCE(SUM(LENGTH(data)),0) FROM unified_events").fetchone()[0] or 0
temps = conn.execute("SELECT COALESCE(SUM(LENGTH(text)),0) FROM temp_facts").fetchone()[0] or 0
db_total = turns + thoughts + events + temps
print(f"convo_turns:     {turns:>10,} chars  (~{turns//4:,} tokens)")
print(f"thought_log:     {thoughts:>10,} chars  (~{thoughts//4:,} tokens)")
print(f"unified_events:  {events:>10,} chars  (~{events//4:,} tokens)")
print(f"temp_facts:      {temps:>10,} chars  (~{temps//4:,} tokens)")
print(f"DB total:        {db_total:>10,} chars  (~{db_total//4:,} tokens)")
conn.close()

code_chars = 0
for root, dirs, files in os.walk("."):
    skip = any(s in root for s in [".venv", "__pycache__", "node_modules", ".git/"])
    if skip:
        continue
    for f in files:
        if f.endswith((".py", ".md", ".txt", ".jsonl", ".yaml", ".yml", ".json", ".ts", ".tsx", ".css")):
            try:
                code_chars += os.path.getsize(os.path.join(root, f))
            except:
                pass

print(f"code+docs+data:  {code_chars:>10,} chars  (~{code_chars//4:,} tokens)")
grand = db_total + code_chars
print(f"GRAND TOTAL:     {grand:>10,} chars  (~{grand//4:,} tokens)")
