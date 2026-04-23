"""
Field Thread API
================
Read-mostly API. Recording observations is the only write op exposed
publicly, and even that is rate-limit-friendly + privacy-hashed.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent.threads.field import schema as field_schema

router = APIRouter(prefix="/api/field", tags=["field"])


# ----- models -----

class EnvironmentIn(BaseModel):
    label: str
    kind: str = "unknown"
    wifi_bssid: Optional[str] = None  # raw, will be hashed


class ObservationIn(BaseModel):
    raw_id: str = Field(..., description="raw MAC/BLE id — hashed on insert, never stored")
    kind: str = Field(..., description="wifi | ble | audio | visual")
    env_id: Optional[str] = None
    rssi: Optional[int] = None


class AlertIn(BaseModel):
    severity: str = "info"
    title: str
    detail: str = ""
    evidence: str = ""


# ----- routes -----

@router.get("/health")
def health() -> Dict[str, Any]:
    return {"stats": field_schema.get_stats()}


@router.get("/environments")
def get_environments(limit: int = 50) -> List[Dict[str, Any]]:
    return field_schema.list_environments(limit=limit)


@router.post("/environments")
def post_environment(env: EnvironmentIn) -> Dict[str, str]:
    env_id = field_schema.upsert_environment(env.label, env.kind, env.wifi_bssid)
    return {"env_id": env_id}


@router.get("/presences")
def get_presences(env_id: Optional[str] = None, since_secs: int = 86400, limit: int = 100):
    return field_schema.list_presences(env_id=env_id, since_secs=since_secs, limit=limit)


@router.get("/strangers")
def get_strangers(min_envs: int = 2, min_days: int = 2) -> List[Dict[str, Any]]:
    """Devices seen in multiple of your environments without being daily fixtures."""
    return field_schema.detect_persistent_strangers(min_envs=min_envs, min_days=min_days)


@router.post("/observations")
def post_observation(obs: ObservationIn) -> Dict[str, str]:
    h = field_schema.record_observation(obs.raw_id, obs.kind, obs.env_id, obs.rssi)
    return {"id_hash": h}


@router.get("/alerts")
def get_alerts(unack_only: bool = False, limit: int = 50):
    return field_schema.list_alerts(unack_only=unack_only, limit=limit)


@router.post("/alerts")
def post_alert(a: AlertIn) -> Dict[str, int]:
    return {"id": field_schema.raise_alert(a.severity, a.title, a.detail, a.evidence)}


@router.post("/alerts/{alert_id}/ack")
def post_ack(alert_id: int) -> Dict[str, str]:
    field_schema.ack_alert(alert_id)
    return {"status": "ok"}


@router.post("/cleanup")
def post_cleanup() -> Dict[str, int]:
    return field_schema.cleanup()
