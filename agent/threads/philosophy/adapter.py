"""
Philosophy Thread Adapter
=========================

Provides values, reasoning frameworks, and ethical bounds to Agent.

This thread answers: "What do I believe? How should I think? What must I not do?"

Modules:
- core_values: Fundamental values and principles
- ethical_bounds: Hard constraints on behavior
- reasoning_style: How to approach problems
"""

from typing import List, Dict, Any
from datetime import datetime, timezone

try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from agent.threads.philosophy.schema import (
        pull_philosophy_profile_facts,
        get_philosophy_profiles,
    )
    from agent.threads.linking_core.schema import extract_concepts_from_text
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from .schema import (
        pull_philosophy_profile_facts,
        get_philosophy_profiles,
    )
    from ..linking_core.schema import extract_concepts_from_text


class PhilosophyThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for values, reasoning, and ethical constraints.
    
    Uses profile-based schema for all data access:
    - philosophy_profile_types: Category definitions
    - philosophy_profiles: Profile instances (agent.core, agent.ethics, etc.)
    - philosophy_profile_facts: Individual facts with L1/L2/L3
    """
    
    _name = "philosophy"
    _description = "Values, reasoning frameworks, and ethical bounds"
    
    def get_data(self, level: int = 2, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """
        Get philosophy data at specified HEA level.
        
        Returns list of {key, fact_type, l1_value, l2_value, l3_value, weight}
        """
        rows = pull_philosophy_profile_facts(min_weight=min_weight, limit=limit)
        return rows
    
    def get_table_data(self) -> List[Dict]:
        """
        Get all philosophy rows with full L1/L2/L3 for table display.
        """
        return pull_philosophy_profile_facts(limit=200)
    
    def health(self) -> HealthReport:
        """Check philosophy thread health."""
        try:
            rows = pull_philosophy_profile_facts()
            row_count = len(rows)
            
            if row_count == 0:
                return HealthReport.degraded(
                    "No philosophy data found",
                    row_count=0
                )
            
            return HealthReport.ok(
                f"{row_count} principles",
                row_count=row_count
            )
        except Exception as e:
            return HealthReport.error(str(e))
    
    def get_core_values(self, level: int = 2) -> List[Dict]:
        """Get core values from profiles with 'value' in fact_type."""
        all_facts = pull_philosophy_profile_facts()
        return [f for f in all_facts if 'value' in (f.get('fact_type') or '').lower()]
    
    def get_ethical_bounds(self, level: int = 2) -> List[Dict]:
        """Get ethical bounds from profiles with 'bound' or 'constraint' in fact_type."""
        all_facts = pull_philosophy_profile_facts()
        return [f for f in all_facts if any(x in (f.get('fact_type') or '').lower() for x in ['bound', 'constraint', 'ethic'])]
    
    def get_reasoning_style(self, level: int = 2) -> List[Dict]:
        """Get reasoning style facts."""
        all_facts = pull_philosophy_profile_facts()
        return [f for f in all_facts if any(x in (f.get('fact_type') or '').lower() for x in ['reasoning', 'style', 'approach'])]
    
    def _filter_by_relevance(self, facts: List[Dict], query: str, top_k: int = 10) -> List[Dict]:
        """Filter facts by relevance to query using linking_core concepts."""
        if not query or not facts:
            return facts[:top_k]
        
        try:
            query_concepts = extract_concepts_from_text(query)
            if not query_concepts:
                return facts[:top_k]
            
            query_concept_set = set(query_concepts)
            scored = []
            
            for fact in facts:
                # Extract concepts from fact content
                fact_text = f"{fact.get('key', '')} {fact.get('l2_value', '')} {fact.get('l3_value', '')}"
                fact_concepts = extract_concepts_from_text(fact_text)
                
                # Score by concept overlap
                overlap = len(set(fact_concepts) & query_concept_set)
                scored.append((overlap, fact))
            
            scored.sort(key=lambda x: x[0], reverse=True)
            return [f for _, f in scored[:top_k]]
            
        except Exception:
            return facts[:top_k]
    
    def introspect(self, context_level: int = 2, query: str = None, threshold: float = 0.0) -> IntrospectionResult:
        """
        Philosophy introspection with values and constraints.
        
        Args:
            context_level: HEA level (1=lean, 2=medium, 3=full)
            query: Optional query for relevance filtering
            threshold: Minimum weight for facts to be included (0-10 scale)
        
        Returns:
            IntrospectionResult with facts like:
                "philosophy.core.honesty.value: always direct"
                "philosophy.core.honesty.weight: 9.5"
        """
        facts = []
        relevant_concepts = []
        
        # Convert 0-10 threshold to 0-1 weight scale
        min_weight = threshold / 10.0
        
        # Get all philosophy facts
        all_facts = pull_philosophy_profile_facts()
        
        # Filter by weight threshold
        all_facts = [f for f in all_facts if f.get('weight', 0.5) >= min_weight]
        
        # Filter by relevance if query provided
        if query:
            all_facts = self._filter_by_relevance(all_facts, query)
            try:
                relevant_concepts = extract_concepts_from_text(query)
            except Exception:
                pass
        
        # Get level-appropriate value column
        level_col = {1: 'l1_value', 2: 'l2_value', 3: 'l3_value'}.get(context_level, 'l2_value')
        
        # Build facts with dot notation
        for f in all_facts:
            key = f.get('key', 'unknown')
            value = f.get(level_col) or f.get('l2_value', '')
            weight = f.get('weight', 0.5)
            fact_type = (f.get('fact_type') or 'general').lower().replace(' ', '_')
            profile_id = f.get('profile_id', 'agent.core')
            
            # Build path: philosophy.{profile_short}.{key}
            profile_parts = profile_id.split('.')
            profile_short = profile_parts[1] if len(profile_parts) >= 2 else profile_id
            
            if value:
                path = f"philosophy.{profile_short}.{key}"
                facts.append(f"{path}.value: {value}")
                facts.append(f"{path}.weight: {weight}")
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level,
            health=self.health().to_dict(),
            relevant_concepts=relevant_concepts
        )


__all__ = ["PhilosophyThreadAdapter"]
