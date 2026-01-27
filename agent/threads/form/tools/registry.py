"""
Form Thread Tools Registry
===========================

Defines all available tools that Agent can use.
Tools are registered on startup and updated as capabilities change.

Each tool has:
    - name: Unique identifier
    - description: What the tool does
    - category: Organization category
    - actions: Available actions
    - run_file: Path to executable (relative to executables/)
    - run_type: "python" | "shell" | "module"
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# Base path for tool executables
EXECUTABLES_DIR = Path(__file__).parent / "executables"


class ToolCategory(Enum):
    """Categories for tool organization."""
    COMMUNICATION = "communication"
    BROWSER = "browser"
    MEMORY = "memory"
    FILES = "files"
    AUTOMATION = "automation"
    INTERNAL = "internal"


class RunType(Enum):
    """How the tool should be executed."""
    PYTHON = "python"      # Import and call Python function
    SHELL = "shell"        # Execute shell script
    MODULE = "module"      # Run as Python module


@dataclass
class ToolDefinition:
    """Definition of a tool Agent can use."""
    name: str
    description: str
    category: ToolCategory
    actions: List[str]
    run_file: str = ""                          # e.g., "browser.py", "search.sh"
    run_type: RunType = RunType.PYTHON
    requires_env: List[str] = field(default_factory=list)
    weight: float = 0.5
    enabled: bool = True
    
    @property
    def path(self) -> Path:
        """Full path to the executable file."""
        if not self.run_file:
            return None
        return EXECUTABLES_DIR / self.run_file
    
    @property
    def exists(self) -> bool:
        """Check if the executable file exists."""
        p = self.path
        return p is not None and p.exists()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "actions": self.actions,
            "run_file": self.run_file,
            "run_type": self.run_type.value,
            "path": str(self.path) if self.path else None,
            "exists": self.exists,
            "requires_env": self.requires_env,
            "weight": self.weight,
            "enabled": self.enabled,
        }


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

TOOLS: List[ToolDefinition] = [
    # --- Communication Tools ---
    ToolDefinition(
        name="stimuli_gmail",
        description="Send and receive emails via Gmail API",
        category=ToolCategory.COMMUNICATION,
        actions=["draft_email", "read_inbox", "reply", "archive"],
        run_file="stimuli_gmail.py",
        run_type=RunType.PYTHON,
        requires_env=["GMAIL_TOKEN"],
        weight=0.6,
    ),
    ToolDefinition(
        name="stimuli_slack",
        description="Send and receive Slack messages",
        category=ToolCategory.COMMUNICATION,
        actions=["send_message", "read_channel", "reply_thread", "react"],
        run_file="stimuli_slack.py",
        run_type=RunType.PYTHON,
        requires_env=["SLACK_BOT_TOKEN"],
        weight=0.6,
    ),
    ToolDefinition(
        name="stimuli_sms",
        description="Send SMS messages via Twilio",
        category=ToolCategory.COMMUNICATION,
        actions=["send_sms", "read_messages"],
        run_file="stimuli_sms.py",
        run_type=RunType.PYTHON,
        requires_env=["TWILIO_SID", "TWILIO_TOKEN"],
        weight=0.5,
    ),
    ToolDefinition(
        name="stimuli_discord",
        description="Discord bot messaging",
        category=ToolCategory.COMMUNICATION,
        actions=["send_message", "read_channel", "reply"],
        run_file="stimuli_discord.py",
        run_type=RunType.PYTHON,
        requires_env=["DISCORD_BOT_TOKEN"],
        weight=0.5,
    ),
    ToolDefinition(
        name="stimuli_telegram",
        description="Telegram bot messaging",
        category=ToolCategory.COMMUNICATION,
        actions=["send_message", "read_updates", "reply"],
        run_file="stimuli_telegram.py",
        run_type=RunType.PYTHON,
        requires_env=["TELEGRAM_BOT_TOKEN"],
        weight=0.5,
    ),
    
    # --- Browser Tools ---
    ToolDefinition(
        name="browser",
        description="Kernel browser for web automation",
        category=ToolCategory.BROWSER,
        actions=["navigate", "screenshot", "click", "type", "extract", "scroll"],
        run_file="browser.py",
        run_type=RunType.PYTHON,
        requires_env=["KERNEL_API_KEY"],
        weight=0.7,
    ),
    ToolDefinition(
        name="web_search",
        description="Search the web for information",
        category=ToolCategory.BROWSER,
        actions=["search", "get_results"],
        run_file="web_search.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.6,
    ),
    
    # --- Memory Tools ---
    ToolDefinition(
        name="memory_identity",
        description="Read and update identity facts (who Agent is)",
        category=ToolCategory.MEMORY,
        actions=["get_identity", "update_identity", "list_keys"],
        run_file="memory_identity.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.8,
    ),
    ToolDefinition(
        name="memory_philosophy",
        description="Read and update beliefs and values",
        category=ToolCategory.MEMORY,
        actions=["get_beliefs", "update_belief", "list_values"],
        run_file="memory_philosophy.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.7,
    ),
    ToolDefinition(
        name="memory_log",
        description="Access conversation and event history",
        category=ToolCategory.MEMORY,
        actions=["search_logs", "get_recent", "get_session"],
        run_file="memory_log.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.6,
    ),
    ToolDefinition(
        name="memory_linking",
        description="Associative memory and concept linking",
        category=ToolCategory.MEMORY,
        actions=["spread_activate", "link_concepts", "find_related"],
        run_file="memory_linking.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.7,
    ),
    
    # --- File Tools ---
    ToolDefinition(
        name="file_read",
        description="Read files from workspace",
        category=ToolCategory.FILES,
        actions=["read_file", "list_directory", "search_files"],
        run_file="file_read.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.6,
    ),
    ToolDefinition(
        name="file_write",
        description="Write and create files in workspace",
        category=ToolCategory.FILES,
        actions=["write_file", "create_directory", "append_file"],
        run_file="file_write.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.5,
    ),
    
    # --- Automation Tools ---
    ToolDefinition(
        name="terminal",
        description="Execute shell commands",
        category=ToolCategory.AUTOMATION,
        actions=["run_command", "get_output", "kill_process"],
        run_file="terminal.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.5,
    ),
    ToolDefinition(
        name="scheduler",
        description="Schedule future actions and reminders",
        category=ToolCategory.AUTOMATION,
        actions=["schedule_task", "list_scheduled", "cancel_task"],
        run_file="scheduler.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.4,
    ),
    
    # --- Project Management Tools ---
    ToolDefinition(
        name="stimuli_github",
        description="GitHub issues, PRs, and notifications",
        category=ToolCategory.AUTOMATION,
        actions=["list_issues", "create_issue", "comment", "list_prs"],
        run_file="stimuli_github.py",
        run_type=RunType.PYTHON,
        requires_env=["GITHUB_TOKEN"],
        weight=0.6,
    ),
    ToolDefinition(
        name="stimuli_linear",
        description="Linear issue tracking",
        category=ToolCategory.AUTOMATION,
        actions=["list_issues", "create_issue", "update_status"],
        run_file="stimuli_linear.py",
        run_type=RunType.PYTHON,
        requires_env=["LINEAR_API_KEY"],
        weight=0.5,
    ),
    ToolDefinition(
        name="stimuli_notion",
        description="Notion pages and databases",
        category=ToolCategory.AUTOMATION,
        actions=["read_page", "update_page", "query_database"],
        run_file="stimuli_notion.py",
        run_type=RunType.PYTHON,
        requires_env=["NOTION_TOKEN"],
        weight=0.5,
    ),
    
    # --- Internal Tools ---
    ToolDefinition(
        name="ask_llm",
        description="Query the LLM for reasoning or generation",
        category=ToolCategory.INTERNAL,
        actions=["generate", "summarize", "analyze", "extract"],
        run_file="ask_llm.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.9,
    ),
    ToolDefinition(
        name="introspect",
        description="Access current consciousness state",
        category=ToolCategory.INTERNAL,
        actions=["get_context", "get_recent_thoughts", "get_active_threads"],
        run_file="introspect.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.8,
    ),
    ToolDefinition(
        name="notify",
        description="Send notifications to the user",
        category=ToolCategory.INTERNAL,
        actions=["alert", "remind", "confirm"],
        run_file="notify.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.6,
    ),
]


def get_all_tools() -> List[ToolDefinition]:
    """Get all tool definitions."""
    return TOOLS


def get_tools_by_category(category: ToolCategory) -> List[ToolDefinition]:
    """Get tools in a specific category."""
    return [t for t in TOOLS if t.category == category]


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Get a specific tool by name."""
    for tool in TOOLS:
        if tool.name == name:
            return tool
    return None


def get_enabled_tools() -> List[ToolDefinition]:
    """Get only enabled tools."""
    return [t for t in TOOLS if t.enabled]


def check_tool_availability(tool: ToolDefinition) -> bool:
    """Check if a tool's requirements are met (env vars exist)."""
    import os
    for env_var in tool.requires_env:
        if not os.environ.get(env_var):
            return False
    return True


def get_available_tools() -> List[ToolDefinition]:
    """Get tools that are enabled AND have requirements met."""
    return [t for t in TOOLS if t.enabled and check_tool_availability(t)]


def get_runnable_tools() -> List[ToolDefinition]:
    """Get tools that are available AND have existing executables."""
    return [t for t in get_available_tools() if t.exists]


# ============================================================================
# TOOL PROMPT GENERATION
# ============================================================================

def format_tools_for_prompt(tools: Optional[List[ToolDefinition]] = None, level: int = 2) -> str:
    """
    Format tools for inclusion in system prompt.
    
    Level 1: Just tool names
    Level 2: Names + descriptions
    Level 3: Full details with actions
    """
    if tools is None:
        tools = get_available_tools()
    
    if not tools:
        return "No tools currently available."
    
    if level == 1:
        return f"Available tools: {', '.join(t.name for t in tools)}"
    
    if level == 2:
        lines = ["Available tools:"]
        for tool in tools:
            status = "✓" if tool.exists else "○"
            lines.append(f"  {status} {tool.name}: {tool.description}")
        return "\n".join(lines)
    
    # Level 3: Full details
    lines = ["Available tools:"]
    for tool in tools:
        status = "✓" if tool.exists else "○"
        lines.append(f"\n  {status} {tool.name}")
        lines.append(f"    {tool.description}")
        lines.append(f"    Actions: {', '.join(tool.actions)}")
        lines.append(f"    File: {tool.run_file} ({tool.run_type.value})")
        if tool.requires_env:
            lines.append(f"    Requires: {', '.join(tool.requires_env)}")
    return "\n".join(lines)


__all__ = [
    "ToolCategory",
    "RunType",
    "ToolDefinition", 
    "TOOLS",
    "EXECUTABLES_DIR",
    "get_all_tools",
    "get_tools_by_category",
    "get_tool",
    "get_enabled_tools",
    "get_available_tools",
    "get_runnable_tools",
    "check_tool_availability",
    "format_tools_for_prompt",
]
