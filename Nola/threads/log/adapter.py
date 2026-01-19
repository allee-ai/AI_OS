"""
Log Thread Adapter
==================

Provides temporal awareness and history to Nola.

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
    from Nola.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from Nola.threads.schema import pull_log_events
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from ..schema import pull_log_events

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
            events = pull_log_events(module_name="events", limit=10)
            sessions = pull_log_events(module_name="sessions", limit=10)
            total = len(events) + len(sessions)
            
            if total > 0:
                return HealthReport.ok(f"{total} log entries", row_count=total)
            else:
                return HealthReport.degraded("No log entries yet")
        except Exception as e:
            return HealthReport.error(f"Log health check failed: {e}")
    
    def introspect(self, context_level: int = 2) -> IntrospectionResult:
        """
        Log introspection with temporal awareness.
        
        Returns facts scaled by recency level.
        """
        facts = []
        
        # Session info
        duration = self.get_session_duration()
        if duration:
            if duration < 60:
                facts.append(f"Session duration: {int(duration)} seconds")
            elif duration < 3600:
                facts.append(f"Session duration: {int(duration/60)} minutes")
            else:
                facts.append(f"Session duration: {duration/3600:.1f} hours")
        
        if self._message_count > 0:
            facts.append(f"Messages this session: {self._message_count}")
        
        # Events based on recency level
        event_limit = LOG_LIMITS.get(context_level, 100) // 10  # Show 1/10th in introspect
        events = self.get_recent_events(event_limit)
        for evt in events[:5]:  # Cap display at 5
            data = evt.get("data", {})
            msg = data.get("message", "")
            if msg:
                facts.append(f"Event: {msg[:50]}")
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level
        )


__all__ = ["LogThreadAdapter"]
