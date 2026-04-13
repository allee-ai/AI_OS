"""Quick survey of data sizes for model architecture planning."""
import sqlite3, os, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db = os.path.join(ROOT, "data/db/state.db")

if not os.path.exists(db):
    print("No state.db found")
    exit()

conn = sqlite3.connect(db)

# Concept graph
try:
    concepts = conn.execute(
        "SELECT COUNT(DISTINCT c) FROM ("
        "SELECT concept_a AS c FROM concept_links UNION "
        "SELECT concept_b AS c FROM concept_links)"
    ).fetchone()[0]
    edges = conn.execute("SELECT COUNT(*) FROM concept_links").fetchone()[0]
    avg = conn.execute("SELECT AVG(strength) FROM concept_links").fetchone()[0]
    long_n = conn.execute(
        "SELECT COUNT(*) FROM concept_links WHERE potentiation='LONG'"
    ).fetchone()[0]
    print(f"Concept graph: {concepts} concepts, {edges} edges, avg={avg:.3f}, LONG={long_n}")
except Exception as e:
    print(f"concept_links error: {e}")

for table in ["identity_facts", "philosophy_facts", "temp_memory",
              "key_sequences", "unified_events"]:
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n}")
    except:
        pass

conn.close()

# Conversations
cdir = os.path.join(ROOT, "Feeds/conversations")
convos = len([f for f in os.listdir(cdir) if f.endswith(".json")]) if os.path.isdir(cdir) else 0
print(f"Conversations: {convos} files")

# Training JSONL
total = 0
for f in glob.glob(os.path.join(ROOT, "finetune/*_train.jsonl")):
    total += sum(1 for _ in open(f))
print(f"Training JSONL lines: {total}")

# Codebase
py_count = 0
py_bytes = 0
for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in {".venv", "node_modules", "__pycache__", ".git", "runs"}]
    for f in files:
        if f.endswith(".py"):
            py_count += 1
            py_bytes += os.path.getsize(os.path.join(root, f))

print(f"Python files: {py_count}, {py_bytes:,} bytes ({py_bytes//1024}KB)")
print(f"Estimated codebase tokens: ~{py_bytes // 4:,}")
print(f"Estimated model capacity needed (at 10 tokens/param): ~{py_bytes // 40:,} params")
