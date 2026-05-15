"""Seed initial users + clean out legacy ones. Idempotent — safe to run repeatedly."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_db, init_db
from backend.auth import hash_password

init_db()
db = get_db()
cur = db.cursor()

# Remove legacy / decommissioned users (jake's owner account, etc.)
cur.execute("DELETE FROM users WHERE username = ANY(%s)", (['jake'],))
removed = cur.rowcount
if removed:
    print(f"  Removed {removed} legacy user(s)")

# Migrate any remaining 'owner' role rows (no longer used) up to 'admin'.
cur.execute("UPDATE users SET role = 'admin' WHERE role = 'owner'")
if cur.rowcount:
    print(f"  Migrated {cur.rowcount} owner→admin")

users = [
    ("cade", "peak2026!", "admin"),
    ("sales", "vanguard2026", "sales"),
]

for username, password, role in users:
    cur.execute("SELECT id FROM users WHERE username = %s", (username,))
    if cur.fetchone():
        print(f"  {username} already exists, skipping")
        continue
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
        (username, hash_password(password), role),
    )
    print(f"  Created {username} ({role})")

db.commit()
db.close()
print("Done.")
