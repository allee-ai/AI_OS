"""Drop the 'paid' column from the jobs table.

SQLite doesn't support ALTER TABLE DROP COLUMN before 3.35,
so we recreate the table.
"""
import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")
db = sqlite3.connect(DB)
db.execute("PRAGMA foreign_keys=OFF")

# Check if paid column exists
cols = [r[1] for r in db.execute("PRAGMA table_info(jobs)").fetchall()]
if "paid" not in cols:
    print("'paid' column already removed — nothing to do.")
    db.close()
    exit()

db.executescript("""
    CREATE TABLE jobs_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL REFERENCES properties(id),
        work_order_id INTEGER REFERENCES work_orders(id),
        description TEXT NOT NULL,
        cost REAL NOT NULL DEFAULT 0,
        status TEXT CHECK(status IN ('pending','scheduled','completed')) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    );

    INSERT INTO jobs_new (id, property_id, work_order_id, description, cost, status, created_at, completed_at)
        SELECT id, property_id, work_order_id, description, cost, status, created_at, completed_at FROM jobs;

    DROP TABLE jobs;
    ALTER TABLE jobs_new RENAME TO jobs;
""")

db.execute("PRAGMA foreign_keys=ON")
db.commit()
db.close()
print("Migration complete — 'paid' column removed from jobs table.")
