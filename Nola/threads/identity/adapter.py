"""
Identity Thread Adapter
=======================

Provides self-awareness and user recognition to Nola.

This thread answers: "Who am I? Who are you?"

Now uses identity_flat table with L1/L2/L3 columns for HEA-native storage.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Import base adapter
try:
    from Nola.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from Nola.threads.schema import (
        pull_identity_flat,
        push_identity_row,
        get_identity_context,
        get_identity_table_data,
    )
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from ..schema import (
        pull_identity_flat,
        push_identity_row,
        get_identity_context,
        get_identity_table_data,
    )

# Training data logging (append-only learning)
try:
    from Nola.training import log_identity_decision
    HAS_TRAINING_LOGGER = True
except ImportError:
    HAS_TRAINING_LOGGER = False
    def log_identity_decision(*args, **kwargs): return False


class IdentityThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for identity — who am I, who are you.
    
    Uses identity_flat table with L1/L2/L3 columns.
    Each row has different detail levels built-in.
    """
    
    _name = "identity"
    _description = "Self-awareness and user recognition"
    
    def get_data(self, level: int = 2, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """
        Get identity data at specified HEA level.
        
        Returns list of {key, metadata_type, metadata_desc, value, weight}
        where 'value' is L1, L2, or L3 content based on level.
        """
        rows = pull_identity_flat(level=level, min_weight=min_weight, limit=limit)
        return rows
    
    def get_table_data(self) -> List[Dict]:
        """
        Get all identity rows with full L1/L2/L3 for table display.
        
        Returns list of {key, metadata_type, metadata_desc, l1, l2, l3, weight}
        """
        return get_identity_table_data()
    
    def get_context_string(self, level: int = 2, token_budget: int = 500) -> str:
        """
        Get identity context formatted for agent prompt.
        
        Returns string like:
        - agent_name: Nola
        - user_name: Jordan
        - ...
        """
        return get_identity_context(level=level, token_budget=token_budget)
    
    def set_fact(
        self,
        key: str,
        l1: str,
        l2: str,
        l3: str,
        metadata_type: str = "fact",
        metadata_desc: str = "",
        weight: float = 0.5
    ) -> None:
        """Set an identity fact with all three HEA levels."""
        push_identity_row(
            key=key,
            l1=l1,
            l2=l2,
            l3=l3,
            metadata_type=metadata_type,
            metadata_desc=metadata_desc,
            weight=weight
        )
    
    def introspect(self, context_level: int = 2) -> IntrospectionResult:
        """
        Identity introspection with structured output.
        
        Returns facts at the requested HEA level.
        """
        rows = self.get_data(level=context_level)
        facts = [f"{row['key']}: {row['value']}" for row in rows]
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level
        )
    
    def health(self) -> HealthReport:
        """Check identity thread health."""
        try:
            rows = pull_identity_flat(level=2)
            row_count = len(rows)
            
            if row_count == 0:
                return HealthReport.degraded(
                    "No identity data found",
                    row_count=0
                )
            
            return HealthReport.ok(
                f"{row_count} facts",
                row_count=row_count
            )
        except Exception as e:
            return HealthReport.error(str(e))
    
    def score_relevance(self, fact: str, context: Dict[str, Any] = None) -> float:
        """
        Score a fact by goal/value relevance (PFC function).
        
        High score if fact mentions:
        - Active project
        - User's stated goals
        - User's core values/preferences
        
        If confidence is high, logs training example (append-only learning).
        """
        if not context:
            return 0.5
        
        score = 0.5
        fact_lower = fact.lower()
        
        # Check active project match
        active_project = context.get('active_project', '')
        if active_project and active_project.lower() in fact_lower:
            score += 0.3
        
        # Check query relevance
        query = context.get('query', '')
        if query:
            query_words = set(query.lower().split())
            fact_words = set(fact_lower.split())
            overlap = len(query_words & fact_words)
            if overlap > 0:
                score += min(overlap * 0.1, 0.3)
        
        # Check goal keywords
        goal_keywords = context.get('goal_keywords', [])
        for kw in goal_keywords:
            if kw.lower() in fact_lower:
                score += 0.15
        
        final_score = min(score, 1.0)
        
        # Log confident retrieval decisions for training
        if HAS_TRAINING_LOGGER and final_score >= 0.7 and query:
            log_identity_decision(
                input_text=query,
                output_text=fact,
                decision_type="retrieval",
                confidence=final_score,
                active_project=active_project,
                overlap_words=overlap if query else 0
            )
        
        return final_score
    
    # Legacy compatibility - map old module-based calls to flat table
    def get_module_data(self, module: str, level: int = 2) -> List[Dict]:
        """Legacy: Get data filtered by old module structure."""
        # Map old modules to key prefixes
        prefix_map = {
            "user_profile": ["user_"],
            "nola_self": ["agent_", "comm_"],
            "machine_context": ["machine_"],
        }
        prefixes = prefix_map.get(module, [])
        
        rows = self.get_data(level=level)
        if not prefixes:
            return rows
        
        filtered = []
        for row in rows:
            if any(row['key'].startswith(p) for p in prefixes):
                # Convert to old format
                filtered.append({
                    "key": row['key'],
                    "metadata": {"type": row.get('metadata_type'), "description": row.get('metadata_desc')},
                    "data": {"value": row['value']},
                    "level": level,
                    "weight": row['weight']
                })
        return filtered


__all__ = ["IdentityThreadAdapter"]
