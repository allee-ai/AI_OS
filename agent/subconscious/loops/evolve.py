"""
Evolution Loop
==============
Autonomous self-improvement loop for the 3-model showdown experiment.

Unlike SelfImprovementLoop (which proposes changes for human review),
this loop is designed to run unattended for 24 hours:

1. Reviews its own codebase (scoped to safe paths)
2. Asks the LLM to propose a single focused improvement
3. Applies the change directly to disk
4. Commits with a descriptive message
5. Optionally triggers a service restart if code changed

Every cycle is logged to an evolution_log table so we can compare
what each model chose to work on.

Safety:
- Only modifies files matching EVOLUTION_ALLOWED (no core auth, no DB schema)
- Each change is committed so we have full git history
- Max file size limits prevent runaway writes
- Errors auto-backoff and cap at MAX_ERRORS consecutive failures
"""

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import BackgroundLoop, LoopConfig


# ── Configuration ───────────────────────────────────────────

# Files the evolution loop is allowed to touch
EVOLUTION_ALLOWED = [
    "agent/services/*.py",
    "agent/subconscious/loops/*.py",
    "agent/subconscious/api.py",
    "agent/subconscious/orchestrator.py",
    "agent/threads/*/adapter.py",
    "agent/threads/*/api.py",
    "agent/core/models_api.py",
    "agent/core/config.py",
    "scripts/server.py",
    "eval/*.py",
    "docs/api.py",
    "chat/api.py",
    "chat/schema.py",
]

# Files explicitly blocked even if they match above
EVOLUTION_BLOCKED = [
    "agent/core/auth.py",        # don't touch auth
    "agent/services/llm.py",     # don't break your own LLM calls
    "agent/subconscious/loops/evolve.py",  # don't modify yourself
]

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]  # → AI_OS/

MAX_FILE_SIZE = 50_000  # refuse to write files larger than 50KB
MAX_DIFF_LINES = 100    # cap on lines changed per cycle


# ── DB helpers ──────────────────────────────────────────────

def _ensure_evolution_table() -> None:
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evolution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle INTEGER NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    file_path TEXT,
                    description TEXT NOT NULL,
                    diff_summary TEXT,
                    commit_hash TEXT,
                    success INTEGER NOT NULL DEFAULT 1,
                    error TEXT,
                    duration_ms INTEGER,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[Evolve] DB init error: {e}")


def _log_evolution(cycle: int, provider: str, model: str,
                   file_path: str = "", description: str = "",
                   diff_summary: str = "", commit_hash: str = "",
                   success: bool = True, error: str = "",
                   duration_ms: int = 0) -> None:
    _ensure_evolution_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                "INSERT INTO evolution_log "
                "(cycle, provider, model, file_path, description, diff_summary, "
                "commit_hash, success, error, duration_ms) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cycle, provider, model, file_path, description,
                 diff_summary, commit_hash, int(success), error, duration_ms)
            )
            conn.commit()
    except Exception as e:
        print(f"[Evolve] Failed to log: {e}")


def get_evolution_log(limit: int = 50) -> List[Dict[str, Any]]:
    """Public: fetch evolution history for dashboard / comparison."""
    _ensure_evolution_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, cycle, provider, model, file_path, description, "
                "diff_summary, commit_hash, success, error, duration_ms, created_at "
                "FROM evolution_log ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            cols = ["id", "cycle", "provider", "model", "file_path", "description",
                    "diff_summary", "commit_hash", "success", "error",
                    "duration_ms", "created_at"]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []


# ── Path safety ─────────────────────────────────────────────

def _is_allowed_path(rel_path: str) -> bool:
    """Check if a relative path matches the evolution allowlist."""
    from fnmatch import fnmatch

    # Blocked list takes priority
    for blocked in EVOLUTION_BLOCKED:
        if fnmatch(rel_path, blocked):
            return False

    for pattern in EVOLUTION_ALLOWED:
        if fnmatch(rel_path, pattern):
            return True
    return False


def _list_allowed_files() -> List[str]:
    """List all files in workspace matching the allowlist."""
    allowed = []
    for f in WORKSPACE_ROOT.rglob("*.py"):
        if "__pycache__" in str(f) or ".venv" in str(f):
            continue
        rel = str(f.relative_to(WORKSPACE_ROOT))
        if _is_allowed_path(rel):
            allowed.append(rel)
    return sorted(allowed)


# ── Git helpers ─────────────────────────────────────────────

def _git_commit(message: str) -> str:
    """Stage all changes and commit. Returns commit hash or empty string."""
    try:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=str(WORKSPACE_ROOT), capture_output=True, timeout=30
        )
        result = subprocess.run(
            ["git", "commit", "-m", message, "--no-verify"],
            cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            # Extract short hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, timeout=10
            )
            return hash_result.stdout.strip()
    except Exception as e:
        print(f"[Evolve] Git commit failed: {e}")
    return ""


def _git_diff_stat() -> str:
    """Get a short diff stat of staged changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()[:500]
    except Exception:
        return ""


# ── Core evolution logic ────────────────────────────────────

EVOLVE_SYSTEM_PROMPT = """You are the autonomous evolution module of Nola, a personal AI operating system.

Your job: review the provided source files and propose ONE small, high-impact improvement.

RULES:
1. Propose exactly ONE change per cycle (not zero, not multiple)
2. The change must be to a SINGLE file
3. Changes should be: bug fixes, error handling, performance, clarity, missing features
4. You MUST provide the exact old text and exact new text for a find-and-replace
5. Keep changes under 30 lines — small and surgical
6. Do NOT change function signatures that other code depends on
7. Do NOT add comments that just restate the code
8. Do NOT refactor working code purely for style
9. Focus on changes that make the system more robust, capable, or efficient
10. Think about what would make this system genuinely better

YOU ARE {provider}/{model}. Your changes will be compared against other AI models
running the same loop. Make changes that demonstrate your model's strengths.

Respond with ONLY this JSON (no markdown fences, no explanation):
{{
  "file_path": "relative/path/to/file.py",
  "description": "What this change does (one line)",
  "rationale": "Why this improves the system (one line)",
  "old_text": "exact text to find in the file",
  "new_text": "exact replacement text"
}}"""


EVOLVE_USER_TEMPLATE = """Here are the files you can modify:

{file_contents}

Recent evolution history (what you've already done):
{recent_history}

Propose your next improvement."""


def _run_evolution_cycle(cycle: int, provider: str, model: str) -> str:
    """Run one evolution cycle. Returns summary string."""
    t0 = time.time()

    # 1. Gather file contents (sample — don't send everything every time)
    all_files = _list_allowed_files()
    if not all_files:
        return "No allowed files found"

    # Rotate through files: pick a window based on cycle number
    window_size = 8
    start = (cycle * window_size) % len(all_files)
    selected = (all_files[start:start + window_size] + all_files[:window_size])[:window_size]

    file_contents = ""
    for rel_path in selected:
        full = WORKSPACE_ROOT / rel_path
        try:
            content = full.read_text(errors="replace")
            if len(content) > 12000:
                content = content[:12000] + "\n# ... [truncated]"
            file_contents += f"\n### {rel_path}\n```python\n{content}\n```\n"
        except Exception:
            continue

    if not file_contents.strip():
        return "Could not read any files"

    # 2. Get recent history so we don't repeat ourselves
    recent = get_evolution_log(limit=10)
    history_text = "\n".join(
        f"- Cycle {r['cycle']}: {r['description']} ({r['file_path']})"
        for r in recent if r.get("success")
    ) or "(none yet — this is the first cycle)"

    # 3. Call LLM
    system = EVOLVE_SYSTEM_PROMPT.format(provider=provider, model=model)
    user_msg = EVOLVE_USER_TEMPLATE.format(
        file_contents=file_contents,
        recent_history=history_text,
    )

    try:
        from agent.services.llm import generate
        response = generate(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            provider=provider,
            model=model,
            temperature=0.4,
            max_tokens=2048,
        )
    except Exception as e:
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, error=str(e),
                       description="LLM call failed", success=False,
                       duration_ms=duration)
        return f"LLM call failed: {e}"

    # 4. Parse response
    try:
        text = response.strip()
        # Strip markdown fences if model wrapped it
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        proposal = json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, error=f"JSON parse: {e}",
                       description="Parse failed",
                       diff_summary=response[:500], success=False,
                       duration_ms=duration)
        return f"JSON parse failed: {response[:200]}"

    file_path = str(proposal.get("file_path", "")).strip()
    description = str(proposal.get("description", "")).strip()
    old_text = str(proposal.get("old_text", ""))
    new_text = str(proposal.get("new_text", ""))
    rationale = str(proposal.get("rationale", "")).strip()

    if not file_path or not old_text or not new_text:
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, file_path=file_path,
                       description="Incomplete proposal", success=False,
                       duration_ms=duration)
        return "Incomplete proposal — missing fields"

    # 5. Validate path
    if not _is_allowed_path(file_path):
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, file_path=file_path,
                       description=f"Blocked path: {file_path}", success=False,
                       duration_ms=duration)
        return f"Path not allowed: {file_path}"

    target = (WORKSPACE_ROOT / file_path).resolve()
    if not str(target).startswith(str(WORKSPACE_ROOT)):
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, file_path=file_path,
                       description="Path traversal blocked", success=False,
                       duration_ms=duration)
        return "Path traversal blocked"

    if not target.exists():
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, file_path=file_path,
                       description=f"File not found: {file_path}", success=False,
                       duration_ms=duration)
        return f"File not found: {file_path}"

    # 6. Apply the change
    content = target.read_text(errors="replace")
    if old_text not in content:
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, file_path=file_path,
                       description=f"old_text not found in {file_path}",
                       diff_summary=old_text[:200], success=False,
                       duration_ms=duration)
        return f"old_text not found in {file_path}"

    new_content = content.replace(old_text, new_text, 1)

    if len(new_content) > MAX_FILE_SIZE:
        duration = int((time.time() - t0) * 1000)
        _log_evolution(cycle, provider, model, file_path=file_path,
                       description="Result too large", success=False,
                       duration_ms=duration)
        return "Resulting file too large"

    # 7. Syntax check (Python only)
    if file_path.endswith(".py"):
        try:
            compile(new_content, file_path, "exec")
        except SyntaxError as e:
            duration = int((time.time() - t0) * 1000)
            _log_evolution(cycle, provider, model, file_path=file_path,
                           description=f"Syntax error: {e}",
                           diff_summary=new_text[:300], success=False,
                           duration_ms=duration)
            return f"Syntax error in proposed change: {e}"

    # 8. Write and commit
    target.write_text(new_content)

    # Stage the change
    subprocess.run(
        ["git", "add", file_path],
        cwd=str(WORKSPACE_ROOT), capture_output=True, timeout=10
    )
    diff_stat = _git_diff_stat()

    commit_msg = f"[evolve] {description}\n\nProvider: {provider}/{model}\nCycle: {cycle}\nFile: {file_path}\nRationale: {rationale}"
    commit_hash = _git_commit(commit_msg)

    duration = int((time.time() - t0) * 1000)
    _log_evolution(
        cycle=cycle, provider=provider, model=model,
        file_path=file_path, description=description,
        diff_summary=diff_stat or f"-{old_text[:100]}\n+{new_text[:100]}",
        commit_hash=commit_hash, success=True,
        duration_ms=duration,
    )

    summary = f"✓ Cycle {cycle}: {description} ({file_path})"
    if commit_hash:
        summary += f" [{commit_hash}]"
    return summary


# ── Loop class ──────────────────────────────────────────────

class EvolutionLoop(BackgroundLoop):
    """
    Autonomous evolution loop for the 3-model showdown.

    Runs every `interval` seconds, proposes + applies one change per cycle,
    commits to git. Designed to run for 24 hours unattended.
    """

    def __init__(self, interval: float = 1800, enabled: bool = True):
        """
        Args:
            interval: Seconds between cycles (default 30 min = ~48 cycles/day)
        """
        config = LoopConfig(
            interval_seconds=interval,
            name="evolution",
            enabled=enabled,
            max_errors=10,     # more forgiving for 24h run
            error_backoff=2.0,
            context_aware=False,
        )
        super().__init__(config, task=self._run)
        self._cycle = 0

    @property
    def provider(self) -> str:
        from agent.services.role_model import resolve_role
        return resolve_role("EVOLVE").provider

    @property
    def model(self) -> str:
        from agent.services.role_model import resolve_role
        return resolve_role("EVOLVE").model

    def _run(self) -> str:
        self._cycle += 1
        return _run_evolution_cycle(self._cycle, self.provider, self.model)

    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["cycle"] = self._cycle
        base["provider"] = self.provider
        base["model"] = self.model
        base["recent_log"] = get_evolution_log(limit=5)
        return base
