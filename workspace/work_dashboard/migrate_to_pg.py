"""Migrate data from SQLite to PostgreSQL."""
import sqlite3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_db, init_db

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "app.db")

# Init Postgres tables
init_db()

# Connect to both
lite = sqlite3.connect(SQLITE_PATH)
lite.row_factory = sqlite3.Row
pg = get_db()
cur = pg.cursor()

# Properties
rows = lite.execute("SELECT address, owner_name, tenant_url_slug, access_notes FROM properties WHERE address != '' AND address != '2802 '").fetchall()
for r in rows:
    cur.execute(
        "INSERT INTO properties (address, owner_name, tenant_url_slug, access_notes) VALUES (%s, %s, %s, %s) ON CONFLICT (address) DO NOTHING",
        (r["address"], r["owner_name"], r["tenant_url_slug"], r["access_notes"]),
    )
print(f"  Properties: {len(rows)}")

# Build address->id map for Postgres
cur.execute("SELECT id, address FROM properties")
pg_props = {r["address"]: r["id"] for r in cur.fetchall()}

# Build old SQLite id->address map
lite_props = {r["id"]: r["address"] for r in lite.execute("SELECT id, address FROM properties").fetchall()}

# Jobs
jobs = lite.execute("SELECT property_id, work_order_id, description, cost, billing_type, hours, status FROM jobs").fetchall()
for j in jobs:
    addr = lite_props.get(j["property_id"])
    if not addr or addr not in pg_props:
        continue
    cur.execute(
        "INSERT INTO jobs (property_id, work_order_id, description, cost, billing_type, hours, status) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (pg_props[addr], j["work_order_id"], j["description"], j["cost"], j["billing_type"] or "flat", j["hours"] or 0, j["status"]),
    )
print(f"  Jobs: {len(jobs)}")

# Payments
payments = lite.execute("SELECT amount, date, note FROM payments").fetchall()
for p in payments:
    cur.execute(
        "INSERT INTO payments (amount, date, note) VALUES (%s, %s, %s)",
        (p["amount"], p["date"], p["note"]),
    )
print(f"  Payments: {len(payments)}")

# Work orders
wos = lite.execute("SELECT property_id, description, urgency, status, submitted_at, resolved_at FROM work_orders").fetchall()
for w in wos:
    addr = lite_props.get(w["property_id"])
    if not addr or addr not in pg_props:
        continue
    cur.execute(
        "INSERT INTO work_orders (property_id, description, urgency, status, submitted_at, resolved_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (pg_props[addr], w["description"], w["urgency"], w["status"], w["submitted_at"], w["resolved_at"]),
    )
print(f"  Work orders: {len(wos)}")

pg.commit()
pg.close()
lite.close()
print("Migration complete.")
