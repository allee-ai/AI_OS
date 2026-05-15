"""PostgreSQL database initialization and connection helpers."""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "dbname=jake_app"  # local default — no password needed on Mac
)


def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn.autocommit = False
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS properties (
            id SERIAL PRIMARY KEY,
            address TEXT NOT NULL UNIQUE,
            owner_name TEXT DEFAULT 'Jake',
            tenant_url_slug TEXT UNIQUE,
            access_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS work_orders (
            id SERIAL PRIMARY KEY,
            property_id INTEGER NOT NULL REFERENCES properties(id),
            description TEXT NOT NULL,
            urgency TEXT CHECK(urgency IN ('low','medium','high')) DEFAULT 'medium',
            photo_path TEXT,
            status TEXT CHECK(status IN ('submitted','approved','denied')) DEFAULT 'submitted',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id SERIAL PRIMARY KEY,
            property_id INTEGER NOT NULL REFERENCES properties(id),
            work_order_id INTEGER REFERENCES work_orders(id),
            description TEXT NOT NULL,
            cost DOUBLE PRECISION NOT NULL DEFAULT 0,
            billing_type TEXT CHECK(billing_type IN ('flat','hourly')) DEFAULT 'flat',
            hours DOUBLE PRECISION DEFAULT 0,
            status TEXT CHECK(status IN ('pending','pushed','scheduled','completed')) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payments (
            id SERIAL PRIMARY KEY,
            amount DOUBLE PRECISION NOT NULL,
            date TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Sales pipeline ----------------------------------------------------
        -- leads: people the salesperson is contacting (cold list + warming)
        -- call_log: every call attempt + outcome
        -- promotion: when a lead status='won', a row is added to properties
        CREATE TABLE IF NOT EXISTS leads (
            id SERIAL PRIMARY KEY,
            company_name TEXT,
            contact_name TEXT NOT NULL,
            contact_role TEXT,           -- owner / pm / investor / agent
            phone TEXT,
            email TEXT,
            address TEXT,
            portfolio_size INTEGER,      -- # units they manage
            neighborhoods TEXT,
            source TEXT,                 -- google / referral / list / drive-by
            status TEXT NOT NULL DEFAULT 'cold' CHECK (status IN
                ('cold','contacted','packet_sent','walkthrough_scheduled','quoted','won','dead')),
            next_action TEXT,
            next_action_date DATE,
            notes TEXT,
            promoted_property_id INTEGER REFERENCES properties(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS call_log (
            id SERIAL PRIMARY KEY,
            lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            outcome TEXT NOT NULL CHECK (outcome IN
                ('no_answer','voicemail','gatekeeper','brushoff','conversation',
                 'packet_sent','walkthrough_booked','quoted','won','dead')),
            objection TEXT,
            best_phrase TEXT,
            notes TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_next_action_date ON leads(next_action_date);
        CREATE INDEX IF NOT EXISTS idx_call_log_lead ON call_log(lead_id);
        CREATE INDEX IF NOT EXISTS idx_call_log_called_at ON call_log(called_at);
    """)

    # Migration: drop legacy users.role CHECK constraint (admin/owner only) so 'sales' is allowed.
    cur.execute("""
        DO $$
        DECLARE c text;
        BEGIN
            FOR c IN SELECT conname FROM pg_constraint
                     WHERE conrelid = 'users'::regclass AND contype = 'c'
            LOOP
                EXECUTE 'ALTER TABLE users DROP CONSTRAINT ' || quote_ident(c);
            END LOOP;
        END$$;
    """)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized")
