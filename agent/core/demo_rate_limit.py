"""Per-IP rate limiting + daily visitor cap for the public demo.

Protects the OpenAI key from spend spikes when AI_OS is running with
AIOS_DEMO_LLM_CHAT_ONLY=1 backed by gpt-4o.

Three concentric limits:
    1. DAILY_IP_CAP   – first N unique IPs per day get to chat at all.
                        IP #N+1 onward sees a friendly canned reply.
    2. PER_IP_MSGS    – within an allowed IP, cap messages per day.
    3. DAILY_BUDGET   – hard global ceiling: stop calling the LLM once
                        we've sent more than ~$X worth of chat tokens
                        today. Estimated via a flat per-message cost.

State is kept in-memory and rotates at midnight UTC. This is fine for
a single-VM demo. For a multi-replica deployment, swap the store for
Redis without touching the middleware shape.

Visitors who get blocked still see a real reply — they don't get an
HTTP error. The whole point is the demo never feels broken.

Env knobs (all optional, defaults are conservative):
    AIOS_DEMO_DAILY_IP_CAP   default 20
    AIOS_DEMO_PER_IP_MSGS    default 30
    AIOS_DEMO_DAILY_BUDGET   default 5.00   (USD per day)
    AIOS_DEMO_COST_PER_MSG   default 0.02   (USD, gpt-4o rough average)
    AIOS_DEMO_RATE_PATH      default /api/chat/   (any /api/chat/*)
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# ── Config ────────────────────────────────────────────────────────────

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


DAILY_IP_CAP   = _env_int(  "AIOS_DEMO_DAILY_IP_CAP",  20)
PER_IP_MSGS    = _env_int(  "AIOS_DEMO_PER_IP_MSGS",   30)
DAILY_BUDGET   = _env_float("AIOS_DEMO_DAILY_BUDGET",  5.00)
COST_PER_MSG   = _env_float("AIOS_DEMO_COST_PER_MSG",  0.02)
RATE_PATH      = os.environ.get("AIOS_DEMO_RATE_PATH", "/api/chat/").strip() or "/api/chat/"


# ── Canned replies (visitor never sees a hard error) ──────────────────

_REPLY_OVER_IP_CAP = (
    "[demo limit reached for today]\n\n"
    "We cap the public demo at the first {cap} unique visitors per day so "
    "the OpenAI bill stays bounded. Try again tomorrow, or run AI_OS locally "
    "to talk to an unmetered Nola:\n\n"
    "  https://github.com/allee-ai/AI_OS\n\n"
    "Everything you'd see in the demo runs on a $300 laptop with Ollama."
)

_REPLY_OVER_PER_IP = (
    "[per-visitor message cap reached]\n\n"
    "You've hit the {cap}-message-per-day cap for this demo. Resets at 00:00 UTC. "
    "Run AI_OS locally if you want to keep going:\n\n"
    "  https://github.com/allee-ai/AI_OS"
)

_REPLY_OVER_BUDGET = (
    "[demo budget reached for today]\n\n"
    "The demo's daily LLM budget is exhausted. Resets at 00:00 UTC. "
    "Run AI_OS locally for unmetered access:\n\n"
    "  https://github.com/allee-ai/AI_OS"
)


# ── State ─────────────────────────────────────────────────────────────

class _DailyState:
    """All-in-memory counters, rotated at UTC midnight."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.day: str = ""
        self.ip_messages: Dict[str, int] = {}    # ip → messages today
        self.spend: float = 0.0                  # USD spent today (estimated)

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _maybe_rotate(self) -> None:
        now = self._today()
        if now != self.day:
            self.day = now
            self.ip_messages.clear()
            self.spend = 0.0

    def check_and_consume(self, ip: str) -> Tuple[bool, str]:
        """Atomically check whether *ip* may send a chat message right now.

        Returns (allowed, reason). When allowed=True, counters have already
        been incremented as if the call happened. When False, *reason* is
        one of "ip_cap", "per_ip", "budget".
        """
        with self.lock:
            self._maybe_rotate()

            # 1. Daily budget
            if self.spend >= DAILY_BUDGET:
                return False, "budget"

            # 2. Daily unique-IP cap
            if ip not in self.ip_messages and len(self.ip_messages) >= DAILY_IP_CAP:
                return False, "ip_cap"

            # 3. Per-IP message cap
            current = self.ip_messages.get(ip, 0)
            if current >= PER_IP_MSGS:
                return False, "per_ip"

            self.ip_messages[ip] = current + 1
            self.spend += COST_PER_MSG
            return True, ""

    def snapshot(self) -> Dict[str, object]:
        with self.lock:
            self._maybe_rotate()
            return {
                "day_utc": self.day,
                "unique_ips": len(self.ip_messages),
                "ip_cap": DAILY_IP_CAP,
                "spend_usd": round(self.spend, 4),
                "budget_usd": DAILY_BUDGET,
                "per_ip_msgs": PER_IP_MSGS,
            }


_STATE = _DailyState()


def get_demo_rate_snapshot() -> Dict[str, object]:
    """Public read-only snapshot. Used by /api/demo/rate-status (added by the
    demo server) and by tests."""
    return _STATE.snapshot()


# ── Middleware ────────────────────────────────────────────────────────

def _client_ip(request) -> str:
    """Extract caller IP, honoring X-Forwarded-For when behind a reverse proxy.

    Trusts only the first hop in XFF. Fine for the simple Caddy/nginx in
    front of a single VM. For multi-hop proxies, configure the proxy to
    rewrite XFF before it reaches the app.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    real = request.headers.get("x-real-ip")
    if real:
        return real.strip()
    if request.client:
        return request.client.host
    return "unknown"


class DemoRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limits to chat-path requests on the public demo.

    Only kicks in when AIOS_DEMO_LLM_CHAT_ONLY=1, which is the canonical
    "this is the public demo" flag. Outside that mode this middleware is
    a no-op so it's safe to register on the shared FastAPI app.
    """

    async def dispatch(self, request, call_next):
        # Pass-through unless we're explicitly in chat-only demo mode.
        if os.environ.get("AIOS_DEMO_LLM_CHAT_ONLY", "").lower() not in ("1", "true", "yes"):
            return await call_next(request)

        # Only rate-limit chat endpoints. Reads (GET /api/*), STATE inspection,
        # and other allowlisted paths fall through.
        if not request.url.path.startswith(RATE_PATH):
            return await call_next(request)

        # Cheap heuristic: only count actual message-sending POSTs. WebSocket
        # upgrade is GET so it doesn't count here; if you wire up a WS chat
        # path later, gate it inside the WS handler instead.
        if request.method != "POST":
            return await call_next(request)

        ip = _client_ip(request)
        allowed, reason = _STATE.check_and_consume(ip)
        if allowed:
            return await call_next(request)

        # Build a SendMessageResponse-shaped JSON so the frontend renders it
        # as a normal assistant reply instead of an error toast.
        if reason == "budget":
            content = _REPLY_OVER_BUDGET
        elif reason == "per_ip":
            content = _REPLY_OVER_PER_IP.format(cap=PER_IP_MSGS)
        else:
            content = _REPLY_OVER_IP_CAP.format(cap=DAILY_IP_CAP)

        return JSONResponse(
            status_code=200,
            content={
                "message": {
                    "id": f"demo_limit_{int(time.time() * 1000)}",
                    "role": "assistant",
                    "content": content,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "agent_status": "rate_limited",
                "demo_limit": {"reason": reason, **_STATE.snapshot()},
            },
        )
