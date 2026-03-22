"""
terminal — Execute shell commands (sandboxed to workspace)
==========================================================

Actions:
    run_command(command)   → stdout + stderr + exit code (30s timeout)
    get_output()           → last command's output

CWD is always the workspace root. 30-second timeout.
Output truncated at 10KB to avoid blowing up context.
"""

import subprocess
import shlex
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # → AI_OS/
TIMEOUT = 30
MAX_OUTPUT = 10_000  # characters

# Commands that are never allowed (even if the LLM requests them)
BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev",
    ":(){ :|:& };:",  # fork bomb
    "> /dev/sda", "chmod -R 777 /",
}

# Prefixes that require extra caution
DESTRUCTIVE_PREFIXES = (
    "rm -rf", "rm -r", "rmdir",
    "sudo", "su ",
    "curl | bash", "curl | sh", "wget | bash",
    "shutdown", "reboot", "halt",
    "kill -9", "killall",
    "pip install", "npm install -g",
)

# Store last output for get_output action
_last_output = {"stdout": "", "stderr": "", "exit_code": -1, "command": ""}


def run(action: str, params: dict) -> str:
    """Execute a terminal action."""
    actions = {
        "run_command": _run_command,
        "get_output": _get_output,
    }
    
    fn = actions.get(action)
    if not fn:
        return f"Unknown action: {action}. Available: {', '.join(actions)}"
    
    return fn(params)


def _run_command(params: dict) -> str:
    global _last_output
    
    command = params.get("command", "")
    if not command:
        return "No command provided"
    
    # Block known-dangerous commands
    cmd_lower = command.strip().lower()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return f"Blocked: '{command}' matches a prohibited command pattern"
    
    for prefix in DESTRUCTIVE_PREFIXES:
        if cmd_lower.startswith(prefix):
            return f"Blocked: '{command}' starts with a destructive prefix ('{prefix}'). Use the CLI directly for this."
    
    try:
        # Use shlex.split + shell=False to prevent injection
        args = shlex.split(command)
        result = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=str(WORKSPACE_ROOT)
        )
        
        _last_output = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "command": command,
        }
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        output += f"\nExit code: {result.returncode}"
        
        # Truncate if massive
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n... [truncated]"
        
        return output
        
    except subprocess.TimeoutExpired:
        return f"Command timed out after {TIMEOUT}s: {command}"
    except Exception as e:
        return f"Error running command: {e}"


def _get_output(params: dict) -> str:
    if _last_output["exit_code"] == -1:
        return "No previous command output"
    return (
        f"Last command: {_last_output['command']}\n"
        f"stdout: {_last_output['stdout']}\n"
        f"stderr: {_last_output['stderr']}\n"
        f"exit code: {_last_output['exit_code']}"
    )
