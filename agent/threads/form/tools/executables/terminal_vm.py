"""
terminal_vm — Execute shell commands on the AIOS VM over SSH
=============================================================

Twin of ``terminal`` but targets the remote ``AIOS`` ssh host so the
agent (and any client — VS Code, CLI, mobile) can run commands on the
VM without leaving the tool protocol. The ssh host must be defined in
``~/.ssh/config`` as ``AIOS`` (same entry used by every other script
in this repo).

Actions:
    run_command(command, cwd=/opt/aios)  → stdout + stderr + exit code
    get_output()                          → last remote command's output
    probe()                               → reachability + basic facts

30-second timeout. Output truncated at 10KB.
"""

from __future__ import annotations

import subprocess
import shlex
from pathlib import Path

SSH_HOST = "AIOS"  # ~/.ssh/config entry
REMOTE_ROOT = "/opt/aios"
TIMEOUT = 30
MAX_OUTPUT = 10_000

# Same blocked set the local terminal uses — nothing destructive even on remote.
BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev",
    ":(){ :|:& };:",
    "> /dev/sda", "chmod -R 777 /",
}
DESTRUCTIVE_PREFIXES = (
    "rm -rf", "rm -r", "rmdir",
    "sudo rm", "sudo dd", "sudo mkfs",
    "shutdown", "reboot", "halt",
    "kill -9", "killall",
)

_last_output = {"stdout": "", "stderr": "", "exit_code": -1, "command": ""}


def run(action: str, params: dict) -> str:
    actions = {
        "run_command": _run_command,
        "get_output": _get_output,
        "probe": _probe,
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

    cmd_lower = command.strip().lower()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return f"Blocked: '{command}' matches a prohibited command pattern"
    for prefix in DESTRUCTIVE_PREFIXES:
        if cmd_lower.startswith(prefix):
            return f"Blocked: '{command}' starts with a destructive prefix ('{prefix}'). Use ssh directly if you really mean it."

    cwd = params.get("cwd") or REMOTE_ROOT
    # Wrap the command so it runs inside the remote cwd; quote for bash.
    remote_cmd = f"cd {shlex.quote(cwd)} && {command}"

    # We pass the whole remote command as a single argv element so the
    # local side doesn't re-split it. ssh -o BatchMode prevents prompts.
    ssh_argv = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=8",
        SSH_HOST,
        remote_cmd,
    ]

    try:
        result = subprocess.run(
            ssh_argv,
            shell=False,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
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
        if len(output) > MAX_OUTPUT:
            output = output[:MAX_OUTPUT] + "\n... [truncated]"
        return output
    except subprocess.TimeoutExpired:
        return f"Remote command timed out after {TIMEOUT}s: {command}"
    except Exception as e:
        return f"Error running remote command: {e}"


def _get_output(params: dict) -> str:
    if _last_output["exit_code"] == -1:
        return "No previous remote command output"
    return (
        f"Last remote command: {_last_output['command']}\n"
        f"stdout: {_last_output['stdout']}\n"
        f"stderr: {_last_output['stderr']}\n"
        f"exit code: {_last_output['exit_code']}"
    )


def _probe(params: dict) -> str:
    """Cheap reachability check + a few facts about the VM."""
    try:
        result = subprocess.run(
            [
                "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6",
                SSH_HOST,
                "hostname && uname -srm && (cd /opt/aios && git rev-parse --short HEAD 2>/dev/null || echo no-repo)",
            ],
            shell=False, capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return f"unreachable (exit {result.returncode}): {(result.stderr or '').strip()}"
        return f"reachable:\n{result.stdout.strip()}"
    except Exception as e:
        return f"probe error: {e}"
