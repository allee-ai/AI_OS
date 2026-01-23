"""
Form Thread Adapter
===================

Provides tool use, actions, and capabilities awareness to Agent.

This thread answers: "What can I do? How do I do it? What's happening now?"

Architecture:
- metadata = CAPABILITIES (what can happen, static)
- data = CURRENT STATE (what is happening now, dynamic)

Modules:
- tool_registry: Available tools and capabilities
- action_history: Record of actions taken
- browser: Browser/Kernel state
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os

try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult

try:
    from .tools import (
        TOOLS, ToolDefinition, ToolCategory,
        get_available_tools, check_tool_availability, format_tools_for_prompt
    )
    _HAS_TOOLS = True
except ImportError:
    _HAS_TOOLS = False
    TOOLS = []
    get_available_tools = lambda: []


class FormThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for tool use and action capabilities.
    
    Form uses:
    - metadata_json = capabilities (what CAN happen)
    - data_json = current state (what IS happening)
    
    This separation lets you query "what tools exist" vs "what's active now".
    """
    
    _name = "form"
    _description = "Tool use, actions, and capabilities"
    _seeded = False
    
    def health(self) -> HealthReport:
        """Check form thread health."""
        try:
            if _HAS_TOOLS:
                tools = get_available_tools()
                if tools:
                    return HealthReport.ok(
                        f"{len(tools)} tools available",
                        tool_count=len(tools)
                    )
            # Form is ready even without registered tools
            return HealthReport.ok(
                "Ready (tools from config)",
                tool_count=0
            )
        except Exception as e:
            return HealthReport.error(str(e))
    
    def seed_tools(self, force: bool = False) -> int:
        """
        Seed tool definitions from tools.py into the database.
        
        Returns number of tools registered.
        """
        if not _HAS_TOOLS:
            return 0
        
        if FormThreadAdapter._seeded and not force:
            return 0
        
        count = 0
        for tool in TOOLS:
            available = check_tool_availability(tool)
            self.register_tool(
                name=tool.name,
                description=tool.description,
                actions=tool.actions,
                category=tool.category.value,
                requires_env=tool.requires_env,
                available=available and tool.enabled,
                weight=tool.weight,
            )
            count += 1
        
        FormThreadAdapter._seeded = True
        return count
    
    def get_tools(self, level: int = 2) -> List[Dict]:
        """Get available tools."""
        return self.get_module_data("tool_registry", level)
    
    def get_tools_formatted(self, level: int = 2) -> str:
        """Get tools formatted for system prompt."""
        if _HAS_TOOLS:
            return format_tools_for_prompt(get_available_tools(), level)
        return "No tools available."
    
    def get_action_history(self, limit: int = 10) -> List[Dict]:
        """Get recent actions."""
        return self.get_module_data("action_history", level=3, limit=limit)
    
    def get_browser_state(self) -> List[Dict]:
        """Get browser/Kernel state."""
        return self.get_module_data("browser", level=2)
    
    def register_tool(
        self,
        name: str,
        description: str,
        actions: List[str],
        available: bool = True,
        weight: float = 0.5,
        category: str = "internal",
        requires_env: Optional[List[str]] = None,
    ) -> None:
        """
        Register a tool in the registry.
        
        metadata = capability definition (static)
        data = current availability state (dynamic)
        """
        self.push(
            module="tool_registry",
            key=f"tool_{name}",
            metadata={
                "type": "tool",
                "name": name,
                "description": description,
                "actions": actions,  # What it CAN do
                "category": category,
                "requires_env": requires_env or [],
            },
            data={
                "available": available,  # Is it usable NOW?
                "last_used": None,
                "use_count": 0,
            },
            level=2,
            weight=weight
        )
    
    def record_action(
        self,
        tool: str,
        action: str,
        success: bool,
        details: str = ""
    ) -> None:
        """
        Record an action that was taken.
        
        metadata = what action was attempted (static record)
        data = result/outcome (what happened)
        """
        timestamp = datetime.now(timezone.utc)
        
        self.push(
            module="action_history",
            key=f"action_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}",
            metadata={
                "type": "action",
                "tool": tool,
                "action": action,
                "timestamp": timestamp.isoformat(),
            },
            data={
                "success": success,
                "details": details,
                "duration_ms": None,
            },
            level=3,
            weight=0.2
        )
    
    def update_browser_state(self, url: str = "", title: str = "", session_id: str = "") -> None:
        """
        Update browser state.
        
        metadata = browser capability info (static)
        data = current page state (dynamic)
        """
        self.push(
            module="browser",
            key="current_browser",
            metadata={
                "type": "browser_state",
                "description": "Kernel browser session",
                "capabilities": ["navigate", "screenshot", "interact"],
            },
            data={
                "url": url,
                "title": title,
                "session_id": session_id,
                "updated": datetime.now(timezone.utc).isoformat(),
            },
            level=2,
            weight=0.4
        )
    
    def introspect(self, context_level: int = 2, query: str = None) -> IntrospectionResult:
        """
        Form introspection with capability awareness.
        
        Returns facts like:
        - "Available tools: browser, terminal, files"
        - "Browser: open on github.com"
        - "Recent action: executed terminal command"
        """
        # Ensure tools are seeded on first introspection
        self.seed_tools()
        
        facts = []
        
        # Tools - use formatted tools from tools.py for cleaner output
        if _HAS_TOOLS:
            available = get_available_tools()
            if available:
                if context_level == 1:
                    facts.append(f"Tools: {', '.join(t.name for t in available[:5])}...")
                elif context_level == 2:
                    # Group by category
                    by_cat: Dict[str, List[str]] = {}
                    for t in available:
                        cat = t.category.value
                        if cat not in by_cat:
                            by_cat[cat] = []
                        by_cat[cat].append(t.name)
                    for cat, names in by_cat.items():
                        facts.append(f"{cat.title()} tools: {', '.join(names)}")
                else:
                    # L3: Full details
                    for t in available:
                        facts.append(f"Tool {t.name}: {t.description} [{', '.join(t.actions[:3])}]")
        else:
            # Fallback to DB lookup
            tools = self.get_tools(context_level)
            tool_names = []
            for tool in tools:
                meta = tool.get("metadata", {})
                data = tool.get("data", {})
                name = meta.get("name", tool.get("key", "").replace("tool_", ""))
                if data.get("available", True):
                    tool_names.append(name)
            if tool_names:
                facts.append(f"Available tools: {', '.join(tool_names)}")
        
        # Browser state (L2+)
        if context_level >= 2:
            browser = self.get_browser_state()
            for b in browser:
                data = b.get("data", {})
                url = data.get("url", "")
                title = data.get("title", "")
                if url:
                    facts.append(f"Browser: {title or url}")
        
        # Action history (L3 only)
        if context_level >= 3:
            actions = self.get_action_history(3)
            for action in actions:
                data = action.get("data", {})
                act = data.get("action", "")
                tool = action.get("metadata", {}).get("tool", "")
                if act:
                    facts.append(f"Recent: {tool} → {act}")
        
        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level
        )


__all__ = ["FormThreadAdapter"]
