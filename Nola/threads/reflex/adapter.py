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
    from Nola.threads.reflex.schema import (
        get_greetings, get_shortcuts, get_system_reflexes,
        add_greeting, add_shortcut, add_system_reflex,
    )
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from .schema import (
        get_greetings, get_shortcuts, get_system_reflexes,
        add_greeting, add_shortcut, add_system_reflex,
    )


class ReflexThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for quick patterns and automatic responses.
    
    Uses local schema.py for in-memory pattern storage.
    - greetings: Greeting responses
    - shortcuts: User shortcuts
    - system: System reflexes
    """
    
    _name = "reflex"
    _description = "Quick patterns, shortcuts, and triggers"
    
    def health(self) -> HealthReport:
        """Check reflex thread health."""
        try:
            greetings = get_greetings(level=1)
            shortcuts = get_shortcuts(level=1)
            
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
        return get_greetings(level)
    
    def get_shortcuts(self, level: int = 2) -> List[Dict]:
        """Get user shortcuts."""
        return get_shortcuts(level)
    
    def get_system_reflexes(self, level: int = 2) -> List[Dict]:
        """Get system reflexes."""
        return get_system_reflexes(level)
    
    def get_modules(self) -> List[str]:
        """List modules in this thread."""
        return ["greetings", "shortcuts", "system"]
    
    def get_data(self, level: int = 2, limit: int = 50) -> List[Dict]:
        """Pull all data from this thread."""
        all_data = []
        for g in get_greetings(level)[:limit]:
            all_data.append({**g, "module": "greetings"})
        for s in get_shortcuts(level)[:limit]:
            all_data.append({**s, "module": "shortcuts"})
        for r in get_system_reflexes(level)[:limit]:
            all_data.append({**r, "module": "system"})
        return all_data[:limit]
    
    def add_greeting(
        self,
        key: str,
        response: str,
        weight: float = 0.8
    ) -> None:
        """Add a greeting response."""
        add_greeting(key, response, weight)
    
    def add_shortcut(
        self,
        trigger: str,
        response: str,
        description: str = ""
    ) -> None:
        """Add a user shortcut."""
        add_shortcut(trigger, response, description)
    
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
    
    def introspect(self, context_level: int = 2, query: str = None) -> IntrospectionResult:
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
        # TODO: Wire up to actual access tracking when designed
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
