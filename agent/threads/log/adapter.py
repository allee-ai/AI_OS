"""
Log Thread Adapter
==================

Provides temporal awareness and history to Agent.

This thread answers: "What has happened? When? How long have we been talking?"

Log events use RECENCY-based levels, not depth-based:
- L1 = Last 10 events (quick context)
- L2 = Last 100 events (conversational history)  
- L3 = Last 1000 events (full timeline)

Weight represents temporal importance for concept mapping.

Modules:
- events: System events (start, stop, errors)
- sessions: Conversation session metadata
- temporal: Time-based patterns and facts
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from agent.threads.log.schema import pull_log_events
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from .schema import pull_log_events

# Recency limits per context level
LOG_LIMITS = {1: 10, 2: 100, 3: 1000}

# Event type relevance scores for sparse activation (0-10 scale)
# Used with score_thread_relevance() for three-tier gating
EVENT_TYPE_RELEVANCE = {
    "convo": 8,       # High: Conversation events (direct interaction)
    "memory": 7,      # High: Memory/reflection events (cognitive)
    "user_action": 6, # Medium-High: User actions (significant)
    "file": 4,        # Medium: File operations (context dependent)
    "system": 2,      # Low: System events (background)
    "activation": 1   # Low: Activation patterns (technical)
}


class LogThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for temporal awareness — events, sessions, history.
    
    Log uses recency-based levels:
    - L1 = 10 most recent (quick glance)
    - L2 = 100 most recent (conversation context)
    - L3 = 1000 most recent (full history)
    """
    
    _name = "log"
    _description = "Temporal awareness and history"
    
    def __init__(self):
        super().__init__()
        self._session_start: Optional[datetime] = None
        self._message_count: int = 0
        self._session_id: Optional[str] = None

    def _ensure_session(self) -> None:
        """Auto-start a session if one isn't active."""
        if self._session_start is None:
            self.start_session()
    
    def get_data(self, level: int = 2, limit: int = None) -> List[Dict]:
        """
        Get log data by recency level.
        
        Level determines how far back to look:
        - L1 = 10 events
        - L2 = 100 events
        - L3 = 1000 events
        """
        recency_limit = limit or LOG_LIMITS.get(level, 100)
        all_data = []
        
        for module in ["events", "sessions"]:
            rows = pull_log_events(module_name=module, limit=recency_limit)
            for row in rows:
                all_data.append({**row, "module": module})
        
        # Sort by timestamp descending
        all_data.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_data[:recency_limit]
    
    def start_session(self) -> str:
        """Start a new conversation session."""
        self._session_start = datetime.now(timezone.utc)
        self._message_count = 0
        session_id = self._session_start.strftime("%Y%m%d_%H%M%S")
        self._session_id = session_id
        
        self.push(
            module="sessions",
            key=f"session_{session_id}",
            metadata={"type": "session", "description": "Conversation session"},
            data={
                "start_time": self._session_start.isoformat(),
                "status": "active",
            },
            level=1,
            weight=0.5
        )
        
        return session_id
    
    def log_event(
        self,
        event_type: str,
        source: str,
        message: str,
        weight: float = 0.3
    ) -> None:
        """Log a system event with weight."""
        timestamp = datetime.now(timezone.utc)
        
        self.push(
            module="events",
            key=f"evt_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}",
            metadata={"type": event_type, "source": source},
            data={"message": message, "timestamp": timestamp.isoformat()},
            level=1,
            weight=weight
        )
    
    def record_message(self) -> None:
        """Record that a message was exchanged."""
        self._message_count += 1
    
    def get_session_duration(self) -> Optional[float]:
        """Get current session duration in seconds."""
        if self._session_start:
            delta = datetime.now(timezone.utc) - self._session_start
            return delta.total_seconds()
        return None
    
    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """Get recent events by timestamp/weight."""
        return pull_log_events(module_name="events", limit=limit)
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions."""
        return pull_log_events(module_name="sessions", limit=limit)
    
    def health(self) -> HealthReport:
        """Check log thread health by counting recent events."""
        try:
            from .schema import get_events
            events = get_events(limit=10)
            total = len(events)
            
            if total > 0:
                return HealthReport.ok(f"{total} log entries", row_count=total)
            else:
                return HealthReport.ok("Ready", row_count=0)
        except Exception as e:
            return HealthReport.error(f"Log health check failed: {e}")

    def _get_raw_facts(self, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """Get raw facts with l1/l2/l3 value tiers for _budget_fill.

        Returns dicts with: path, l1_value, l2_value, l3_value, weight.
        """
        self._ensure_session()
        raw: List[Dict] = []

        # Session metadata — always high weight (temporal context)
        duration = self.get_session_duration()
        if duration:
            if duration < 60:
                dur_str = f"{int(duration)}s"
            elif duration < 3600:
                dur_str = f"{int(duration / 60)}m"
            else:
                dur_str = f"{duration / 3600:.1f}h"
            raw.append({
                "path": "log.session.duration",
                "l1_value": dur_str,
                "l2_value": f"Session active for {dur_str}",
                "l3_value": (
                    f"Current session started at "
                    f"{self._session_start.isoformat()}, active for {dur_str}"
                ),
                "weight": 0.9,
            })

        if self._message_count > 0:
            raw.append({
                "path": "log.session.messages",
                "l1_value": str(self._message_count),
                "l2_value": f"{self._message_count} messages exchanged",
                "l3_value": (
                    f"{self._message_count} messages exchanged in current session"
                ),
                "weight": 0.8,
            })

        # Events — convert to l1/l2/l3 dicts
        events = self.get_recent_events(limit)
        for i, evt in enumerate(events):
            meta = evt.get("metadata", {})
            event_type = meta.get("type", "system")
            event_type_clean = (
                event_type.split(":")[0] if ":" in event_type else event_type
            )
            source = meta.get("source", "")
            data = evt.get("data", {})
            msg = data.get("message", "")
            timestamp = data.get("timestamp", "")
            stored_weight = evt.get("weight", 0.3)

            if not msg or stored_weight < min_weight:
                continue

            # Blend stored weight with event-type relevance
            type_relevance = EVENT_TYPE_RELEVANCE.get(event_type_clean, 3) / 10.0
            weight = max(stored_weight, type_relevance)

            raw.append({
                "path": f"log.events.{i}",
                "l1_value": f"{msg[:40]} [{event_type_clean}]",
                "l2_value": f"{msg[:80]} [{event_type_clean}]",
                "l3_value": (
                    f"{msg} [{event_type_clean}] source={source} at={timestamp}"
                ),
                "weight": weight,
            })

        return raw[:limit]
    
    def get_section_metadata(self) -> List[str]:
        """Permanent log metadata for STATE section header."""
        try:
            lines = []
            if hasattr(self, '_session_id') and self._session_id:
                lines.append(f"  session: {self._session_id}")
            if hasattr(self, '_session_start') and self._session_start:
                elapsed = (datetime.now(timezone.utc) - self._session_start).total_seconds()
                if elapsed < 3600:
                    lines.append(f"  duration: {int(elapsed // 60)}m")
                else:
                    lines.append(f"  duration: {elapsed / 3600:.1f}h")
            if hasattr(self, '_message_count'):
                lines.append(f"  messages: {self._message_count}")
            try:
                from agent.threads.log.schema import get_log_stats
                stats = get_log_stats()
                lines.append(f"  total_events: {stats.get('total_events', 0)}")
            except Exception:
                pass
            return lines
        except Exception:
            return []

    def get_section_rules(self) -> List[str]:
        return [
            "  rules:",
            "  - Events shown are a sample. Do not fabricate events not listed here.",
            "  - To see more history, ask the user or use search tools.",
        ]

    def introspect(self, context_level: int = 2, query: str = None, threshold: float = 0.0) -> IntrospectionResult:
        """
        Log introspection with budget-aware fact packing.

        Uses _budget_fill to fit temporal facts within a per-level
        token budget.  Top facts get full detail; tail facts are
        downgraded to L1 so context stays compact.

        Args:
            context_level: HEA level (1=lean, 2=medium, 3=full)
            query: Optional query for relevance filtering
            threshold: Thread relevance score (0-10, inverted by orchestrator)
        """
        relevant_concepts: List[str] = []

        min_weight = threshold / 10.0
        raw = self._get_raw_facts(min_weight=min_weight)

        if query:
            raw, relevant_concepts = self._relevance_boost(raw, query)

        facts = self._budget_fill(raw, context_level, query=query)

        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level,
            health=self.health().to_dict(),
            relevant_concepts=relevant_concepts,
        )


__all__ = ["LogThreadAdapter"]
