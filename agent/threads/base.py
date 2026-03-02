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
    # Thread metadata for STATE block
    thread_name: str = ""
    thread_description: str = ""
    relevance_score: float = 0.0
    fact_scores: Dict[str, float] = field(default_factory=dict)  # fact -> score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON/aggregation."""
        return {
            "facts": self.facts,
            "state": self.state,
            "context_level": self.context_level,
            "health": self.health,
            "relevant_concepts": self.relevant_concepts,
            "fact_count": len(self.facts),
            "thread_name": self.thread_name,
            "thread_description": self.thread_description,
            "relevance_score": self.relevance_score,
            "fact_scores": self.fact_scores,
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

    # Per-level token budgets — threads can override
    _token_budgets: Dict[int, int] = {1: 150, 2: 400, 3: 800}
    
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

    def sync(self) -> None:
        """Periodic sync hook called by SyncLoop.

        Base implementation updates the last-sync timestamp.
        Subclasses can override to persist pending state, reconcile
        conflicts, or run deferred maintenance.
        """
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
    # BUDGET-AWARE FACT PACKING
    # =========================================================================

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~1.3 tokens per whitespace-separated word."""
        return max(1, int(len(text.split()) * 1.3))

    def _budget_fill(
        self,
        raw_facts: List[Dict[str, Any]],
        level: int,
        token_budget: int = 0,
    ) -> List[str]:
        """Pack facts into a token budget at varying detail levels.

        Each *raw_fact* dict must contain:
            path  – dot-notation prefix  (e.g. "identity.nola.name")
            l1_value, l2_value, l3_value – value at each tier
            weight – 0-1 importance

        Algorithm (greedy, O(n)):
            1. Sort by weight descending (most important first).
            2. For each fact, try the *requested* level value.
            3. If that would blow the remaining budget, try L1 instead.
            4. If even L1 won't fit, skip the fact.

        Returns a list of formatted "path: value" strings.
        """
        budget = token_budget or self._token_budgets.get(level, 400)
        used = 0
        result: List[str] = []

        # Sort by weight descending — highest-value facts first
        sorted_facts = sorted(raw_facts, key=lambda f: f.get("weight", 0.5), reverse=True)

        for fact in sorted_facts:
            path = fact.get("path", "")
            l1 = fact.get("l1_value") or ""
            l2 = fact.get("l2_value") or ""
            l3 = fact.get("l3_value") or ""

            # Pick value at requested level (with fallbacks)
            if level >= 3:
                preferred = l3 or l2 or l1
            elif level >= 2:
                preferred = l2 or l1 or l3
            else:
                preferred = l1 or l2 or l3

            lean = l1 or l2 or l3  # always the shortest version

            if not preferred:
                continue

            line = f"{path}: {preferred}"
            cost = self._estimate_tokens(line)

            if used + cost <= budget:
                result.append(line)
                used += cost
                continue

            # Preferred blows the budget — try lean version if different
            if lean and lean != preferred:
                lean_line = f"{path}: {lean}"
                lean_cost = self._estimate_tokens(lean_line)
                if used + lean_cost <= budget:
                    result.append(lean_line)
                    used += lean_cost
                    continue

            # Even lean doesn't fit — we're done (facts are sorted, rest are less important)
            break

        return result

    def _relevance_boost(
        self,
        raw_facts: List[Dict[str, Any]],
        query: str,
    ) -> tuple:
        """Boost weights of query-relevant facts so _budget_fill prioritises them.

        Uses LinkingCore spread_activate to find concepts related to the
        query, then bumps the weight of any raw_fact whose path / values
        mention one of those concepts.

        Returns (raw_facts, relevant_concepts).
        Falls back to (raw_facts, []) if LinkingCore is unavailable.
        """
        try:
            from agent.threads.linking_core.schema import (
                spread_activate,
                extract_concepts_from_text,
            )

            query_concepts = extract_concepts_from_text(query)
            if not query_concepts:
                return raw_facts, []

            activated = spread_activate(
                input_concepts=query_concepts,
                activation_threshold=0.1,
                max_hops=1,
                limit=20,
            )
            relevant = set(query_concepts)
            for a in activated:
                relevant.add(a.get("concept", ""))

            for fact in raw_facts:
                text = (
                    f"{fact.get('path', '')} {fact.get('key', '')} "
                    f"{fact.get('l1_value', '')} {fact.get('l2_value', '')}"
                ).lower()
                for concept in relevant:
                    if concept.lower() in text:
                        fact["weight"] = min(1.0, fact.get("weight", 0.5) + 0.3)
                        break

            return raw_facts, list(relevant)
        except Exception:
            return raw_facts, []

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
            from agent.threads.linking_core.schema import (
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
            query: The feeds to score against
            context: Optional dict (unused, for backward compatibility)
        
        Returns:
            Score from 0.0 to 10.0
        """
        try:
            from agent.threads import get_thread
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
