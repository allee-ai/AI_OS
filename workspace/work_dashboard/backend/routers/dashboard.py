"""Dashboard router — CRUD for jobs and payments.

Provides both the legacy bulk JSON endpoint (backward compat with Status.html)
and individual CRUD endpoints for the new dashboard.
"""

from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.auth import require_admin
from backend.models import (
    JobCreate, JobUpdate, JobOut,
    PaymentCreate, PaymentOut,
    DashboardData, PropertyCreate, PropertyOut,
)

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_admin)])


# ── Balance summary ──

@router.get("/balance")
def get_balance():
    """Rolling retainer balance: deposits - completed work.

    For hourly jobs, the effective cost is rate * hours.
    """
    EFFECTIVE = "CASE WHEN billing_type = 'hourly' AND hours > 0 THEN cost * hours ELSE cost END"
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments")
    deposits = cur.fetchone()["total"]
    cur.execute(f"SELECT COALESCE(SUM({EFFECTIVE}), 0) as total FROM jobs WHERE status = 'completed'")
    billed = cur.fetchone()["total"]
    cur.execute(f"SELECT COALESCE(SUM({EFFECTIVE}), 0) as total FROM jobs WHERE status = 'scheduled'")
    scheduled = cur.fetchone()["total"]
    cur.execute(f"SELECT COALESCE(SUM({EFFECTIVE}), 0) as total FROM jobs WHERE status = 'pending'")
    pending = cur.fetchone()["total"]
    db.close()
    return {
        "deposits": deposits,
        "completed": billed,
        "scheduled": scheduled,
        "pending": pending,
        "balance": deposits - billed,
    }


# ── Legacy bulk endpoint (same shape as jake_tracker_backup.json) ──


@router.get("/data", response_model=DashboardData)
def get_dashboard_data():
    """Return all jobs + payments in the legacy array-of-arrays format."""
    db = get_db()
    cur = db.cursor()
    result: dict[str, list] = {"completed": [], "scheduled": [], "pending": [], "payments": []}

    for status in ("completed", "scheduled", "pending"):
        cur.execute(
            """SELECT p.address, j.description, j.cost
               FROM jobs j JOIN properties p ON j.property_id = p.id
               WHERE j.status = %s ORDER BY j.id""",
            (status,),
        )
        rows = cur.fetchall()
        result[status] = [[r["address"], r["description"], str(int(r["cost"]))] for r in rows]

    cur.execute("SELECT date, amount, note FROM payments ORDER BY id")
    payments = cur.fetchall()
    result["payments"] = [[r["date"], str(int(r["amount"])), r["note"] or ""] for r in payments]

    db.close()
    return result


@router.post("/data")
def save_dashboard_data(data: DashboardData):
    """Accept bulk save from the dashboard — rebuild jobs + payments from arrays."""
    db = get_db()
    cur = db.cursor()

    # Collect addresses and ensure properties exist
    addresses = set()
    for section in ("completed", "scheduled", "pending"):
        for row in getattr(data, section):
            addresses.add(row[0])

    prop_ids = {}
    for addr in addresses:
        cur.execute(
            "INSERT INTO properties (address, tenant_url_slug) VALUES (%s, %s) ON CONFLICT (address) DO NOTHING",
            (addr, addr.lower().replace(" ", "-")),
        )
        cur.execute("SELECT id FROM properties WHERE address = %s", (addr,))
        prop_ids[addr] = cur.fetchone()["id"]

    # Clear and re-insert all jobs
    cur.execute("DELETE FROM jobs")
    for status in ("completed", "scheduled", "pending"):
        for row in getattr(data, status):
            address, desc = row[0], row[1]
            cost = float(row[2]) if len(row) > 2 else 0
            cur.execute(
                "INSERT INTO jobs (property_id, description, cost, status) VALUES (%s, %s, %s, %s)",
                (prop_ids[address], desc, cost, status),
            )

    # Clear and re-insert payments
    cur.execute("DELETE FROM payments")
    for row in data.payments:
        date_val = row[0] if len(row) > 0 else ""
        amount = float(row[1]) if len(row) > 1 else 0
        note = row[2] if len(row) > 2 else ""
        cur.execute(
            "INSERT INTO payments (date, amount, note) VALUES (%s, %s, %s)",
            (date_val, amount, note),
        )

    db.commit()
    db.close()
    return {"ok": True}


# ── Individual CRUD endpoints ──


# Properties
@router.get("/properties", response_model=list[PropertyOut])
def list_properties():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, address, owner_name, tenant_url_slug, access_notes FROM properties ORDER BY address")
    rows = cur.fetchall()
    db.close()
    return rows


@router.post("/properties", response_model=PropertyOut)
def create_property(p: PropertyCreate):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO properties (address, owner_name, tenant_url_slug, access_notes) VALUES (%s, %s, %s, %s) RETURNING id",
        (p.address, p.owner_name, p.tenant_url_slug, p.access_notes),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    cur.execute("SELECT id, address, owner_name, tenant_url_slug, access_notes FROM properties WHERE id = %s", (new_id,))
    row = cur.fetchone()
    db.close()
    return row


@router.patch("/properties/{prop_id}", response_model=PropertyOut)
def update_property(prop_id: int, p: PropertyCreate):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM properties WHERE id = %s", (prop_id,))
    if not cur.fetchone():
        db.close()
        raise HTTPException(404, "Property not found")
    cur.execute(
        "UPDATE properties SET address = %s, owner_name = %s, tenant_url_slug = %s, access_notes = %s WHERE id = %s",
        (p.address, p.owner_name, p.tenant_url_slug, p.access_notes, prop_id),
    )
    db.commit()
    cur.execute("SELECT id, address, owner_name, tenant_url_slug, access_notes FROM properties WHERE id = %s", (prop_id,))
    row = cur.fetchone()
    db.close()
    return row


@router.delete("/properties/{prop_id}")
def delete_property(prop_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM jobs WHERE property_id = %s LIMIT 1", (prop_id,))
    if cur.fetchone():
        db.close()
        raise HTTPException(400, "Cannot delete property with existing jobs")
    cur.execute("DELETE FROM properties WHERE id = %s", (prop_id,))
    db.commit()
    db.close()
    return {"ok": True}


# Jobs
@router.get("/jobs", response_model=list[JobOut])
def list_jobs(status: str | None = None):
    db = get_db()
    cur = db.cursor()
    query = """SELECT j.id, j.property_id, p.address as property_address, j.work_order_id,
                      j.description, j.cost, j.billing_type, j.hours, j.status
               FROM jobs j JOIN properties p ON j.property_id = p.id"""
    params: list = []
    if status:
        query += " WHERE j.status = %s"
        params.append(status)
    query += " ORDER BY j.id"
    cur.execute(query, params)
    rows = cur.fetchall()
    db.close()
    return rows


@router.post("/jobs", response_model=JobOut)
def create_job(j: JobCreate):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO jobs (property_id, description, cost, billing_type, hours, status, work_order_id) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (j.property_id, j.description, j.cost, j.billing_type, j.hours, j.status, j.work_order_id),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    cur.execute(
        """SELECT j.id, j.property_id, p.address as property_address, j.work_order_id,
                  j.description, j.cost, j.billing_type, j.hours, j.status
           FROM jobs j JOIN properties p ON j.property_id = p.id WHERE j.id = %s""",
        (new_id,),
    )
    row = cur.fetchone()
    db.close()
    return row


@router.patch("/jobs/{job_id}", response_model=JobOut)
def update_job(job_id: int, updates: JobUpdate):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM jobs WHERE id = %s", (job_id,))
    if not cur.fetchone():
        db.close()
        raise HTTPException(404, "Job not found")

    fields = updates.model_dump(exclude_unset=True)
    if fields:
        set_clause = ", ".join(f"{k} = %s" for k in fields)
        cur.execute(f"UPDATE jobs SET {set_clause} WHERE id = %s", (*fields.values(), job_id))
        db.commit()

    cur.execute(
        """SELECT j.id, j.property_id, p.address as property_address, j.work_order_id,
                  j.description, j.cost, j.billing_type, j.hours, j.status
           FROM jobs j JOIN properties p ON j.property_id = p.id WHERE j.id = %s""",
        (job_id,),
    )
    row = cur.fetchone()
    db.close()
    return row


@router.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
    db.commit()
    db.close()
    return {"ok": True}


# Payments
@router.get("/payments", response_model=list[PaymentOut])
def list_payments():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, amount, date, note FROM payments ORDER BY id")
    rows = cur.fetchall()
    db.close()
    return rows


@router.post("/payments", response_model=PaymentOut)
def create_payment(p: PaymentCreate):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO payments (date, amount, note) VALUES (%s, %s, %s) RETURNING id",
        (p.date, p.amount, p.note),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    cur.execute("SELECT id, amount, date, note FROM payments WHERE id = %s", (new_id,))
    row = cur.fetchone()
    db.close()
    return row


@router.delete("/payments/{payment_id}")
def delete_payment(payment_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM payments WHERE id = %s", (payment_id,))
    db.commit()
    db.close()
    return {"ok": True}
