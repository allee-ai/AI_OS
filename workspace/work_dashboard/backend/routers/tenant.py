"""Tenant router — public work order submission."""

from fastapi import APIRouter, HTTPException
from backend.database import get_db
from backend.models import WorkOrderCreate

router = APIRouter(tags=["tenant"])


@router.get("/properties")
def list_tenant_properties():
    """Public list of properties for the tenant dropdown."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, address FROM properties ORDER BY address")
    rows = cur.fetchall()
    db.close()
    return rows


@router.post("/work-order")
def submit_work_order(wo: WorkOrderCreate):
    """Tenant submits a new work order."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM properties WHERE id = %s", (wo.property_id,))
    if not cur.fetchone():
        db.close()
        raise HTTPException(404, "Property not found")

    cur.execute(
        "INSERT INTO work_orders (property_id, description, urgency) VALUES (%s, %s, %s) RETURNING id",
        (wo.property_id, wo.description, wo.urgency),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    cur.execute(
        "SELECT id, description, urgency, status, submitted_at FROM work_orders WHERE id = %s",
        (new_id,),
    )
    row = cur.fetchone()
    db.close()
    return row
