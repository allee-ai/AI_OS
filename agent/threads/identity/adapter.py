"""
Identity Thread Adapter
=======================

Provides self-awareness and user recognition to Agent.

This thread answers: "Who am I? Who are you?"

Uses profile-based identity system with fact types.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Import base adapter
try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from agent.threads.identity.schema import (
        pull_profile_facts,
        push_profile_fact,
        get_profiles,
        get_value_by_weight,
    )
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from .schema import (
        pull_profile_facts,
        push_profile_fact,
        get_profiles,
        get_value_by_weight,
    )


class IdentityThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for identity — who am I, who are you.
    
    Uses profile-based fact storage with L1/L2/L3 value tiers.
    """
    
    _name = "identity"
    _description = "Self-awareness and user recognition"
    
    def get_data(self, level: int = 2, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """
        Get identity data at specified HEA level.
        
        Returns list of facts across all profiles.
        """
        # Get all profiles and collect their facts
        profiles = get_profiles()
        all_facts = []
        
        for profile in profiles:
            profile_id = profile.get("profile_id", "")
            facts = pull_profile_facts(profile_id=profile_id, min_weight=min_weight, limit=limit)
            for fact in facts[:limit]:
                # Get the appropriate value based on level
                value = get_value_by_weight(fact, fact.get("weight", 0.5))
                all_facts.append({
                    "key": fact.get("key", ""),
                    "value": value,
                    "weight": fact.get("weight", 0.5),
                    "profile_id": profile_id,
                    "fact_type": fact.get("fact_type", ""),
                })
        
        return all_facts[:limit]
    
    def get_context_string(self, level: int = 2, token_budget: int = 500) -> str:
        """
        Get identity context formatted for agent prompt.
        
        Returns string like:
        - agent_name: Agent
        - user_name: Jordan
        - ...
        """
        facts = self.get_data(level=level)
        lines = [f"- {f['key']}: {f['value']}" for f in facts]
        return "\n".join(lines[:20])  # Cap at 20 facts
    
    def set_fact(
        self,
        profile_id: str,
        key: str,
        l1_value: str = None,
        l2_value: str = None,
        l3_value: str = None,
        fact_type: str = "preference",
        weight: float = 0.5
    ) -> None:
        """Set an identity fact."""
        push_profile_fact(
            profile_id=profile_id,
            key=key,
            fact_type=fact_type,
            l1_value=l1_value,
            l2_value=l2_value,
            l3_value=l3_value,
            weight=weight
        )
    
    def introspect(self, context_level: int = 2, query: str = None, threshold: float = 0.0) -> IntrospectionResult:
        """
        Identity introspection with structured output.
        
        Returns facts at the requested HEA level, filtered by weight threshold.
        Facts are formatted with dot notation for addressability.
        
        Args:
            context_level: HEA level (1=lean, 2=medium, 3=full)
            query: Optional query for relevance filtering
            threshold: Minimum weight for facts to be included (0-10 scale)
        
        Returns:
            IntrospectionResult with facts like:
                "identity.agent.name.value: Nola"
                "identity.agent.name.weight: 10.0"
        """
        relevant_concepts = []
        
        # Convert 0-10 threshold to 0-1 weight scale
        min_weight = threshold / 10.0
        
        # Get raw data filtered by weight
        rows = self.get_data(level=context_level, min_weight=min_weight)
        
        # If query provided, filter by relevance
        if query:
            rows, relevant_concepts = self._filter_by_relevance(rows, query, context_level)
        
        # Format facts with dot notation
        facts = []
        for row in rows:
            profile_id = row.get('profile_id', 'unknown')
            key = row.get('key', 'unknown')
            value = row.get('value', '')
            weight = row.get('weight', 0.5)
            
            # Build dot notation path: identity.{profile}.{key}
            # profile_id is like "self.agent" or "user.primary"
            # We want: identity.agent.name or identity.user.name
            profile_parts = profile_id.split('.')
            if len(profile_parts) >= 2:
                profile_short = profile_parts[1]  # "agent" or "primary" -> "user"
                if profile_short == "primary":
                    profile_short = "user"
            else:
                profile_short = profile_id
            
            path = f"identity.{profile_short}.{key}"
            facts.append(f"{path}.value: {value}")
            facts.append(f"{path}.weight: {weight}")
        
        # Get health
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
    ) -> tuple:
        """Filter items by relevance to query using LinkingCore."""
        try:
            from agent.threads.linking_core.schema import (
                spread_activate, 
                extract_concepts_from_text
            )
            
            query_concepts = extract_concepts_from_text(query)
            if not query_concepts:
                return items, []
            
            activated = spread_activate(
                input_concepts=query_concepts,
                activation_threshold=0.1,
                max_hops=1,
                limit=20
            )
            
            relevant = set(query_concepts)
            for a in activated:
                relevant.add(a.get("concept", ""))
            
            # Filter items
            filtered = []
            for item in items:
                key = item.get("key", "").lower()
                value = str(item.get("value", "")).lower()
                item_text = f"{key} {value}"
                
                for concept in relevant:
                    if concept.lower() in item_text:
                        filtered.append(item)
                        break
            
            return (filtered if filtered else items[:10], list(relevant))
            
        except Exception:
            return items, []
    
    def health(self) -> HealthReport:
        """Check identity thread health."""
        try:
            rows = self.get_data(level=2)
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
        return final_score
    
    # Legacy compatibility - map old module-based calls to flat table
    def get_module_data(self, module: str, level: int = 2) -> List[Dict]:
        """Legacy: Get data filtered by old module structure."""
        # Map old modules to key prefixes
        prefix_map = {
            "user_profile": ["user_"],
            "aios_self": ["agent_", "comm_"],
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
