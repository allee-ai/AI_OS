"""Check if dot notation already encodes thread-region topology."""
import sqlite3
from collections import Counter

conn = sqlite3.connect("data/db/state.db")
cur = conn.cursor()

cur.execute("SELECT DISTINCT c FROM (SELECT concept_a AS c FROM concept_links UNION SELECT concept_b AS c FROM concept_links)")
all_concepts = [r[0] for r in cur.fetchall()]

dotted = [c for c in all_concepts if "." in c]
flat = [c for c in all_concepts if "." not in c]

print(f"Total concepts: {len(all_concepts)}")
print(f"Dotted (has hierarchy): {len(dotted)}")
print(f"Flat (single word): {len(flat)}")

roots = Counter()
for c in dotted:
    roots[c.split(".")[0]] += 1
print(f"\nDotted root prefixes (top 20):")
for r, cnt in roots.most_common(20):
    print(f"  {r}: {cnt}")

print(f"\nSample dotted concepts (first 30 alpha):")
for c in sorted(dotted)[:30]:
    print(f"  {c}")

print(f"\nSample flat concepts (first 30 alpha):")
for c in sorted(flat)[:30]:
    print(f"  {c}")

# Check: do dotted concepts link TO thread roots?
thread_roots = ["identity", "log", "form", "philosophy", "reflex"]
print(f"\nThread root nodes in graph?")
for root in thread_roots:
    cur.execute("SELECT COUNT(*) FROM concept_links WHERE concept_a = ? OR concept_b = ?", (root, root))
    cnt = cur.fetchone()[0]
    print(f"  {root}: {cnt} links")

conn.close()
