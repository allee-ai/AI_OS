"""
Work Thread Adapter — read-only introspection of the live work dashboard.

The work dashboard (jake-app) runs on the bycade droplet at
https://bycade.com/api/sales. This adapter hits two endpoints
(/summary and /leads?limit=5) and caches results for 60s so STATE
assembly stays cheap.

JWT is read from the macOS keychain (AIOS-Jake-Token / sales). On
non-Darwin hosts, falls back to the env var JAKE_SERVICE_TOKEN.
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    import certifi
except ImportError:
    certifi = None

try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult


WORK_API_BASE = os.environ.get("WORK_API_BASE", "https://bycade.com/api/sales")
WORK_API_TIMEOUT = 3.0
CACHE_TTL_SEC = 60.0

_cache: Dict[str, Tuple[float, Any]] = {}


def _get_token() -> str:
    env_tok = os.environ.get("JAKE_SERVICE_TOKEN") or os.environ.get("WORK_API_TOKEN")
    if env_tok:
        return env_tok
    if sys.platform == "darwin":
        try:
            r = subprocess.run(
                ["security", "find-generic-password",
                 "-s", "AIOS-Jake-Token", "-a", "sales", "-w"],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0:
                return r.stdout.strip()
        except Exception:
            pass
    return ""


def _http_get(path: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    cached = _cache.get(path)
    if cached and (now - cached[0]) < CACHE_TTL_SEC:
        return cached[1]
    tok = _get_token()
    if not tok:
        return None
    url = f"{WORK_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {tok}"},
        method="GET",
    )
    try:
        if certifi is not None:
            ctx = ssl.create_default_context(cafile=certifi.where())
        else:
            ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=WORK_API_TIMEOUT, context=ctx) as r:
            data = json.loads(r.read().decode())
        _cache[path] = (now, data)
        return data
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    except Exception:
        return None


class WorkThreadAdapter(BaseThreadAdapter):
    """Sales & operations awareness — live mirror of work_dashboard funnel."""

    _name = "work"
    _description = "Live state of the work dashboard: leads, calls today, funnel"
    _prompt_hint = "Use when the user mentions leads, sales, calls, walkthroughs, follow-ups, or pipeline"

    def get_modules(self) -> List[str]:
        return ["summary", "leads"]

    def get_data(self, level: int = 2, limit: int = 50) -> List[Dict]:
        out: List[Dict] = []
        s = _http_get("/summary") or {}
        if s:
            out.append({"kind": "summary", **s})
        leads = _http_get("/leads?limit=5") or []
        if isinstance(leads, list):
            for ld in leads[:limit]:
                out.append({
                    "kind": "lead",
                    "name": ld.get("contact_name"),
                    "status": ld.get("status"),
                    "next_action": ld.get("next_action"),
                    "next_action_date": ld.get("next_action_date"),
                })
        return out

    def health(self) -> HealthReport:
        tok = _get_token()
        if not tok:
            return HealthReport.degraded("no JAKE_SERVICE_TOKEN configured")
        s = _http_get("/summary")
        if s is None:
            return HealthReport.degraded(f"work API unreachable: {WORK_API_BASE}")
        return HealthReport.ok("work API reachable", calls_today=s.get("calls_today", 0))

    def introspect(self, context_level: int = 2, query: str = "", threshold: float = 0.0) -> IntrospectionResult:
        result = IntrospectionResult(
            thread_name=self._name,
            thread_description=self._description,
        )
        summary = _http_get("/summary")
        leads = _http_get("/leads?limit=5")

        if summary is None:
            result.facts.append("work.error: live API unreachable (token or network)")
            result.relevance_score = 0.05
            return result

        by_status = summary.get("by_status") or {}
        total = sum(by_status.values())
        result.state.update({
            "total_leads": total,
            "calls_today": summary.get("calls_today", 0),
            "packets_today": summary.get("packets_today", 0),
            "walkthroughs_today": summary.get("walkthroughs_today", 0),
            "wins_today": summary.get("wins_today", 0),
            "by_status": by_status,
        })

        for status, count in sorted(by_status.items(), key=lambda x: -x[1]):
            result.facts.append(f"work.leads.{status}: {count}")
        for k in ("calls_today", "packets_today", "walkthroughs_today", "wins_today"):
            v = summary.get(k, 0)
            if v:
                result.facts.append(f"work.{k.replace('_today', '')}.today: {v}")

        if isinstance(leads, list):
            for i, ld in enumerate(leads[:3], 1):
                name = ld.get("contact_name") or "(no name)"
                status = ld.get("status") or "?"
                na = ld.get("next_action") or ""
                line = f"work.recent_lead.{i}: {name} [{status}]"
                if na:
                    line += f" — {na}"
                result.facts.append(line)

        # Relevance
        q = (query or "").lower()
        sales_kw = (
            "lead", "leads", "sales", "call", "calls", "walkthrough", "packet",
            "funnel", "pipeline", "follow up", "follow-up", "client", "clients",
            "quote", "bid", "vre", "vanguard", "deal", "dial", "cold call",
        )
        if any(k in q for k in sales_kw):
            result.relevance_score = 0.95
            result.context_level = 3
        elif total > 0:
            result.relevance_score = 0.35
            result.context_level = 1
        else:
            result.relevance_score = 0.05

        return result

    def get_section_metadata(self) -> List[str]:
        s = _http_get("/summary")
        if not s:
            return ["api: unreachable"]
        by_status = s.get("by_status") or {}
        total = sum(by_status.values())
        return [
            f"leads(total): {total}",
            f"calls today: {s.get('calls_today', 0)}",
            f"walkthroughs today: {s.get('walkthroughs_today', 0)}",
            f"wins today: {s.get('wins_today', 0)}",
        ]

    def get_section_rules(self) -> List[str]:
        return [
            "Lead names/phones are PII — never share outside the operator.",
            "Funnel numbers are live; quote them with timestamp implied.",
            "If work API is unreachable, say 'work data stale' instead of guessing.",
        ]
