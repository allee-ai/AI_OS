"""Invoices table schema. Snapshot of dashboard at point-in-time."""
from backend.database import get_db


def init_invoices_table() -> None:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            label TEXT,
            snapshot JSONB NOT NULL,
            html_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices(created_at DESC);
    """)
    conn.commit()
    conn.close()
