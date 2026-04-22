"""
Mobile Remote Control API
─────────────────────────
Slim, phone-optimised endpoints for quick actions from any browser or HTTP client.
All endpoints return compact JSON. Requires X-Device-Token header when AIOS_MOBILE_TOKEN is set.

Endpoints:
  GET  /api/mobile/status        — Dashboard: loops, tasks, agent status
  POST /api/mobile/chat          — Quick send message, get reply
  POST /api/mobile/task          — Add a task (background or immediate)
  POST /api/mobile/goal          — Propose a new goal (pings phone + pushes to Copilot)
  POST /api/mobile/note          — Quick-add a note
  POST /api/mobile/loops/{name}  — Pause / resume a loop
  GET  /api/mobile/loops         — All loop statuses (compact)
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import hmac
import os

router = APIRouter(prefix="/api/mobile", tags=["mobile"])

_PANEL_HTML = (Path(__file__).parent / "mobile_panel.html").read_text()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def mobile_panel():
    """Serve the mobile control panel UI."""
    return _PANEL_HTML


# ── Auth ──────────────────────────────────────────────────────────────────────
# Set AIOS_MOBILE_TOKEN env var to require a token.  When unset, endpoints are
# open (handy for local-only testing on the same machine / Tailscale network).

def _check_token(x_device_token: Optional[str] = Header(None)):
    expected = os.getenv("AIOS_MOBILE_TOKEN")
    if not expected:
        return                       # no token configured → open access
    if not x_device_token:
        raise HTTPException(status_code=401, detail="X-Device-Token header required")
    if not hmac.compare_digest(x_device_token, expected):
        raise HTTPException(status_code=401, detail="Invalid device token")


# ── Models ────────────────────────────────────────────────────────────────────

class QuickChat(BaseModel):
    text: str
    session_id: Optional[str] = None

class QuickTask(BaseModel):
    goal: str
    execute_now: bool = False

class QuickGoal(BaseModel):
    goal: str
    rationale: Optional[str] = ""
    priority: Optional[str] = "medium"   # urgent | high | medium | low
    urgency: Optional[int] = None        # 0-100

class QuickNote(BaseModel):
    text: str

class LoopAction(BaseModel):
    action: str          # "pause" or "resume"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def mobile_status(_=Depends(_check_token)):
    """One-glance dashboard: agent, loops, recent tasks."""
    # Loops
    loops = []
    try:
        from agent.subconscious import _loop_manager
        if _loop_manager:
            for s in _loop_manager.get_stats():
                loops.append({
                    "name": s.get("name"),
                    "status": s.get("status"),
                    "is_busy": s.get("is_busy", False),
                    "runs": s.get("run_count", 0),
                    "interval": s.get("interval"),
                    "initial_delay": s.get("initial_delay", 0),
                    "last_run": s.get("last_run"),
                    "last_duration": s.get("last_duration"),
                    "avg_duration": s.get("avg_duration"),
                })
    except Exception:
        pass

    # Recent tasks
    tasks = []
    try:
        from agent.subconscious.loops import get_tasks
        for t in get_tasks(limit=5):
            tasks.append({"id": t["id"], "goal": t["goal"], "status": t["status"]})
    except Exception:
        pass

    # Agent
    agent_status = "unknown"
    try:
        from agent.services.agent_service import get_agent_service
        svc = get_agent_service()
        info = await svc.get_agent_status()
        agent_status = info.get("status", "ready")
    except Exception:
        pass

    return {"agent": agent_status, "loops": loops, "tasks": tasks}


@router.post("/chat")
async def mobile_chat(msg: QuickChat, _=Depends(_check_token)):
    """Send a message, get the reply. No WebSocket needed."""
    if not msg.text.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    from agent.services.agent_service import get_agent_service
    svc = get_agent_service()
    reply = await svc.send_message(msg.text.strip(), msg.session_id)
    return {"reply": reply.content, "session_id": msg.session_id}


@router.post("/task")
async def mobile_task(t: QuickTask, _=Depends(_check_token)):
    """Add a task from your phone."""
    if not t.goal.strip():
        raise HTTPException(status_code=400, detail="Goal cannot be empty")

    from agent.subconscious.loops import create_task
    task = create_task(t.goal.strip(), source="mobile")

    if t.execute_now:
        try:
            from agent.subconscious import _loop_manager
            if _loop_manager:
                planner = _loop_manager.get_loop("task_planner")
                if planner and hasattr(planner, "execute_task"):
                    task = planner.execute_task(task["id"])
        except Exception:
            pass

    return {"id": task["id"], "goal": task["goal"], "status": task["status"]}


@router.post("/goal")
async def mobile_goal(g: QuickGoal, _=Depends(_check_token)):
    """Propose a new goal from the phone. Fires phone ping + forwards to VS Code Copilot."""
    text = (g.goal or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Goal cannot be empty")
    priority = (g.priority or "medium").lower()
    if priority not in ("urgent", "high", "medium", "low"):
        raise HTTPException(status_code=400, detail="priority must be urgent/high/medium/low")

    from agent.subconscious.loops.goals import propose_goal, set_goal_urgency
    gid = propose_goal(
        goal=text,
        rationale=(g.rationale or ""),
        priority=priority,
        sources=["mobile"],
    )
    if not gid:
        raise HTTPException(status_code=500, detail="Failed to create goal")
    if g.urgency is not None:
        try:
            set_goal_urgency(gid, int(g.urgency))
        except Exception:
            pass

    # Fire phone ping immediately (propose_goal's vs_bridge hook already
    # handles the Copilot push — don't duplicate that here).
    try:
        from agent.services.alerts import fire_alerts
        fire_alerts(
            message=f"new goal #{gid} [{priority}]: {text[:80]}",
            priority="high" if priority in ("urgent", "high") else "default",
            source="mobile_goal",
        )
    except Exception:
        pass

    return {"id": gid, "goal": text, "priority": priority, "urgency": g.urgency}


@router.post("/note")
async def mobile_note(n: QuickNote, _=Depends(_check_token)):
    """Quick-add a note."""
    if not n.text.strip():
        raise HTTPException(status_code=400, detail="Note cannot be empty")

    from agent.subconscious.api import _ensure_notes_table
    from data.db import get_connection
    from contextlib import closing

    _ensure_notes_table()
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "INSERT INTO user_notes (text) VALUES (?)",
            (n.text.strip(),),
        )
        conn.commit()
        return {"id": cur.lastrowid, "text": n.text.strip()}


@router.post("/loops/{loop_name}")
async def mobile_loop_control(loop_name: str, body: LoopAction, _=Depends(_check_token)):
    """Pause or resume a loop by name."""
    from agent.subconscious import _loop_manager
    if not _loop_manager:
        raise HTTPException(status_code=503, detail="Loops not running")

    loop = _loop_manager.get_loop(loop_name)
    if not loop:
        raise HTTPException(status_code=404, detail=f"Loop '{loop_name}' not found")

    if body.action == "pause":
        loop.pause()
    elif body.action == "resume":
        loop.resume()
    else:
        raise HTTPException(status_code=400, detail="action must be 'pause' or 'resume'")

    return {"loop": loop_name, "status": body.action + "d"}


@router.get("/loops")
async def mobile_loops(_=Depends(_check_token)):
    """Compact loop status list."""
    from agent.subconscious import _loop_manager
    if not _loop_manager:
        return {"loops": []}
    return {
        "loops": [
            {
                "name": s["name"],
                "status": s["status"],
                "is_busy": s.get("is_busy", False),
                "runs": s.get("run_count", 0),
                "errors": s.get("error_count", 0),
                "interval": s.get("interval"),
                "initial_delay": s.get("initial_delay", 0),
                "last_run": s.get("last_run"),
                "last_duration": s.get("last_duration"),
                "avg_duration": s.get("avg_duration"),
            }
            for s in _loop_manager.get_stats()
        ]
    }
