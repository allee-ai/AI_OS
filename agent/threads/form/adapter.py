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
        """Seed tool definitions into the form_tools DB table.

        Delegates to registry.ensure_tools_in_db() which does INSERT OR
        REPLACE, so the registry.py TOOLS list is the single source of truth.
        Also pushes lightweight entries into the thread memory so that
        introspection can still list tools.

        Returns number of tools written.
        """
        if not _HAS_TOOLS:
            return 0

        if FormThreadAdapter._seeded and not force:
            return 0

        # Write to form_tools DB (the path execute_tool_action reads)
        try:
            from .tools.registry import ensure_tools_in_db
            ensure_tools_in_db()
        except Exception:
            pass

        # Also push lightweight entries into thread memory for introspection
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
    
    def get_section_metadata(self) -> List[str]:
        """Permanent form metadata for STATE section header."""
        try:
            if _HAS_TOOLS:
                from .tools.registry import get_runnable_tools
                available = get_available_tools()
                enabled = [t for t in available if t.weight > 0]
                runnable = get_runnable_tools()
                lines = [
                    f"  tools: {len(available)} ({len(runnable)} runnable)",
                ]
            else:
                tools = self.get_tools(1)
                lines = [f"  tools: {len(tools)}"]
            # Trace stats
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                row = conn.execute(
                    "SELECT COUNT(*) as cnt, AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as rate "
                    "FROM tool_traces"
                ).fetchone()
                cnt = row["cnt"] if row else 0
                rate = row["rate"] if row and row["rate"] is not None else 0
                if cnt > 0:
                    lines.append(f"  executions: {cnt} (success_rate: {rate:.0%})")
            except Exception:
                pass
            return lines
        except Exception:
            return []

    def introspect(self, context_level: int = 2, query: str = None, threshold: float = 0.0) -> IntrospectionResult:
        """
        Form introspection with budget-aware fact packing.

        Uses _budget_fill to fit tool/capability facts within a
        per-level token budget.

        Args:
            context_level: HEA level (1=lean, 2=medium, 3=full)
            query: Optional query for relevance filtering
            threshold: Minimum weight for tools/actions (0-10 scale)
        """
        self.seed_tools()
        relevant_concepts: List[str] = []

        min_weight = threshold / 10.0
        raw = self._get_raw_facts(min_weight=min_weight)

        if query:
            raw, relevant_concepts = self._relevance_boost(raw, query)

        facts = self._budget_fill(raw, context_level, query=query)

        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level,
            health=self.health().to_dict(),
            relevant_concepts=relevant_concepts,
        )

    def _get_raw_facts(self, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """Get raw facts with l1/l2/l3 value tiers for _budget_fill.

        Returns dicts with: path, l1_value, l2_value, l3_value, weight.
        """
        raw: List[Dict] = []

        # Tool-use instructions — high weight so they sort near top
        if _HAS_TOOLS:
            from .tools.registry import get_runnable_tools
            runnable = get_runnable_tools()
            if runnable:
                usage_short = "Tool calling available via :::execute blocks"
                usage_mid = (
                    "To use a tool, write an execute block:\\n"
                    ":::execute\\ntool: <tool_name>\\naction: <action_name>\\n"
                    "param_name: param_value\\n:::\\n"
                    "Only use tools when genuinely needed."
                )
                raw.append({
                    "path": "form.tools._usage",
                    "l1_value": usage_short,
                    "l2_value": usage_mid,
                    "l3_value": usage_mid + " Explain your reasoning first.",
                    "weight": 0.95,
                })

        # Available tools
        if _HAS_TOOLS:
            available = get_available_tools()
            for t in available:
                if t.weight < min_weight:
                    continue
                raw.append({
                    "path": f"form.tools.{t.name}",
                    "l1_value": t.name,
                    "l2_value": f"{t.description} (actions: {', '.join(t.actions)})",
                    "l3_value": (
                        f"{t.description} [{t.category.value}] "
                        f"(actions: {', '.join(t.actions)})"
                    ),
                    "weight": t.weight,
                })
        else:
            tools = self.get_tools(2)
            for tool in tools:
                meta = tool.get("metadata", {})
                data = tool.get("data", {})
                weight = tool.get("weight", 0.5)
                if weight < min_weight:
                    continue
                name = meta.get("name", tool.get("key", "").replace("tool_", ""))
                if data.get("available", True):
                    actions = ", ".join(meta.get("actions", []))
                    raw.append({
                        "path": f"form.tools.{name}",
                        "l1_value": name,
                        "l2_value": meta.get("description", ""),
                        "l3_value": (
                            f"{meta.get('description', '')} (actions: {actions})"
                        ),
                        "weight": weight,
                    })

        # Browser state
        browser = self.get_browser_state()
        for b in browser:
            data = b.get("data", {})
            url = data.get("url", "")
            title = data.get("title", "")
            if url:
                raw.append({
                    "path": "form.browser.url",
                    "l1_value": url,
                    "l2_value": f"{url} — {title}" if title else url,
                    "l3_value": f"Browser at {url}" + (f" ({title})" if title else ""),
                    "weight": 0.6,
                })

        # Action history
        actions = self.get_action_history(10)
        for i, action in enumerate(actions):
            data = action.get("data", {})
            meta = action.get("metadata", {})
            act = meta.get("action", "")
            tool = meta.get("tool", "")
            success = data.get("success", False)
            if act:
                raw.append({
                    "path": f"form.history.{i}",
                    "l1_value": f"{tool} → {act}",
                    "l2_value": f"{tool} → {act} ({'ok' if success else 'fail'})",
                    "l3_value": (
                        f"{tool} → {act} "
                        f"({'success' if success else 'failed'})"
                    ),
                    "weight": 0.4,
                })

        # Tool traces — recent weighted executions from tool_traces table
        try:
            from data.db import get_connection
            conn = get_connection(readonly=True)
            rows = conn.execute(
                """SELECT tool, action, success, output, weight, created_at
                   FROM tool_traces
                   WHERE weight >= ?
                   ORDER BY weight DESC, created_at DESC
                   LIMIT 10""",
                (min_weight,)
            ).fetchall()
            for r in rows:
                tool = r["tool"]
                action = r["action"]
                ok = "✓" if r["success"] else "✗"
                w = r["weight"]
                output = (r["output"] or "")[:100]
                raw.append({
                    "path": f"form.traces.{tool}.{action}",
                    "l1_value": f"{tool}.{action} {ok}",
                    "l2_value": f"{tool}.{action} {ok} (w={w:.2f})",
                    "l3_value": f"{tool}.{action} {ok} (w={w:.2f}) {output}".strip(),
                    "weight": w,
                })
        except Exception:
            pass

        return raw[:limit]


__all__ = ["FormThreadAdapter"]
