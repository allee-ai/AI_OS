"""
Philosophy Thread Adapter
=========================

Provides values, reasoning frameworks, and ethical bounds to Nola.

This thread answers: "What do I believe? How should I think? What must I not do?"

Modules:
- core_values: Fundamental values and principles
- ethical_bounds: Hard constraints on behavior
- reasoning_style: How to approach problems
"""

from typing import List, Dict, Any
from datetime import datetime, timezone

try:
    from Nola.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from Nola.threads.schema import pull_philosophy_flat, get_philosophy_table_data
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from ..schema import pull_philosophy_flat, get_philosophy_table_data


class PhilosophyThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for values, reasoning, and ethical constraints.
    
    Uses schema.py for all data access:
    - philosophy_core_values: What I believe
    - philosophy_ethical_bounds: What I must not do
    - philosophy_reasoning_style: How I think
    """
    
    _name = "philosophy"
    _description = "Values, reasoning frameworks, and ethical bounds"
    
    def get_data(self, level: int = 2, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """
        Get philosophy data at specified HEA level.
        
        Returns list of {key, metadata_type, metadata_desc, value, weight}
        where 'value' is L1, L2, or L3 content based on level.
        """
        rows = pull_philosophy_flat(level=level, min_weight=min_weight, limit=limit)
        return rows
    
    def get_table_data(self) -> List[Dict]:
        """
        Get all philosophy rows with full L1/L2/L3 for table display.
        
        Returns list of {key, metadata_type, metadata_desc, l1, l2, l3, weight}
        """
        return get_philosophy_table_data()
    
    def health(self) -> HealthReport:
        """Check philosophy thread health."""
        try:
            rows = pull_philosophy_flat(level=2)
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
        """Get core values."""
        return self.get_module_data("core_values", level)
    
    def get_ethical_bounds(self, level: int = 2) -> List[Dict]:
        """Get ethical bounds."""
        return self.get_module_data("ethical_bounds", level)
    
    def get_reasoning_style(self, level: int = 2) -> List[Dict]:
        """Get reasoning style."""
        return self.get_module_data("reasoning_style", level)
    
    def add_value(
        self,
        key: str,
        value: str,
        description: str = "",
        weight: float = 0.8
    ) -> None:
        """Add a core value."""
        self.push(
            module="core_values",
            key=key,
            metadata={"type": "value", "description": description or f"Core value: {key}"},
            data={"value": value},
            level=1,
            weight=weight
        )
    
    def add_bound(
        self,
        key: str,
        constraint: str,
        weight: float = 1.0
    ) -> None:
        """Add an ethical bound (hard constraint)."""
        self.push(
            module="ethical_bounds",
            key=key,
            metadata={"type": "constraint", "description": f"Ethical bound: {key}"},
            data={"value": constraint},
            level=1,
            weight=weight
        )
    
    def introspect(self, context_level: int = 2) -> IntrospectionResult:
        """
        Philosophy introspection with values and constraints.
        
        Returns facts like:
        - "I value: helpfulness, honesty, transparency"
        - "I must not: cause harm, deceive users"
        - "My approach: step-by-step reasoning"
        """
        facts = []
        
        # Core values (L1+)
        values = self.get_core_values(context_level)
        value_names = []
        for v in values:
            key = v.get("key", "")
            if key:
                value_names.append(key.replace("_", " "))
        
        if value_names:
            facts.append(f"I value: {', '.join(value_names)}")
        
        # Ethical bounds (L1+)
        bounds = self.get_ethical_bounds(context_level)
        bound_strs = []
        for b in bounds:
            key = b.get("key", "")
            data = b.get("data", {})
            value = data.get("value", "")
            if value:
                bound_strs.append(value[:50])
        
        if bound_strs:
            facts.append(f"Constraints: {'; '.join(bound_strs)}")
        
        # Reasoning style (L2+)
        if context_level >= 2:
            style = self.get_reasoning_style(context_level)
            for s in style:
                data = s.get("data", {})
                value = data.get("value", "")
                if value:
                    facts.append(f"Approach: {value}")
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level
        )


__all__ = ["PhilosophyThreadAdapter"]
