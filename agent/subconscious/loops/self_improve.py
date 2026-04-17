"""
Self-Improvement Loop
=====================
Scoped code improvement loop that reads insights from the thought loop,
proposes small edits to allowlisted files (API schemas, configs), and
stores proposals for human approval before applying.

Safety: only operates on allowlisted paths (*/api.py, */schema.py,
*/registry.py). Changes are NEVER auto-applied — they go to
proposed_improvements for explicit approval.
"""

import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .base import BackgroundLoop, LoopConfig


# Only these file patterns can be improved
ALLOWED_PATTERNS = [
    "*/api.py",
    "*/schema.py",
    "*/registry.py",
    "*/events.py",
]


# ─────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────

def _ensure_improvements_table() -> None:
    """Create proposed_improvements table if needed."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS proposed_improvements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    description TEXT NOT NULL,
                    diff TEXT NOT NULL,
                    rationale TEXT NOT NULL DEFAULT '',
                    source_thought_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    resolved_at TEXT
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[SelfImprove] Failed to create table: {e}")


def propose_improvement(file_path: str, description: str, diff: str,
                        rationale: str = "", source_thought_id: Optional[int] = None) -> int:
    """Store a proposed code improvement for review. Returns proposal ID."""
    _ensure_improvements_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO proposed_improvements "
                "(file_path, description, diff, rationale, source_thought_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (file_path, description, diff, rationale, source_thought_id)
            )
            conn.commit()
            return cur.lastrowid or 0
    except Exception as e:
        print(f"[SelfImprove] Failed to propose: {e}")
        return 0


def get_proposed_improvements(status: str = "pending", limit: int = 20) -> List[Dict[str, Any]]:
    """Get proposed improvements filtered by status."""
    _ensure_improvements_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, file_path, description, diff, rationale, source_thought_id, "
                "status, created_at, resolved_at "
                "FROM proposed_improvements WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit)
            )
            return [
                {
                    "id": r[0], "file_path": r[1], "description": r[2],
                    "diff": r[3], "rationale": r[4], "source_thought_id": r[5],
                    "status": r[6], "created_at": r[7], "resolved_at": r[8],
                }
                for r in cur.fetchall()
            ]
    except Exception:
        return []


def resolve_improvement(improvement_id: int, status: str = "approved") -> bool:
    """Approve or reject a proposed improvement."""
    if status not in ("approved", "rejected", "applied"):
        return False
    _ensure_improvements_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                "UPDATE proposed_improvements SET status = ?, resolved_at = datetime('now') "
                "WHERE id = ?",
                (status, improvement_id)
            )
            conn.commit()
            return True
    except Exception:
        return False


def apply_improvement(improvement_id: int) -> str:
    """Apply an approved improvement to the file. Returns result message."""
    improvements = get_proposed_improvements("approved", limit=100)
    imp = None
    for i in improvements:
        if i["id"] == improvement_id:
            imp = i
            break
    if not imp:
        return f"Improvement {improvement_id} not found or not approved"

    if not _is_allowed_path(imp["file_path"]):
        return f"File {imp['file_path']} is not in the allowlist"

    try:
        diff = json.loads(imp["diff"])
        old_text = diff.get("old", "")
        new_text = diff.get("new", "")
    except (json.JSONDecodeError, KeyError):
        return "Invalid diff format — expected JSON with 'old' and 'new' fields"

    from pathlib import Path
    workspace = Path(__file__).resolve().parents[4]  # → AI_OS/
    target = (workspace / imp["file_path"]).resolve()

    if not str(target).startswith(str(workspace)):
        return "Path traversal blocked"
    if not target.exists():
        return f"File not found: {imp['file_path']}"

    content = target.read_text()
    if old_text not in content:
        return "Old text not found in file — file may have changed since proposal"

    content = content.replace(old_text, new_text, 1)
    target.write_text(content)

    resolve_improvement(improvement_id, "applied")
    return f"Applied improvement {improvement_id} to {imp['file_path']}"


# ─────────────────────────────────────────────────────────────
# Path allowlist
# ─────────────────────────────────────────────────────────────

def _is_allowed_path(path: str) -> bool:
    """Check if a file path matches the allowlist."""
    from pathlib import PurePosixPath
    p = PurePosixPath(path)
    for pattern in ALLOWED_PATTERNS:
        # Simple glob-style match: */api.py matches chat/api.py, docs/api.py, etc.
        parts = pattern.split("/")
        if len(parts) == 2 and parts[0] == "*":
            if p.name == parts[1]:
                return True
    return False


# ─────────────────────────────────────────────────────────────
# Context gathering
# ─────────────────────────────────────────────────────────────

def _get_actionable_thoughts(limit: int = 10) -> List[Dict[str, Any]]:
    """Get un-acted-on thoughts that suggest improvements."""
    try:
        from .thought import get_thought_log
        thoughts = get_thought_log(limit=50, category="suggestion")
        return [t for t in thoughts if not t.get("acted_on")][:limit]
    except Exception:
        return []


def _get_recent_errors(limit: int = 5) -> List[str]:
    """Get recent error events from the log."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT data FROM events WHERE event_type = 'error' "
                "ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


def _read_allowed_files() -> Dict[str, str]:
    """Read contents of allowlisted files for the LLM to analyze."""
    from pathlib import Path
    workspace = Path(__file__).resolve().parents[4]  # → AI_OS/
    files = {}
    for pattern in ALLOWED_PATTERNS:
        parts = pattern.split("/")
        if len(parts) == 2 and parts[0] == "*":
            for match in workspace.rglob(parts[1]):
                if match.is_file():
                    rel = str(match.relative_to(workspace))
                    # Skip __pycache__, node_modules, etc.
                    if "__pycache__" in rel or "node_modules" in rel:
                        continue
                    try:
                        content = match.read_text(errors="replace")
                        # Truncate large files
                        if len(content) > 10000:
                            content = content[:10000] + "\n... [truncated]"
                        files[rel] = content
                    except Exception:
                        pass
    return files


# ─────────────────────────────────────────────────────────────
# Improvement generation
# ─────────────────────────────────────────────────────────────

IMPROVE_PROMPT = """You are the self-improvement module of a personal AI OS.

Your job: given recent insights, errors, and the current API/schema files,
propose 0-2 small, safe improvements to the codebase.

RULES:
- Only propose changes to these files: {allowed_files}
- Changes must be small and focused (< 20 lines changed)
- Never break existing functionality
- Changes should fix bugs, improve error handling, or add missing validations
- Do NOT refactor working code or add features
- If nothing needs improvement, return an empty list

Respond with ONLY a JSON array:
[{{"file_path": "...", "description": "...", "rationale": "...",
   "diff": {{"old": "exact text to replace", "new": "replacement text"}}}}]
Return [] if no improvements are warranted.

RECENT INSIGHTS:
{thoughts}

RECENT ERRORS:
{errors}

CURRENT FILES:
{files}"""


def _generate_improvements(prompt_template: str = IMPROVE_PROMPT) -> str:
    """Run one cycle of improvement proposal generation. Returns summary."""
    thoughts = _get_actionable_thoughts()
    errors = _get_recent_errors()
    files = _read_allowed_files()

    if not thoughts and not errors:
        return "No actionable thoughts or errors to work with"

    pending = get_proposed_improvements("pending")
    if len(pending) >= 5:
        return f"Skipped — already {len(pending)} pending proposals"

    file_list = list(files.keys())
    file_contents = "\n\n".join(
        f"### {path}\n```python\n{content}\n```"
        for path, content in list(files.items())[:10]
    )

    prompt = prompt_template.format(
        allowed_files=json.dumps(file_list),
        thoughts=json.dumps([t["thought"] for t in thoughts[:5]]),
        errors=json.dumps(errors[:5]),
        files=file_contents,
    )

    try:
        from agent.services.llm import generate
        response = generate(prompt=prompt, max_tokens=2048)
    except Exception as e:
        print(f"[SelfImprove] LLM call failed: {e}")
        return f"LLM call failed: {e}"

    # Parse response — lazy parse: try JSON, fall back to raw text
    try:
        text = response.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end == 0:
            return f"[raw output - no JSON array]\n{text[:2000]}"
        proposals = json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        return f"[raw output - JSON parse failed]\n{response.strip()[:2000]}"

    if not isinstance(proposals, list):
        return f"[raw output - not a list]\n{response.strip()[:2000]}"

    proposed_lines = []
    for p in proposals:
        if not isinstance(p, dict):
            continue
        file_path = str(p.get("file_path", "")).strip()
        if not file_path or not _is_allowed_path(file_path):
            continue
        diff = p.get("diff", {})
        if not isinstance(diff, dict) or "old" not in diff or "new" not in diff:
            continue
        if thoughts:
            try:
                from .thought import mark_thought_acted
                mark_thought_acted(thoughts[0]["id"])
            except Exception:
                pass
        propose_improvement(
            file_path=file_path,
            description=str(p.get("description", "")),
            diff=json.dumps(diff),
            rationale=str(p.get("rationale", "")),
        )
        proposed_lines.append(f"  {file_path}: {p.get('description', '')[:100]}")

    if proposed_lines:
        return f"Proposed {len(proposed_lines)} improvements:\n" + "\n".join(proposed_lines)
    return "No valid improvements to propose"


# ─────────────────────────────────────────────────────────────
# Loop class
# ─────────────────────────────────────────────────────────────

class SelfImprovementLoop(BackgroundLoop):
    """
    Periodically analyzes allowlisted files and proposes small improvements.
    Changes are NEVER auto-applied — they require explicit human approval.
    """

    def __init__(self, interval: float = 3600, enabled: bool = True):
        config = LoopConfig(
            interval_seconds=interval,
            name="self_improvement",
            enabled=enabled,
            max_errors=3,
            error_backoff=3.0,
            context_aware=False,
        )
        super().__init__(config, task=self._run)
        self._prompts: Dict[str, str] = {"improve": IMPROVE_PROMPT}

    def _run(self) -> str:
        return _generate_improvements(self._prompts.get("improve", IMPROVE_PROMPT))

    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["prompts"] = dict(self._prompts)
        return base
