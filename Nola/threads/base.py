"""
Base Thread Adapter
===================

Universal base class for all thread adapters.
All adapters inherit from this and use schema.py for data access.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

# Import schema functions
try:
    from Nola.threads.schema import (
        pull_from_module,
        pull_all_thread_data,
        push_to_module,
        get_registered_modules,
    )
except ImportError:
    from ..schema import (
        pull_from_module,
        pull_all_thread_data,
        push_to_module,
        get_registered_modules,
    )


class ThreadStatus(Enum):
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class HealthReport:
    """Health status for a thread."""
    status: ThreadStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def ok(cls, msg: str = "", **details) -> "HealthReport":
        return cls(ThreadStatus.OK, msg, details)
    
    @classmethod
    def degraded(cls, msg: str, **details) -> "HealthReport":
        return cls(ThreadStatus.DEGRADED, msg, details)
    
    @classmethod
    def error(cls, msg: str, **details) -> "HealthReport":
        return cls(ThreadStatus.ERROR, msg, details)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "message": self.message,
            "details": self.details
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "message": self.message,
            "details": self.details
        }


@dataclass
class IntrospectionResult:
    """Result of introspecting a thread."""
    facts: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    context_level: int = 2


class BaseThreadAdapter:
    """
    Base class for all thread adapters.
    
    Subclasses should set:
        _name: str - Thread name (identity, log, etc.)
        _description: str - Human-readable description
    
    Data access is via schema.py functions:
        pull_from_module() - Read rows
        push_to_module() - Write rows
        pull_all_thread_data() - Read all modules
    """
    
    _name: str = "base"
    _description: str = "Base thread adapter"
    
    def __init__(self):
        self._last_sync: Optional[str] = None
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def purpose(self) -> str:
        return self._description
    
    # =========================================================================
    # UNIVERSAL INTERFACE - use schema.py
    # =========================================================================
    
    def get_modules(self) -> List[str]:
        """List modules in this thread from DB."""
        modules = get_registered_modules(self._name)
        return [m["module_name"] for m in modules]
    
    def get_data(self, level: int = 2, limit: int = 50) -> List[Dict]:
        """
        Pull all data from this thread at given level.
        
        Returns flat list of items from all modules.
        """
        all_data = pull_all_thread_data(self._name, level)
        
        flat = []
        for module_name, rows in all_data.items():
            for row in rows[:limit]:
                flat.append({
                    **row,
                    "module": module_name,
                })
        
        return flat
    
    def get_module_data(self, module: str, level: int = 2, limit: int = 50) -> List[Dict]:
        """Pull data from a specific module."""
        return pull_from_module(self._name, module, level, limit)
    
    def push(
        self,
        module: str,
        key: str,
        metadata: Dict[str, Any],
        data: Dict[str, Any],
        level: int = 2,
        weight: float = 0.5
    ) -> None:
        """Push a row to a module."""
        push_to_module(self._name, module, key, metadata, data, level, weight)
        self._last_sync = datetime.now(timezone.utc).isoformat()
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Thread-level metadata for STATE block.
        
        Subclasses can override to add custom metadata.
        """
        modules = self.get_modules()
        return {
            "name": self._name,
            "purpose": self._description,
            "status": "healthy",
            "last_sync": self._last_sync,
            "module_count": len(modules),
            "modules": modules,
        }
    
    # =========================================================================
    # HEALTH & INTROSPECTION
    # =========================================================================
    
    def health(self) -> HealthReport:
        """Check thread health."""
        try:
            modules = self.get_modules()
            if modules:
                return HealthReport.ok(
                    f"{self._name} thread healthy",
                    modules=modules
                )
            else:
                return HealthReport.degraded(
                    f"{self._name} has no registered modules"
                )
        except Exception as e:
            return HealthReport.error(f"Health check failed: {e}")
    
    def introspect(self, context_level: int = 2) -> IntrospectionResult:
        """
        Introspect this thread for context assembly.
        
        Returns facts as strings for the system prompt.
        """
        facts = []
        
        try:
            items = self.get_data(level=context_level)
            for item in items:
                key = item.get("key", "")
                data = item.get("data", {})
                value = data.get("value", str(data)) if isinstance(data, dict) else str(data)
                
                if key and value:
                    facts.append(f"{key}: {value}")
        except Exception as e:
            facts.append(f"[{self._name} error: {e}]")
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level
        )
    
    def get_context(self, level: int = 2) -> List[str]:
        """Get facts as strings for context assembly."""
        result = self.introspect(level)
        return result.facts
    
    # =========================================================================
    # RELEVANCE SCORING - Each thread implements its dimension
    # =========================================================================
    
    def score_relevance(self, fact: str, context: Dict[str, Any] = None) -> float:
        """
        Score a fact from this thread's cognitive perspective.
        
        Each thread scores differently:
          - Identity: Does this match user's goals/values? (PFC)
          - Log: How recent is this? (Hippocampus)
          - Form: Semantic similarity to query? (Temporal lobe)
          - Philosophy: Emotional salience? (Amygdala)
          - Reflex: How frequently accessed? (Basal Ganglia)
        
        Args:
            fact: The fact text to score
            context: Optional dict with 'query', 'active_project', etc.
        
        Returns:
            Score from 0.0 to 1.0
        
        Default implementation returns 0.5 (neutral).
        Subclasses should override with thread-specific logic.
        """
        return 0.5
    
    def get_score_explanation(self, fact: str, score: float, context: Dict[str, Any] = None) -> str:
        """
        Explain why this thread gave this score.
        
        For audit trail - shows reasoning behind the number.
        """
        return f"{self._name}: {score:.2f} (default scoring)"


# For backwards compatibility
ThreadInterface = BaseThreadAdapter

__all__ = [
    "BaseThreadAdapter",
    "ThreadInterface",
    "ThreadStatus",
    "HealthReport",
    "IntrospectionResult",
]
