"""
Subconscious Orchestrator
=========================

The orchestrator that builds STATE + CONTEXT blocks from all threads.
Uses the new schema.py for data access and LinkingCore for scoring.

Usage:
    from Nola.subconscious.orchestrator import Subconscious
    
    sub = Subconscious()
    context = sub.build_context(level=2, query="Tell me about yourself")
    # Returns: {"state": {...}, "context": [...]}

This replaces:
- Nola.json for runtime state
- identity.sync_for_stimuli()
- ContextManager in agent_service.py
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import json

# Import schema functions
try:
    from Nola.threads.schema import (
        pull_from_module,
        pull_all_thread_data,
        push_to_module,
        get_registered_modules,
        get_thread_summary,
        bootstrap_threads,
    )
except ImportError:
    # Fallback for relative imports
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from threads.schema import (
        pull_from_module,
        pull_all_thread_data,
        push_to_module,
        get_registered_modules,
        get_thread_summary,
        bootstrap_threads,
    )

# Import LinkingCore
try:
    from Nola.threads.linking_core import score_relevance, rank_items
except ImportError:
    from threads.linking_core import score_relevance, rank_items


# HEA Level limits: items per module
LEVEL_LIMITS = {
    1: 2,   # L1: top 2 per module
    2: 5,   # L2: top 5 per module
    3: 10,  # L3: top 10 per module
}

# Thread list
THREADS = ["identity", "log", "form", "philosophy", "reflex"]


class Subconscious:
    """
    The orchestrator that builds context from all threads.
    
    Responsibilities:
    - Pull data from all threads at given level
    - Score and rank items using LinkingCore
    - Build STATE block (metadata) + CONTEXT block (facts)
    - Record interactions to log thread
    """
    
    def __init__(self):
        self._last_context_time: Optional[str] = None
        self._last_query: Optional[str] = None
    
    def build_context(
        self,
        level: int = 2,
        query: str = "",
        threads: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build STATE + CONTEXT blocks from all threads.
        
        Args:
            level: Context level (1=minimal, 2=standard, 3=full)
            query: User's message for relevance scoring
            threads: Which threads to pull from (default: all)
        
        Returns:
            {
                "state": {thread: metadata...},
                "context": [{"key": ..., "value": ..., "source": ...}, ...],
                "meta": {"level": N, "total_items": N, ...}
            }
        """
        level = max(1, min(3, level))  # Clamp to 1-3
        threads = threads or THREADS
        limit_per_module = LEVEL_LIMITS.get(level, 5)
        
        # Pull data from all threads
        all_data = {}
        for thread in threads:
            thread_data = pull_all_thread_data(thread, level)
            if thread_data:
                all_data[thread] = thread_data
        
        # Build STATE block (metadata from each thread)
        state = self._build_state_block(all_data)
        
        # Flatten all items for scoring
        flat_items = self._flatten_items(all_data)
        
        # Score and rank
        if query and flat_items:
            ranked = rank_items(flat_items, query, threshold=0.0, limit=limit_per_module * len(THREADS) * 3)
        else:
            # No query = use weights only
            ranked = sorted(flat_items, key=lambda x: x.get("weight", 0.5), reverse=True)
        
        # Build CONTEXT block (top items per thread)
        context = self._build_context_block(ranked, limit_per_module)
        
        # Track timing
        self._last_context_time = datetime.now(timezone.utc).isoformat()
        self._last_query = query
        
        return {
            "state": state,
            "context": context,
            "meta": {
                "level": level,
                "total_items": len(flat_items),
                "context_items": len(context),
                "threads_queried": threads,
                "timestamp": self._last_context_time,
            }
        }
    
    def _build_state_block(self, all_data: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Build the STATE block from thread metadata.
        
        STATE tells the agent what threads exist and their status.
        """
        state = {}
        
        for thread, modules in all_data.items():
            module_summaries = {}
            for module_name, rows in modules.items():
                module_summaries[module_name] = {
                    "count": len(rows),
                    "keys": [r.get("key") for r in rows[:5]],  # First 5 keys
                }
            
            state[thread] = {
                "modules": list(modules.keys()),
                "module_details": module_summaries,
                "total_items": sum(len(rows) for rows in modules.values()),
            }
        
        return state
    
    def _flatten_items(self, all_data: Dict[str, Dict]) -> List[Dict]:
        """
        Flatten nested thread→module→rows structure into flat list.
        
        Adds thread/module source info to each item.
        """
        flat = []
        
        for thread, modules in all_data.items():
            for module_name, rows in modules.items():
                for row in rows:
                    flat.append({
                        **row,
                        "thread": thread,
                        "module": module_name,
                    })
        
        return flat
    
    def _build_context_block(
        self,
        ranked_items: List[Dict],
        limit_per_module: int
    ) -> List[Dict[str, Any]]:
        """
        Build the CONTEXT block from ranked items.
        
        CONTEXT is the actual facts the agent can use.
        Respects per-module limits for balance.
        """
        # Track counts per thread/module
        counts: Dict[str, int] = {}
        context = []
        
        for item in ranked_items:
            thread = item.get("thread", "unknown")
            module = item.get("module", "unknown")
            source_key = f"{thread}.{module}"
            
            # Check limit
            current_count = counts.get(source_key, 0)
            if current_count >= limit_per_module:
                continue
            
            # Extract value
            data = item.get("data", {})
            if isinstance(data, dict):
                value = data.get("value", data.get("fact", str(data)))
            else:
                value = str(data)
            
            context.append({
                "key": item.get("key", ""),
                "value": value,
                "source": source_key,
                "weight": item.get("weight", 0.5),
                "score": item.get("score", item.get("weight", 0.5)),
            })
            
            counts[source_key] = current_count + 1
        
        return context
    
    def record_interaction(
        self,
        user_message: str,
        agent_response: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Record an interaction to the log thread.
        
        Args:
            user_message: What the user said
            agent_response: What the agent replied
            metadata: Optional extra data (stimuli_type, etc.)
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Push to log.sessions
        push_to_module(
            thread_name="log",
            module_name="sessions",
            key=f"msg_{timestamp}",
            metadata={
                "type": "interaction",
                "timestamp": timestamp,
                **(metadata or {}),
            },
            data={
                "user": user_message[:500],  # Truncate long messages
                "agent": agent_response[:500],
            },
            level=3,  # Full context only
            weight=0.3,
        )
    
    def get_identity_facts(self, level: int = 2) -> List[str]:
        """
        Get identity facts as simple strings.
        
        Convenience method for backwards compatibility.
        """
        ctx = self.build_context(level=level, threads=["identity"])
        facts = []
        for item in ctx.get("context", []):
            key = item.get("key", "")
            value = item.get("value", "")
            if key and value:
                facts.append(f"{key}: {value}")
        return facts
    
    def consolidate(self) -> Dict[str, int]:
        """
        Run consolidation: analyze access patterns and adjust levels/weights.
        
        Frequently accessed L3 items → promote to L2
        Stale L2 items → demote to L3
        
        Returns counts of promotions/demotions.
        """
        # TODO: Implement consolidation logic
        # For now, just return stats
        return {"promoted": 0, "demoted": 0, "analyzed": 0}


# Singleton instance
_SUBCONSCIOUS: Optional[Subconscious] = None


def get_subconscious() -> Subconscious:
    """Get the singleton Subconscious instance."""
    global _SUBCONSCIOUS
    if _SUBCONSCIOUS is None:
        _SUBCONSCIOUS = Subconscious()
    return _SUBCONSCIOUS


def build_context(level: int = 2, query: str = "", threads: Optional[List[str]] = None) -> Dict[str, Any]:
    """Convenience function to build context."""
    return get_subconscious().build_context(level, query, threads)


def record_interaction(user_msg: str, agent_resp: str, meta: Optional[Dict] = None) -> None:
    """Convenience function to record interaction."""
    get_subconscious().record_interaction(user_msg, agent_resp, meta)
