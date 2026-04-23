"""
Field Thread Adapter
====================

Surfaces situational awareness to STATE — what's around the user right now,
what unfamiliar patterns are recurring, and what alerts need attention.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone

try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from agent.threads.field import schema as field_schema
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from . import schema as field_schema


class FieldThreadAdapter(BaseThreadAdapter):
    """Situational awareness — environments, presences, alerts."""

    _name = "field"
    _description = "What's around me — environments, recurring devices, situational alerts"
    _prompt_hint = "Use to ground awareness of physical surroundings; flag anomalies, never identify individuals"

    def get_modules(self) -> List[str]:
        return ["environments", "presences", "alerts"]

    def get_data(self, level: int = 2, limit: int = 50) -> List[Dict]:
        envs = field_schema.list_environments(limit=10)
        alerts = field_schema.list_alerts(unack_only=True, limit=10)
        out: List[Dict] = []
        for e in envs:
            out.append({
                "kind": "environment",
                "label": e.get("label"),
                "type": e.get("kind"),
                "visits": e.get("visit_count"),
            })
        for a in alerts:
            out.append({
                "kind": "alert",
                "severity": a.get("severity"),
                "title": a.get("title"),
            })
        return out[:limit]

    def health(self) -> HealthReport:
        try:
            stats = field_schema.get_stats()
            unack = stats.get("unack_alerts", 0)
            if unack > 0:
                return HealthReport.degraded(f"{unack} unacknowledged field alert(s)", **stats)
            return HealthReport.ok("field clear", **stats)
        except Exception as e:
            return HealthReport.error(f"field schema error: {e}")

    def introspect(self, context_level: int = 2, query: str = "", threshold: float = 0.0) -> IntrospectionResult:
        result = IntrospectionResult(
            thread_name=self._name,
            thread_description=self._description,
        )
        try:
            stats = field_schema.get_stats()
            envs = field_schema.list_environments(limit=5)
            alerts = field_schema.list_alerts(unack_only=True, limit=5)
            strangers = field_schema.detect_persistent_strangers(min_envs=2, min_days=2)
        except Exception as e:
            result.facts.append(f"field.error: {e}")
            return result

        # Always-on metadata
        result.state.update({
            "environments": stats.get("field_environments", 0),
            "active_presences": stats.get("field_presences", 0),
            "unack_alerts": stats.get("unack_alerts", 0),
            "persistent_strangers": len(strangers),
        })

        for e in envs:
            label = e.get("label", "?")
            result.facts.append(f"field.env.{e.get('env_id', '?')}: {label} ({e.get('kind', 'unknown')})")

        for a in alerts:
            sev = a.get("severity", "info")
            result.facts.append(f"field.alert.{sev}: {a.get('title', '')}")

        if strangers:
            result.facts.append(
                f"field.strangers: {len(strangers)} unfamiliar device(s) seen across multiple environments"
            )

        # Relevance: bumps if query mentions surroundings / threats / who
        keywords = ("around", "near", "follow", "stranger", "device", "wifi",
                    "where", "safe", "watch", "surveill", "threat", "alert")
        if any(k in (query or "").lower() for k in keywords):
            result.relevance_score = 0.9
            result.context_level = 3
        else:
            result.relevance_score = 0.2 if stats.get("unack_alerts", 0) else 0.05
            result.context_level = 1

        return result

    def get_section_metadata(self) -> List[str]:
        try:
            stats = field_schema.get_stats()
            return [
                f"environments: {stats.get('field_environments', 0)}",
                f"active_presences: {stats.get('field_presences', 0)}",
                f"alerts(unack): {stats.get('unack_alerts', 0)}",
            ]
        except Exception:
            return []

    def get_section_rules(self) -> List[str]:
        return [
            "Never identify individuals from field data — describe patterns only.",
            "Never expose raw identifiers; field stores only one-way hashes.",
            "Treat alerts as advisory; surface them but do not act autonomously.",
        ]

    def sync(self) -> None:
        """Apply TTL cleanup as part of sync loop."""
        super().sync()
        try:
            field_schema.cleanup()
        except Exception:
            pass
