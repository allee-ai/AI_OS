"""Sales router — lead tracking + call log + promote-to-client.

Locked to admin + sales roles. iPad logs in once and the bearer token rides
in the Authorization header.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

from backend.database import get_db
from backend.auth import require_sales_or_admin


router = APIRouter(tags=["sales"], dependencies=[Depends(require_sales_or_admin)])


# ── Models ────────────────────────────────────────────────────────────────

class LeadCreate(BaseModel):
    contact_name: str
    company_name: Optional[str] = None
    contact_role: Optional[str] = None    # owner / pm / investor / agent
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    portfolio_size: Optional[int] = None
    neighborhoods: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[date] = None


class LeadUpdate(BaseModel):
    contact_name: Optional[str] = None
    company_name: Optional[str] = None
    contact_role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    portfolio_size: Optional[int] = None
    neighborhoods: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[date] = None


class CallLogCreate(BaseModel):
    outcome: str                          # see schema CHECK constraint
    objection: Optional[str] = None
    best_phrase: Optional[str] = None
    notes: Optional[str] = None


# Status auto-advance map: which call outcomes bump the lead's status forward.
# Salesperson can still manually override via PATCH.
OUTCOME_TO_STATUS = {
    "no_answer": None,                    # don't change status
    "voicemail": "contacted",
    "gatekeeper": "contacted",
    "brushoff": "contacted",
    "conversation": "contacted",
    "packet_sent": "packet_sent",
    "walkthrough_booked": "walkthrough_scheduled",
    "quoted": "quoted",
    "won": "won",
    "dead": "dead",
}


# ── Leads ─────────────────────────────────────────────────────────────────

@router.get("/leads")
def list_leads(status: Optional[str] = None):
    """List leads, optionally filtered by status. Sorted by next-action urgency."""
    db = get_db()
    cur = db.cursor()
    if status:
        cur.execute(
            """SELECT l.*,
                      (SELECT COUNT(*) FROM call_log c WHERE c.lead_id = l.id) AS call_count,
                      (SELECT MAX(called_at) FROM call_log c WHERE c.lead_id = l.id) AS last_called_at
               FROM leads l
               WHERE status = %s
               ORDER BY COALESCE(next_action_date, DATE '9999-12-31') ASC, l.id DESC""",
            (status,),
        )
    else:
        cur.execute(
            """SELECT l.*,
                      (SELECT COUNT(*) FROM call_log c WHERE c.lead_id = l.id) AS call_count,
                      (SELECT MAX(called_at) FROM call_log c WHERE c.lead_id = l.id) AS last_called_at
               FROM leads l
               ORDER BY
                 CASE status
                   WHEN 'walkthrough_scheduled' THEN 1
                   WHEN 'quoted' THEN 2
                   WHEN 'packet_sent' THEN 3
                   WHEN 'contacted' THEN 4
                   WHEN 'cold' THEN 5
                   WHEN 'won' THEN 6
                   WHEN 'dead' THEN 7
                 END,
                 COALESCE(next_action_date, DATE '9999-12-31') ASC,
                 l.id DESC"""
        )
    rows = cur.fetchall()
    db.close()
    return rows


@router.post("/leads")
def create_lead(lead: LeadCreate):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        """INSERT INTO leads (contact_name, company_name, contact_role, phone, email,
                              address, portfolio_size, neighborhoods, source, notes,
                              next_action, next_action_date)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (lead.contact_name, lead.company_name, lead.contact_role, lead.phone, lead.email,
         lead.address, lead.portfolio_size, lead.neighborhoods, lead.source, lead.notes,
         lead.next_action, lead.next_action_date),
    )
    new_id = cur.fetchone()["id"]
    db.commit()
    db.close()
    return {"id": new_id}


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, patch: LeadUpdate):
    fields = patch.model_dump(exclude_unset=True)
    if not fields:
        return {"updated": 0}
    sets = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [lead_id]
    db = get_db()
    cur = db.cursor()
    cur.execute(f"UPDATE leads SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = %s", values)
    db.commit()
    db.close()
    return {"updated": 1}


@router.delete("/leads/{lead_id}")
def delete_lead(lead_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM leads WHERE id = %s", (lead_id,))
    db.commit()
    db.close()
    return {"deleted": 1}


@router.get("/leads/{lead_id}")
def get_lead(lead_id: int):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM leads WHERE id = %s", (lead_id,))
    lead = cur.fetchone()
    if not lead:
        db.close()
        raise HTTPException(404, "Lead not found")
    cur.execute(
        "SELECT * FROM call_log WHERE lead_id = %s ORDER BY called_at DESC",
        (lead_id,),
    )
    calls = cur.fetchall()
    db.close()
    return {"lead": lead, "calls": calls}


# ── Calls ─────────────────────────────────────────────────────────────────

@router.post("/leads/{lead_id}/call")
def log_call(lead_id: int, call: CallLogCreate):
    """Log a call attempt and auto-advance lead status if appropriate."""
    if call.outcome not in OUTCOME_TO_STATUS:
        raise HTTPException(400, f"Invalid outcome: {call.outcome}")

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, status FROM leads WHERE id = %s", (lead_id,))
    lead = cur.fetchone()
    if not lead:
        db.close()
        raise HTTPException(404, "Lead not found")

    cur.execute(
        """INSERT INTO call_log (lead_id, outcome, objection, best_phrase, notes)
           VALUES (%s,%s,%s,%s,%s) RETURNING id, called_at""",
        (lead_id, call.outcome, call.objection, call.best_phrase, call.notes),
    )
    new_call = cur.fetchone()

    new_status = OUTCOME_TO_STATUS.get(call.outcome)
    if new_status and new_status != lead["status"]:
        # Don't downgrade walkthrough_scheduled / quoted on a brushoff call etc.
        rank = {
            "cold": 0, "contacted": 1, "packet_sent": 2,
            "walkthrough_scheduled": 3, "quoted": 4, "won": 5, "dead": 5,
        }
        if rank.get(new_status, 0) >= rank.get(lead["status"], 0) or new_status in ("won", "dead"):
            cur.execute(
                "UPDATE leads SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_status, lead_id),
            )

    db.commit()
    db.close()
    return {"id": new_call["id"], "called_at": new_call["called_at"].isoformat()}


# ── Promote to client ─────────────────────────────────────────────────────

@router.post("/leads/{lead_id}/promote")
def promote_to_client(lead_id: int):
    """Move a won lead into the properties table (the clients list)."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM leads WHERE id = %s", (lead_id,))
    lead = cur.fetchone()
    if not lead:
        db.close()
        raise HTTPException(404, "Lead not found")

    address = lead["address"] or f"{lead['contact_name']} (no address yet)"
    owner_name = lead["company_name"] or lead["contact_name"]

    # Upsert by address to avoid duplicates
    cur.execute("SELECT id FROM properties WHERE address = %s", (address,))
    existing = cur.fetchone()
    if existing:
        property_id = existing["id"]
    else:
        cur.execute(
            "INSERT INTO properties (address, owner_name, access_notes) VALUES (%s,%s,%s) RETURNING id",
            (address, owner_name, lead["notes"]),
        )
        property_id = cur.fetchone()["id"]

    cur.execute(
        "UPDATE leads SET status = 'won', promoted_property_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
        (property_id, lead_id),
    )
    db.commit()
    db.close()
    return {"property_id": property_id, "address": address}


# ── Today's stats / summary ───────────────────────────────────────────────

@router.get("/summary")
def sales_summary():
    """Numbers the salesperson sees at the top of the iPad."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM call_log WHERE called_at::date = CURRENT_DATE")
    calls_today = cur.fetchone()["n"]
    cur.execute(
        "SELECT COUNT(*) AS n FROM call_log WHERE called_at::date = CURRENT_DATE "
        "AND outcome = 'packet_sent'"
    )
    packets_today = cur.fetchone()["n"]
    cur.execute(
        "SELECT COUNT(*) AS n FROM call_log WHERE called_at::date = CURRENT_DATE "
        "AND outcome = 'walkthrough_booked'"
    )
    walkthroughs_today = cur.fetchone()["n"]
    cur.execute("SELECT status, COUNT(*) AS n FROM leads GROUP BY status")
    by_status = {r["status"]: r["n"] for r in cur.fetchall()}
    cur.execute(
        "SELECT COUNT(*) AS n FROM call_log WHERE called_at::date = CURRENT_DATE "
        "AND outcome = 'won'"
    )
    wins_today = cur.fetchone()["n"]
    db.close()
    return {
        "calls_today": calls_today,
        "packets_today": packets_today,
        "walkthroughs_today": walkthroughs_today,
        "wins_today": wins_today,
        "by_status": by_status,
    }


# ── Clients (read-only) ───────────────────────────────────────────────────

@router.get("/clients")
def list_clients():
    """Promoted-to-client list for the sales iPad. Read-only view of properties."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, address, owner_name, access_notes FROM properties ORDER BY id DESC")
    rows = cur.fetchall()
    db.close()
    return rows
