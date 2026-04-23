"""sensory/api.py — HTTP surface for the sensory event bus."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sensory.schema import (
    counts_by_source,
    delete_event,
    get_recent_events,
    record_event,
)
from sensory.salience import (
    get_config as get_salience_config,
    save_config as save_salience_config,
    recent_dropped,
    score_event,
)

router = APIRouter(prefix="/api/sensory", tags=["sensory"])


class RecordRequest(BaseModel):
    source: str = Field(..., description="mic|vision|screen|clipboard|ambient|...")
    text: str
    kind: str = "unknown"
    confidence: float = 1.0
    meta: Optional[Dict[str, Any]] = None
    force: bool = False


@router.post("/record")
async def record(req: RecordRequest) -> dict:
    rid = record_event(
        source=req.source,
        text=req.text,
        kind=req.kind,
        confidence=req.confidence,
        meta=req.meta,
        force=req.force,
    )
    if rid is None:
        # Either empty text OR salience filter dropped it
        return {"id": None, "source": req.source, "kind": req.kind, "dropped": True}
    return {"id": rid, "source": req.source, "kind": req.kind, "dropped": False}


class ScoreRequest(BaseModel):
    source: str
    kind: str = "unknown"
    text: str
    confidence: float = 1.0


@router.post("/score")
async def score(req: ScoreRequest) -> dict:
    """Test the salience filter without writing."""
    s, reason = score_event(req.source, req.kind, req.text, req.confidence)
    cfg = get_salience_config()
    return {
        "score": s,
        "threshold": cfg["threshold"],
        "would_promote": s >= cfg["threshold"],
        "reason": reason,
    }


@router.get("/salience/config")
async def salience_config() -> dict:
    return get_salience_config()


@router.post("/salience/config")
async def update_salience_config(cfg: Dict[str, Any]) -> dict:
    save_salience_config(cfg)
    return {"saved": True, "config": get_salience_config()}


@router.get("/dropped")
async def dropped(limit: int = 50, source: Optional[str] = None) -> dict:
    rows = recent_dropped(limit=limit, source=source)
    return {"count": len(rows), "dropped": rows}


@router.get("/events")
async def events(
    limit: int = 50,
    source: Optional[str] = None,
    kind: Optional[str] = None,
    since: Optional[str] = None,
) -> dict:
    kinds = [kind] if kind else None
    rows = get_recent_events(limit=limit, source=source, kinds=kinds, since_iso=since)
    return {"count": len(rows), "events": rows}


@router.get("/stats")
async def stats(since: Optional[str] = None) -> dict:
    return {"counts_by_source": counts_by_source(since_iso=since)}


@router.delete("/{event_id}")
async def delete(event_id: int) -> dict:
    ok = delete_event(event_id)
    if not ok:
        raise HTTPException(404, "not found")
    return {"deleted": event_id}


@router.get("/health")
async def health() -> dict:
    try:
        rows = get_recent_events(limit=1)
        return {"status": "ok", "latest_ts": rows[0]["created_at"] if rows else None}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
