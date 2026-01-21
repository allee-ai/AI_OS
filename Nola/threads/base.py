"""
Base Thread Adapter
===================

Universal base class for all thread adapters.
Each thread has its own schema.py with dedicated tables/storage.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum


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
    """
    Result of introspecting a thread.
    
    Each thread builds its own contribution to the STATE block.
    """
    facts: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    context_level: int = 2
    health: Optional[Dict[str, Any]] = None
    relevant_concepts: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON/aggregation."""
        return {
            "facts": self.facts,
            "state": self.state,
            "context_level": self.context_level,
            "health": self.health,
            "relevant_concepts": self.relevant_concepts,
            "fact_count": len(self.facts),
        }


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
    # UNIVERSAL INTERFACE - override in subclass with thread-specific schema
    # =========================================================================
    
    def get_modules(self) -> List[str]:
        """List modules in this thread. Override in subclass."""
        return []
    
    def get_data(self, level: int = 2, limit: int = 50) -> List[Dict]:
        """
        Pull all data from this thread at given level.
        Override in subclass with thread-specific implementation.
        
        Returns flat list of items from all modules.
        """
        return []
    
    def get_module_data(self, module: str, level: int = 2, limit: int = 50) -> List[Dict]:
        """Pull data from a specific module. Override in subclass."""
        return []
    
    def push(
        self,
        module: str,
        key: str,
        metadata: Dict[str, Any],
        data: Dict[str, Any],
        level: int = 2,
        weight: float = 0.5
    ) -> None:
        """Push a row to a module. Override in subclass."""
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
    
    def introspect(self, context_level: int = 2, query: str = None) -> IntrospectionResult:
        """
        Introspect this thread for context assembly.
        
        Each thread is responsible for building its own STATE block contribution.
        If query is provided, uses LinkingCore to filter to relevant facts.
        
        Args:
            context_level: HEA level (1=minimal, 2=moderate, 3=full)
            query: Optional input text to filter relevance
        
        Returns:
            IntrospectionResult with facts, state, health, and relevant concepts
        """
        facts = []
        relevant_concepts = []
        
        try:
            # Get raw items from this thread
            items = self.get_data(level=context_level)
            
            # If query provided, filter by relevance using LinkingCore
            if query:
                items, relevant_concepts = self._filter_by_relevance(items, query, context_level)
            
            # Convert to fact strings
            for item in items:
                key = item.get("key", "")
                data = item.get("data", {})
                value = data.get("value", str(data)) if isinstance(data, dict) else str(data)
                
                if key and value:
                    facts.append(f"{key}: {value}")
                    
        except Exception as e:
            facts.append(f"[{self._name} error: {e}]")
        
        # Include health in the result
        health_report = self.health()
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level,
            health=health_report.to_dict(),
            relevant_concepts=relevant_concepts,
        )
    
    def _filter_by_relevance(
        self, 
        items: List[Dict], 
        query: str, 
        level: int
    ) -> tuple[List[Dict], List[str]]:
        """
        Filter items by relevance to query using LinkingCore.
        
        Returns (filtered_items, relevant_concepts)
        """
        try:
            from Nola.threads.linking_core.schema import (
                spread_activate, 
                extract_concepts_from_text
            )
            
            # Extract concepts from query
            query_concepts = extract_concepts_from_text(query)
            if not query_concepts:
                return items, []
            
            # Spread activation to find related concepts
            activated = spread_activate(
                input_concepts=query_concepts,
                activation_threshold=0.1,
                max_hops=1,
                limit=20
            )
            
            # Build set of relevant concepts
            relevant = set(query_concepts)
            for a in activated:
                relevant.add(a.get("concept", ""))
            
            # Filter items that match relevant concepts
            filtered = []
            for item in items:
                key = item.get("key", "").lower()
                data = item.get("data", {})
                value = str(data.get("value", data)).lower() if isinstance(data, dict) else str(data).lower()
                
                # Check if any relevant concept appears in the item
                item_text = f"{key} {value}"
                for concept in relevant:
                    if concept.lower() in item_text:
                        filtered.append(item)
                        break
            
            # Return filtered (or all if no matches) + the concepts found
            return (filtered if filtered else items[:10], list(relevant))
            
        except Exception:
            # If linking_core unavailable, return all items
            return items, []
    
    def get_context(self, level: int = 2, query: str = None) -> List[str]:
        """Get facts as strings for context assembly."""
        result = self.introspect(level, query=query)
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
    
    def score_thread_relevance(self, query: str, context: Dict[str, Any] = None) -> float:
        """
        Score this thread's overall relevance to a query for sparse activation.
        
        NOTE: Delegates to linking_core.score_threads().
        Individual threads should NOT override this.
        
        Used for three-tier context gating:
          - Score 0-3.5: Tier 1 (Metadata only)
          - Score 3.5-7: Tier 2 (Profile metadata)
          - Score 7-10: Tier 3 (Full facts with L1/L2/L3)
        
        Args:
            query: The stimuli to score against
            context: Optional dict (unused, for backward compatibility)
        
        Returns:
            Score from 0.0 to 10.0
        """
        try:
            from Nola.threads import get_thread
            linking_core = get_thread('linking_core')
            if linking_core:
                scores = linking_core.score_threads(query)
                return scores.get(self._name, 5.0)
        except:
            pass
        
        return 5.0
    
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
