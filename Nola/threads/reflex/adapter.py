"""
Reflex Thread Adapter
=====================

Provides quick patterns, shortcuts, and triggers to Nola.

This thread answers: "What's my instant response? Is this a familiar pattern?"

Modules:
- greetings: Quick greeting patterns
- shortcuts: User-defined shortcuts
- system: System reflexes (resource management)
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import re

try:
    from Nola.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult


class ReflexThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for quick patterns and automatic responses.
    
    Uses schema.py for all data access:
    - reflex_greetings: Greeting responses
    - reflex_shortcuts: User shortcuts
    - reflex_system: System reflexes
    """
    
    _name = "reflex"
    _description = "Quick patterns, shortcuts, and triggers"
    
    def health(self) -> HealthReport:
        """Check reflex thread health."""
        try:
            # Reflex works even without data - it's ready to learn
            modules = self.get_modules()
            greetings = self.get_greetings(level=1)
            shortcuts = self.get_shortcuts(level=1)
            
            total_patterns = len(greetings) + len(shortcuts)
            
            if total_patterns > 0:
                return HealthReport.ok(
                    f"{total_patterns} patterns",
                    row_count=total_patterns
                )
            else:
                # Even with no patterns, reflex is ready
                return HealthReport.ok(
                    "Ready (no patterns yet)",
                    row_count=0
                )
        except Exception as e:
            return HealthReport.error(str(e))
    
    def get_greetings(self, level: int = 2) -> List[Dict]:
        """Get greeting patterns."""
        return self.get_module_data("greetings", level)
    
    def get_shortcuts(self, level: int = 2) -> List[Dict]:
        """Get user shortcuts."""
        return self.get_module_data("shortcuts", level)
    
    def get_system_reflexes(self, level: int = 2) -> List[Dict]:
        """Get system reflexes."""
        return self.get_module_data("system", level)
    
    def add_greeting(
        self,
        key: str,
        response: str,
        weight: float = 0.8
    ) -> None:
        """Add a greeting response."""
        self.push(
            module="greetings",
            key=key,
            metadata={"type": "pattern", "description": f"Greeting: {key}"},
            data={"value": response},
            level=1,
            weight=weight
        )
    
    def add_shortcut(
        self,
        trigger: str,
        response: str,
        description: str = ""
    ) -> None:
        """Add a user shortcut."""
        self.push(
            module="shortcuts",
            key=f"shortcut_{trigger.lower().replace(' ', '_')}",
            metadata={"type": "shortcut", "description": description or f"Shortcut: {trigger}"},
            data={"trigger": trigger, "response": response},
            level=1,
            weight=0.7
        )
    
    def match_greeting(self, text: str) -> Optional[str]:
        """
        Check if text matches a greeting pattern.
        
        Returns the response if matched, None otherwise.
        """
        text_lower = text.lower().strip()
        
        greetings = self.get_greetings(level=1)
        for g in greetings:
            key = g.get("key", "")
            data = g.get("data", {})
            response = data.get("value", "")
            
            # Simple keyword match
            if key in text_lower or text_lower.startswith(key):
                return response
        
        return None
    
    def match_shortcut(self, text: str) -> Optional[str]:
        """
        Check if text matches a shortcut.
        
        Returns the response if matched, None otherwise.
        """
        text_lower = text.lower().strip()
        
        shortcuts = self.get_shortcuts(level=1)
        for s in shortcuts:
            data = s.get("data", {})
            trigger = data.get("trigger", "").lower()
            response = data.get("response", "")
            
            if trigger and trigger in text_lower:
                return response
        
        return None
    
    def try_quick_response(self, text: str) -> Optional[str]:
        """
        Try to get a quick response for the input.
        
        Checks greetings and shortcuts.
        Returns response string or None if no match.
        """
        # Check shortcuts first (more specific)
        shortcut_resp = self.match_shortcut(text)
        if shortcut_resp:
            return shortcut_resp
        
        # Check greetings
        greeting_resp = self.match_greeting(text)
        if greeting_resp:
            return greeting_resp
        
        return None
    
    def introspect(self, context_level: int = 2) -> IntrospectionResult:
        """
        Reflex introspection with pattern awareness.
        
        Returns facts like:
        - "Quick responses: hello, goodbye, thanks"
        - "Shortcuts: /help, /status"
        """
        facts = []
        
        # Greetings (L1+)
        greetings = self.get_greetings(context_level)
        greeting_keys = [g.get("key", "") for g in greetings if g.get("key")]
        
        if greeting_keys:
            facts.append(f"Quick responses: {', '.join(greeting_keys[:5])}")
        
        # Shortcuts (L2+)
        if context_level >= 2:
            shortcuts = self.get_shortcuts(context_level)
            shortcut_triggers = []
            for s in shortcuts:
                data = s.get("data", {})
                trigger = data.get("trigger", "")
                if trigger:
                    shortcut_triggers.append(trigger)
            
            if shortcut_triggers:
                facts.append(f"Shortcuts: {', '.join(shortcut_triggers[:5])}")
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level
        )
    
    def score_relevance(self, fact: str, context: Dict[str, Any] = None) -> float:
        """
        Score a fact by access frequency (Basal Ganglia function).
        
        High score if fact has been accessed many times.
        This is habit/procedural memory - things we do often.
        """
        # Try to get access count from fact_relevance table
        try:
            from Nola.threads.schema import get_fact_relevance
            fact_key = fact[:50].strip()
            relevance = get_fact_relevance(fact_key)
            
            if relevance:
                access_count = relevance.get('access_count', 0)
                # Log scale: 1 access = 0.3, 10 = 0.6, 50 = 0.8, 100+ = 0.9
                import math
                if access_count > 0:
                    return min(0.3 + math.log(access_count + 1) * 0.15, 0.95)
        except Exception:
            pass
        
        return 0.3  # Low default - new facts haven't formed habits yet
    
    def get_score_explanation(self, fact: str, score: float, context: Dict[str, Any] = None) -> str:
        """Explain frequency-based scoring."""
        if score > 0.7:
            return f"Reflex: {score:.2f} (high frequency - habitual)"
        elif score > 0.5:
            return f"Reflex: {score:.2f} (moderate frequency)"
        else:
            return f"Reflex: {score:.2f} (low frequency - new/rare)"


__all__ = ["ReflexThreadAdapter"]
