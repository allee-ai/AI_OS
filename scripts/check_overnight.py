"""Quick check of overnight loop results."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "data", "db", "state.db")
db_size = os.path.getsize(db_path) / (1024 * 1024)
print(f"Database size: {db_size:.1f} MB")

conn = sqlite3.connect(db_path)
c = conn.cursor()

# Temp facts stats
c.execute("SELECT status, COUNT(*) FROM temp_facts GROUP BY status")
print("\n=== TEMP FACTS BY STATUS ===")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]}")
c.execute("SELECT COUNT(*) FROM temp_facts")
print(f"  TOTAL: {c.fetchone()[0]}")

# Profile facts
c.execute("SELECT COUNT(*) FROM profile_facts")
print(f"\n=== PROFILE FACTS: {c.fetchone()[0]} ===")

# Concept graph
try:
    c.execute("SELECT COUNT(*) FROM concept_nodes")
    nodes = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM concept_links")
    links = c.fetchone()[0]
    c.execute("SELECT AVG(strength) FROM concept_links")
    avg_str = c.fetchone()[0] or 0
    print(f"\n=== CONCEPT GRAPH: {nodes} nodes, {links} links, avg_strength={avg_str:.2f} ===")
except Exception as e:
    print(f"Concept graph: {e}")

# Conversations
try:
    c.execute("SELECT COUNT(*) FROM conversations")
    convos = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM conversation_turns")
    turns = c.fetchone()[0]
    print(f"\n=== CONVERSATIONS: {convos} convos, {turns} turns ===")
except:
    # Try chat schema
    for tbl in ["chat_conversations", "chat_sessions", "convo_turns"]:
        try:
            c.execute(f"SELECT COUNT(*) FROM {tbl}")
            print(f"  {tbl}: {c.fetchone()[0]}")
        except:
            pass

# Thoughts
try:
    c.execute("SELECT COUNT(*) FROM thoughts")
    print(f"\n=== THOUGHTS: {c.fetchone()[0]} ===")
except:
    pass

# List all tables
print("\n=== ALL TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for row in c.fetchall():
    c2 = conn.cursor()
    try:
        c2.execute(f"SELECT COUNT(*) FROM [{row[0]}]")
        cnt = c2.fetchone()[0]
        if cnt > 0:
            print(f"  {row[0]}: {cnt} rows")
    except:
        print(f"  {row[0]}: (error)")

# Recent temp facts sample
print("\n=== RECENT FACTS (last 5) ===")
c.execute("SELECT text, status, confidence_score FROM temp_facts ORDER BY created_at DESC LIMIT 5")
for row in c.fetchall():
    text = row[0][:80] if row[0] else "?"
    print(f"  [{row[1]}] (conf={row[2]}) {text}")

conn.close()
