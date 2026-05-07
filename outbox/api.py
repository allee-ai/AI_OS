"""
Outbox API
==========
Endpoints:
    GET    /api/outbox                       list pending (or by status)
    GET    /api/outbox/{id}                  one card
    POST   /api/outbox                       create (motors call this)
    POST   /api/outbox/{id}/approve          mark approved
    POST   /api/outbox/{id}/reject           mark rejected
    POST   /api/outbox/{id}/edit             save edited body + approve
    GET    /api/outbox/_/count                pending count (for now-bar)
    POST   /api/outbox/_/seed_from_goals      backfill cards from existing
                                              pending proposed_goals
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .schema import (
    create_card,
    list_cards,
    get_card,
    resolve_card,
    count_pending,
)


router = APIRouter(prefix="/api/outbox", tags=["outbox"])


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────

class CardCreate(BaseModel):
    motor: str
    title: str
    body: str = ""
    context: Optional[Dict[str, Any]] = None
    priority: float = 0.5
    related_table: Optional[str] = None
    related_id: Optional[int] = None
    expires_at: Optional[str] = None


class Resolution(BaseModel):
    note: Optional[str] = None


class EditResolution(BaseModel):
    edited_body: str
    note: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Reads
# ─────────────────────────────────────────────────────────────

@router.get("")
def get_outbox(
    status: str = Query("pending"),
    motor: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> List[Dict[str, Any]]:
    return list_cards(status=status, motor=motor, limit=limit)


@router.get("/_/count")
def get_count(motor: Optional[str] = Query(None)) -> Dict[str, int]:
    return {"pending": count_pending(motor=motor)}


@router.get("/{card_id}")
def get_one(card_id: int) -> Dict[str, Any]:
    card = get_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"outbox card {card_id} not found")
    return card


# ─────────────────────────────────────────────────────────────
# Writes
# ─────────────────────────────────────────────────────────────

@router.post("")
def post_card(card: CardCreate) -> Dict[str, Any]:
    card_id = create_card(
        motor=card.motor,
        title=card.title,
        body=card.body,
        context=card.context,
        priority=card.priority,
        related_table=card.related_table,
        related_id=card.related_id,
        expires_at=card.expires_at,
    )
    out = get_card(card_id)
    return out or {"id": card_id}


@router.post("/{card_id}/approve")
def approve(card_id: int, body: Optional[Resolution] = None) -> Dict[str, Any]:
    note = body.note if body else None
    card = resolve_card(card_id, status="approved", note=note)
    if not card:
        raise HTTPException(status_code=404, detail=f"outbox card {card_id} not found")
    _maybe_propagate_to_related(card)
    return card


@router.post("/{card_id}/reject")
def reject(card_id: int, body: Optional[Resolution] = None) -> Dict[str, Any]:
    note = body.note if body else None
    card = resolve_card(card_id, status="rejected", note=note)
    if not card:
        raise HTTPException(status_code=404, detail=f"outbox card {card_id} not found")
    _maybe_propagate_to_related(card)
    return card


@router.post("/{card_id}/edit")
def edit(card_id: int, body: EditResolution) -> Dict[str, Any]:
    card = resolve_card(
        card_id,
        status="edited",
        note=body.note,
        edited_body=body.edited_body,
    )
    if not card:
        raise HTTPException(status_code=404, detail=f"outbox card {card_id} not found")
    _maybe_propagate_to_related(card)
    return card


# ─────────────────────────────────────────────────────────────
# Side-effects: when a card is resolved, mirror status onto the
# producing row when we know how. Initial wiring: proposed_goals.
# ─────────────────────────────────────────────────────────────

def _maybe_propagate_to_related(card: Dict[str, Any]) -> None:
    """If this card is bound to a known producer table, mirror the resolution.

    Best-effort — never raise. New motors add their own branches here.
    """
    try:
        rt = card.get("related_table")
        rid = card.get("related_id")
        status = card.get("status")
        if not rt or rid is None or not status:
            return

        from contextlib import closing as _closing
        from data.db import get_connection as _gc

        if rt == "proposed_goals":
            new_status = {
                "approved": "approved",
                "rejected": "rejected",
                "edited":   "approved",
            }.get(status)
            if new_status is None:
                return
            with _closing(_gc()) as conn:
                conn.execute(
                    "UPDATE proposed_goals SET status=?, resolved_at=datetime('now') "
                    "WHERE id=? AND status='pending'",
                    (new_status, int(rid)),
                )
                conn.commit()
    except Exception as e:  # noqa: BLE001
        try:
            print(f"[outbox] propagate failed: {e}")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# Bootstrap: backfill cards from currently-pending proposed_goals so
# the outbox isn't empty on first load.
# ─────────────────────────────────────────────────────────────

@router.post("/_/seed_from_goals")
def seed_from_goals(limit: int = Query(20, ge=1, le=200)) -> Dict[str, Any]:
    """One-shot helper: turn pending proposed_goals into outbox cards.

    Idempotent thanks to the (motor, related_table, related_id) dedupe in
    `create_card`. Safe to call repeatedly.
    """
    from contextlib import closing as _closing
    from data.db import get_connection as _gc

    created: List[int] = []
    with _closing(_gc(readonly=True)) as conn:
        rows = conn.execute(
            "SELECT id, goal, rationale, priority, urgency, sources, risk "
            "FROM proposed_goals WHERE status='pending' "
            "ORDER BY COALESCE(urgency, 50) DESC, id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()

    for r in rows:
        urgency = r["urgency"] if r["urgency"] is not None else 50
        prio = max(0.0, min(1.0, urgency / 100.0))
        title = (r["goal"] or "(no goal text)").strip()
        body = (r["rationale"] or "").strip()
        ctx = {
            "priority_label": r["priority"],
            "urgency": urgency,
            "risk": r["risk"],
            "sources": r["sources"],
        }
        card_id = create_card(
            motor="goal_proposal",
            title=title[:240],
            body=body,
            context=ctx,
            priority=prio,
            related_table="proposed_goals",
            related_id=int(r["id"]),
        )
        created.append(card_id)

    return {"created_or_existing": len(created), "ids": created}


# ─────────────────────────────────────────────────────────────
# Copilot inbox: phone → Copilot-in-VS-Code lane.
# ─────────────────────────────────────────────────────────────

class CopilotRequest(BaseModel):
    title: str
    body: str = ""
    priority: float = 0.6
    context: Optional[Dict[str, Any]] = None


@router.post("/_/copilot_request")
def post_copilot_request(req: CopilotRequest) -> Dict[str, Any]:
    """Phone-friendly endpoint: submit a request for Copilot to act on.

    Creates an outbox card with motor='copilot_request' AND drops a
    markdown mirror file into workspace/_copilot_inbox/ so VS Code's
    file explorer shows it the moment Cade opens the laptop.

    Mobile dashboard wires a "Ask Copilot" button to POST here.
    """
    from . import copilot_inbox
    return copilot_inbox.submit(
        title=req.title,
        body=req.body,
        priority=req.priority,
        context=req.context,
    )


@router.post("/_/copilot_request/{card_id}/done")
def post_copilot_request_done(
    card_id: int,
    body: Optional[Resolution] = None,
) -> Dict[str, Any]:
    """Mark a copilot_request done. Removes the workspace mirror file."""
    from . import copilot_inbox
    note = body.note if body else None
    card = copilot_inbox.mark_done(card_id, note=note)
    if not card:
        raise HTTPException(status_code=404, detail=f"copilot request {card_id} not found")
    return card


@router.get("/_/copilot_request/pending")
def get_copilot_pending(limit: int = Query(20, ge=1, le=200)) -> List[Dict[str, Any]]:
    """List pending copilot_requests for laptop turn_start.py to pick up."""
    from . import copilot_inbox
    return copilot_inbox.pending(limit=limit)
