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
    MCP = "mcp"


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
        name="feed_gmail",
        description="Send and receive emails via Gmail API",
        category=ToolCategory.COMMUNICATION,
        actions=["draft_email", "read_inbox", "reply", "archive"],
        run_file="feed_gmail.py",
        run_type=RunType.PYTHON,
        requires_env=["GMAIL_TOKEN"],
        weight=0.6,
    ),
    ToolDefinition(
        name="feed_slack",
        description="Send and receive Slack messages",
        category=ToolCategory.COMMUNICATION,
        actions=["send_message", "read_channel", "reply_thread", "react"],
        run_file="feed_slack.py",
        run_type=RunType.PYTHON,
        requires_env=["SLACK_BOT_TOKEN"],
        weight=0.6,
    ),
    ToolDefinition(
        name="feed_sms",
        description="Send SMS messages via Twilio",
        category=ToolCategory.COMMUNICATION,
        actions=["send_sms", "read_messages"],
        run_file="feed_sms.py",
        run_type=RunType.PYTHON,
        requires_env=["TWILIO_SID", "TWILIO_TOKEN"],
        weight=0.5,
    ),
    ToolDefinition(
        name="feed_discord",
        description="Discord bot messaging",
        category=ToolCategory.COMMUNICATION,
        actions=["send_message", "read_channel", "reply"],
        run_file="feed_discord.py",
        run_type=RunType.PYTHON,
        requires_env=["DISCORD_BOT_TOKEN"],
        weight=0.5,
    ),
    ToolDefinition(
        name="feed_telegram",
        description="Telegram bot messaging",
        category=ToolCategory.COMMUNICATION,
        actions=["send_message", "read_updates", "reply"],
        run_file="feed_telegram.py",
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
    
    # --- Workspace DB Tools ---
    ToolDefinition(
        name="workspace_read",
        description="Read files from the workspace database (user-uploaded / UI-created files visible in the workspace panel)",
        category=ToolCategory.FILES,
        actions=["read_file", "list_directory", "search_files"],
        run_file="workspace_read.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.6,
    ),
    ToolDefinition(
        name="workspace_write",
        description="Write, create, move, or delete files in the workspace database (appears in workspace UI, does NOT touch git)",
        category=ToolCategory.FILES,
        actions=["write_file", "create_directory", "move_file", "delete_file"],
        run_file="workspace_write.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.6,
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
        name="feed_github",
        description="GitHub issues, PRs, and notifications",
        category=ToolCategory.AUTOMATION,
        actions=["list_issues", "create_issue", "comment", "list_prs"],
        run_file="feed_github.py",
        run_type=RunType.PYTHON,
        requires_env=["GITHUB_TOKEN"],
        weight=0.6,
    ),
    ToolDefinition(
        name="feed_linear",
        description="Linear issue tracking",
        category=ToolCategory.AUTOMATION,
        actions=["list_issues", "create_issue", "update_status"],
        run_file="feed_linear.py",
        run_type=RunType.PYTHON,
        requires_env=["LINEAR_API_KEY"],
        weight=0.5,
    ),
    ToolDefinition(
        name="feed_notion",
        description="Notion pages and databases",
        category=ToolCategory.AUTOMATION,
        actions=["read_page", "update_page", "query_database"],
        run_file="feed_notion.py",
        run_type=RunType.PYTHON,
        requires_env=["NOTION_TOKEN"],
        weight=0.5,
    ),
    
    # --- Search & Retrieval ---
    ToolDefinition(
        name="regex_search",
        description="Regex search across code, memory, logs, and concepts",
        category=ToolCategory.FILES,
        actions=["search", "search_memory", "search_logs", "search_concepts"],
        run_file="regex_search.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.7,
    ),
    ToolDefinition(
        name="cli_command",
        description="Execute AI OS internal CLI commands (/identity, /memory, /links, /tasks, etc.)",
        category=ToolCategory.AUTOMATION,
        actions=["run", "list_commands", "help"],
        run_file="cli_command.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.7,
    ),
    
    # --- Internal Tools ---
    ToolDefinition(
        name="code_edit",
        description="Edit project source files (sandboxed, allowlisted extensions only)",
        category=ToolCategory.FILES,
        actions=["edit_file", "read_file", "search_code", "list_files"],
        run_file="code_edit.py",
        run_type=RunType.PYTHON,
        requires_env=[],
        weight=0.6,
    ),
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
# SAFETY ALLOWLIST
# ============================================================================

# Actions that auto-execute without user approval
SAFE_ACTIONS: Dict[str, List[str]] = {
    "file_read": ["read_file", "list_directory", "search_files"],
    "web_search": ["search", "get_results"],
    "terminal": ["get_output"],
    "file_write": ["create_directory"],
    "workspace_read": ["read_file", "list_directory", "search_files"],
    "workspace_write": ["write_file", "create_directory", "move_file"],
    "memory_identity": ["get_identity", "list_keys"],
    "memory_philosophy": ["get_beliefs", "list_values"],
    "memory_log": ["search_logs", "get_recent", "get_session"],
    "memory_linking": ["spread_activate", "find_related"],
    "introspect": ["get_context", "get_recent_thoughts", "get_active_threads"],
    "regex_search": ["search", "search_memory", "search_logs", "search_concepts"],
    "cli_command": ["run", "list_commands", "help"],
    "notify": ["alert", "remind", "confirm", "list", "dismiss"],
    "code_edit": ["read_file", "search_code", "list_files"],
}

# Actions that are blocked by default (require user to toggle allowed)
BLOCKED_ACTIONS: Dict[str, List[str]] = {
    "terminal": ["run_command", "kill_process"],
    "file_write": ["write_file", "append_file"],
    "code_edit": ["edit_file"],
    "workspace_write": ["delete_file"],
}


def is_action_safe(tool_name: str, action: str) -> bool:
    """Check if a tool action can auto-execute.
    
    Safe actions run immediately.
    Blocked/unknown actions are denied — the LLM sees the denial
    and can tell the user what it wanted to do.
    
    This is an extra layer: the executor already checks the
    `allowed` DB flag per-tool. This adds per-action granularity.
    """
    safe = SAFE_ACTIONS.get(tool_name, [])
    return action in safe


# ============================================================================
# OLLAMA JSON TOOL CALLING SCHEMA
# ============================================================================

# Parameter schemas for each action (tool__action) used when building
# Ollama JSON tool specs.  Only actions listed in SAFE_ACTIONS are exported.
_ACTION_PARAM_SCHEMAS: Dict[str, Dict[str, str]] = {
    # file_read
    "file_read__read_file":        {"path": "File path relative to workspace root"},
    "file_read__list_directory":   {"path": "Directory path to list (default '.')"},
    "file_read__search_files":     {"pattern": "Glob pattern e.g. *.py",
                                    "directory": "Start directory (default '.')"},
    # file_write
    "file_write__write_file":      {"path": "File path to write",
                                    "content": "Content to write"},
    "file_write__append_file":     {"path": "File path to append to",
                                    "content": "Content to append"},
    "file_write__create_directory":{"path": "Directory path to create"},
    # terminal
    "terminal__run_command":       {"command": "Shell command to execute"},
    "terminal__get_output":        {},
    # web_search
    "web_search__search":          {"query": "Search query string"},
    "web_search__get_results":     {},
    # memory
    "memory_identity__get_identity":   {"key": "Optional fact key to retrieve"},
    "memory_identity__list_keys":      {},
    "memory_log__search_logs":         {"query": "Search string"},
    "memory_log__get_recent":          {"limit": "Number of events (default 10)"},
    "memory_log__get_session":         {},
    "memory_linking__spread_activate": {"concept": "Concept name to activate"},
    "memory_linking__find_related":    {"concept": "Concept name to find links for"},
    # regex_search
    "regex_search__search":            {"pattern": "Regex pattern to search for",
                                        "directory": "Directory to search (default '.')",
                                        "file_pattern": "File glob e.g. *.py (default '*')"},
    "regex_search__search_memory":     {"pattern": "Regex pattern to match against memory facts"},
    "regex_search__search_logs":       {"pattern": "Regex pattern to match in conversation logs",
                                        "limit": "Max turns to search (default 100)"},
    "regex_search__search_concepts":   {"pattern": "Regex pattern to match concept names"},
    # cli_command
    "cli_command__run":                {"command": "CLI command e.g. /identity, /tasks pending"},
    "cli_command__list_commands":      {},
    "cli_command__help":               {"command": "Command to get help for"},
    # notify
    "notify__alert":                   {"message": "Notification message",
                                        "priority": "low|normal|high|urgent (default normal)"},
    "notify__remind":                  {"message": "Reminder message",
                                        "context": "Additional context for the reminder"},
    "notify__confirm":                 {"question": "Question to ask the user",
                                        "options": "Comma-separated options (default yes,no)"},
    "notify__list":                    {"limit": "Max notifications (default 10)",
                                        "unread_only": "Only show unread (default false)"},
    "notify__dismiss":                 {"id": "Notification ID to dismiss"},
    # code_edit
    "code_edit__edit_file":             {"path": "File path relative to workspace",
                                        "old": "Exact text to replace",
                                        "new": "Replacement text"},
    "code_edit__read_file":             {"path": "File path to read"},
    "code_edit__search_code":           {"pattern": "Regex pattern to search for",
                                        "directory": "Directory to search (default '.')",
                                        "file_pattern": "Glob e.g. *.py (default *.py)"},
    "code_edit__list_files":            {"path": "Directory to list (default '.')"},
    # workspace_read
    "workspace_read__read_file":        {"path": "File path in workspace DB (e.g. /notes/todo.md)"},
    "workspace_read__list_directory":   {"path": "Directory path to list (default '/')"},
    "workspace_read__search_files":     {"query": "Full-text search query",
                                         "limit": "Max results (default 20)"},
    # workspace_write
    "workspace_write__write_file":      {"path": "File path to create/update in workspace DB",
                                         "content": "File content to write"},
    "workspace_write__create_directory":{"path": "Folder path to create in workspace DB"},
    "workspace_write__move_file":       {"old_path": "Current path of file/folder to move",
                                         "new_path": "Destination path (e.g. /organized/file.txt)"},
    "workspace_write__delete_file":     {"path": "File or folder path to delete from workspace DB"},
}


def to_ollama_tools(tools: Optional[List[ToolDefinition]] = None) -> List[Dict[str, Any]]:
    """Convert tool definitions to Ollama JSON tool calling format.

    Only exports actions present in SAFE_ACTIONS — the same set the
    text-native path auto-executes — so the safety contract is identical
    regardless of which calling mode is active.

    Function name format: ``{tool_name}__{action_name}``
    (double underscore; Ollama function names must be flat strings)

    Returns a list ready to pass as ``tools=`` in ``ollama.chat()``.
    """
    if tools is None:
        tools = get_runnable_tools()

    result: List[Dict[str, Any]] = []
    for tool in tools:
        safe = SAFE_ACTIONS.get(tool.name, [])
        for action in tool.actions:
            if action not in safe:
                continue

            fn_name = f"{tool.name}__{action}"
            param_descs = _ACTION_PARAM_SCHEMAS.get(fn_name, {})

            properties: Dict[str, Any] = {}
            required: List[str] = []
            for param, desc in param_descs.items():
                properties[param] = {"type": "string", "description": desc}
                required.append(param)

            result.append({
                "type": "function",
                "function": {
                    "name": fn_name,
                    "description": f"{tool.description} — {action}",
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            })

    return result


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


# ============================================================================
# DB SYNC — write registry tools to form_tools table once
# ============================================================================

_db_synced = False


def ensure_tools_in_db() -> int:
    """Write all TOOLS definitions into the form_tools DB table.

    Idempotent: INSERT OR REPLACE so the registry is always the authority.
    Called once per process; subsequent calls are a no-op.
    Returns the number of tools written.
    """
    global _db_synced
    if _db_synced:
        return 0

    try:
        import json as _json
        from contextlib import closing as _closing
        from agent.threads.form.schema import init_form_tools_table
        from data.db import get_connection

        init_form_tools_table()

        with _closing(get_connection()) as conn:
            for tool in TOOLS:
                conn.execute("""
                    INSERT OR REPLACE INTO form_tools
                        (name, description, category, actions, run_file,
                         run_type, requires_env, weight, enabled, allowed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tool.name,
                    tool.description,
                    tool.category.value,
                    _json.dumps(tool.actions),
                    tool.run_file,
                    tool.run_type.value,
                    _json.dumps(tool.requires_env),
                    tool.weight,
                    1 if tool.enabled else 0,
                    1,  # allowed=True for all registry tools
                ))
            conn.commit()

        _db_synced = True
        return len(TOOLS)
    except Exception:
        return 0


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
    "SAFE_ACTIONS",
    "BLOCKED_ACTIONS",
    "is_action_safe",
    "to_ollama_tools",
    "ensure_tools_in_db",
]
