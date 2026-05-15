"""One-time migration: import jake_tracker_backup.json into SQLite."""

import json
import os
import sys

# Allow running as `python -m backend.migrate` from jake-app/ or `python backend/migrate.py`
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from backend.database import init_db, get_db

BACKUP_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "jake_tracker_backup.json"
)

# Property access notes from Jake_Notes.md
ACCESS_NOTES = {
    "2332 Chickasaw": "Back door code 2736",
    "3016 Euclid": "Water gets in basement bedroom utility closets",
    "2736 Coy": "Berms needed whole side of building",
    "2421 Fairview": "Berms on left side if facing building",
}


def slugify(address: str) -> str:
    return address.lower().replace(" ", "-")


def migrate():
    if not os.path.exists(BACKUP_FILE):
        print(f"Backup file not found: {BACKUP_FILE}")
        sys.exit(1)

    with open(BACKUP_FILE) as f:
        data = json.load(f)

    init_db()
    db = get_db()

    # Collect unique property addresses
    addresses = set()
    for section in ("completed", "scheduled", "pending"):
        for row in data.get(section, []):
            addresses.add(row[0])

    # Insert properties
    prop_ids = {}
    for addr in sorted(addresses):
        db.execute(
            "INSERT OR IGNORE INTO properties (address, tenant_url_slug, access_notes) VALUES (?, ?, ?)",
            (addr, slugify(addr), ACCESS_NOTES.get(addr)),
        )
        row = db.execute("SELECT id FROM properties WHERE address = ?", (addr,)).fetchone()
        prop_ids[addr] = row["id"]

    # Insert jobs
    status_map = {"completed": "completed", "scheduled": "scheduled", "pending": "pending"}
    job_count = 0
    for section, status in status_map.items():
        for row in data.get(section, []):
            address, description, cost, paid = row[0], row[1], float(row[2]), float(row[3])
            db.execute(
                "INSERT INTO jobs (property_id, description, cost, paid, status) VALUES (?, ?, ?, ?, ?)",
                (prop_ids[address], description, cost, paid, status),
            )
            job_count += 1

    # Insert payments
    pay_count = 0
    for row in data.get("payments", []):
        date, amount, note = row[0], float(row[1]), row[2] if len(row) > 2 else ""
        db.execute(
            "INSERT INTO payments (date, amount, note) VALUES (?, ?, ?)",
            (date, amount, note),
        )
        pay_count += 1

    db.commit()

    # Summary
    prop_count = db.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
    print(f"Migration complete:")
    print(f"  {prop_count} properties")
    print(f"  {job_count} jobs")
    print(f"  {pay_count} payments")

    db.close()


if __name__ == "__main__":
    migrate()
