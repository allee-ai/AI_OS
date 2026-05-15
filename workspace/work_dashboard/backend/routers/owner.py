"""Owner router — Jake's property overview and work order approval."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.database import get_db
from backend.auth import require_owner_or_admin, require_admin

router = APIRouter(tags=["owner"])


@router.get("/balance")
def owner_balance():
    """Rolling retainer balance for the owner view."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments")
    deposits = cur.fetchone()["total"]
    cur.execute("SELECT COALESCE(SUM(cost), 0) as total FROM jobs WHERE status = 'completed'")
    billed = cur.fetchone()["total"]
    cur.execute("SELECT COALESCE(SUM(cost), 0) as total FROM jobs WHERE status = 'scheduled'")
    scheduled = cur.fetchone()["total"]
    cur.execute("SELECT COALESCE(SUM(cost), 0) as total FROM jobs WHERE status = 'pending'")
    pending = cur.fetchone()["total"]
    db.close()
    return {"deposits": deposits, "completed": billed, "scheduled": scheduled, "pending": pending, "balance": deposits - billed}


@router.get("/jobs")
def owner_jobs():
    """All jobs visible to the owner."""
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """SELECT j.id, j.property_id, p.address as property_address, j.work_order_id,
                  j.description, j.cost, j.billing_type, j.hours, j.status
           FROM jobs j JOIN properties p ON j.property_id = p.id ORDER BY j.id"""
    )
    rows = cur.fetchall()
    db.close()
    return rows


@router.get("/properties")
def owner_properties():
    """All properties with job summary stats."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, address, access_notes FROM properties ORDER BY address")
    props = cur.fetchall()
    result = []
    for p in props:
        cur.execute(
            "SELECT status, SUM(cost) as total_cost, COUNT(*) as cnt FROM jobs WHERE property_id = %s GROUP BY status",
            (p["id"],),
        )
        jobs = cur.fetchall()
        summary = {r["status"]: {"count": r["cnt"], "cost": r["total_cost"]} for r in jobs}
        result.append({"id": p["id"], "address": p["address"], "access_notes": p["access_notes"], "jobs": summary})
    db.close()
    return result


@router.get("/work-orders")
def owner_work_orders():
    """All work orders for Jake to review."""
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """SELECT wo.id, wo.description, wo.urgency, wo.status, wo.submitted_at,
                  p.address as property_address, p.id as property_id
           FROM work_orders wo JOIN properties p ON wo.property_id = p.id
           ORDER BY wo.submitted_at DESC"""
    )
    rows = cur.fetchall()
    db.close()
    return rows


@router.post("/work-orders/{wo_id}/approve")
def approve_work_order(wo_id: int, body: dict | None = None):
    """Approve a work order — creates a scheduled job with a price."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM work_orders WHERE id = %s", (wo_id,))
    wo = cur.fetchone()
    if not wo:
        db.close()
        raise HTTPException(404, "Work order not found")
    if wo["status"] != "submitted":
        db.close()
        raise HTTPException(400, f"Work order already {wo['status']}")

    cost = float(body.get("cost", 0)) if body else 0
    cur.execute("UPDATE work_orders SET status = 'approved', resolved_at = CURRENT_TIMESTAMP WHERE id = %s", (wo_id,))
    cur.execute(
        "INSERT INTO jobs (property_id, work_order_id, description, cost, status) VALUES (%s, %s, %s, %s, 'scheduled')",
        (wo["property_id"], wo_id, wo["description"], cost),
    )
    db.commit()
    db.close()
    return {"ok": True, "status": "approved"}


@router.post("/work-orders/{wo_id}/deny")
def deny_work_order(wo_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM work_orders WHERE id = %s", (wo_id,))
    wo = cur.fetchone()
    if not wo:
        db.close()
        raise HTTPException(404, "Work order not found")
    if wo["status"] != "submitted":
        db.close()
        raise HTTPException(400, f"Work order already {wo['status']}")

    cur.execute("UPDATE work_orders SET status = 'denied', resolved_at = CURRENT_TIMESTAMP WHERE id = %s", (wo_id,))
    db.commit()
    db.close()
    return {"ok": True, "status": "denied"}
