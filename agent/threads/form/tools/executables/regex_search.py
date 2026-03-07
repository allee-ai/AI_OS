"""
regex_search — Regex search across codebase, data, and memory
==============================================================

Actions:
    search(pattern, directory, file_pattern)  → regex matches with context
    search_memory(pattern)                    → regex over approved memory facts
    search_logs(pattern, limit)               → regex over conversation history
    search_concepts(pattern)                  → regex over concept graph nodes

Combines structural search (files/code) with reality search (memory/logs)
so the task planner gets full context retrieval in one tool.

Output truncated at 20KB.
"""

import re
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]  # → AI_OS/
MAX_OUTPUT = 20_000
MAX_MATCHES = 50

# Directories to skip during file search
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
}

# Binary extensions to skip
SKIP_EXTS = {
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2",
    ".db", ".sqlite", ".sqlite3",
    ".dmg", ".app",
}


def run(action: str, params: dict) -> str:
    """Execute a regex_search action."""
    actions = {
        "search": _search_files,
        "search_memory": _search_memory,
        "search_logs": _search_logs,
        "search_concepts": _search_concepts,
    }

    fn = actions.get(action)
    if not fn:
        return f"Unknown action: {action}. Available: {', '.join(actions)}"

    try:
        return fn(params)
    except re.error as e:
        return f"Invalid regex pattern: {e}"
    except Exception as e:
        return f"Error: {e}"


# ── File / Code Search ───────────────────────────────────

def _search_files(params: dict) -> str:
    """Search files for regex matches with surrounding context."""
    pattern_str = params.get("pattern", "")
    directory = params.get("directory", ".")
    file_pattern = params.get("file_pattern", "*")
    context_lines = int(params.get("context_lines", "2"))
    case_sensitive = params.get("case_sensitive", "false").lower() == "true"

    if not pattern_str:
        return "No pattern provided."

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern_str, flags)
    except re.error as e:
        return f"Invalid regex: {e}"

    search_dir = (WORKSPACE_ROOT / directory).resolve()
    if not str(search_dir).startswith(str(WORKSPACE_ROOT)):
        return f"Directory outside workspace: {directory}"
    if not search_dir.is_dir():
        return f"Not a directory: {directory}"

    matches = []
    files_searched = 0

    for fpath in _walk_files(search_dir, file_pattern):
        files_searched += 1
        try:
            text = fpath.read_text(errors="replace")
        except Exception:
            continue

        lines = text.splitlines()
        for i, line in enumerate(lines):
            if regex.search(line):
                rel = fpath.relative_to(WORKSPACE_ROOT)
                ctx_start = max(0, i - context_lines)
                ctx_end = min(len(lines), i + context_lines + 1)
                context = lines[ctx_start:ctx_end]

                matches.append({
                    "file": str(rel),
                    "line": i + 1,
                    "match": line.strip(),
                    "context": context,
                })

                if len(matches) >= MAX_MATCHES:
                    break
        if len(matches) >= MAX_MATCHES:
            break

    if not matches:
        return f"No matches for /{pattern_str}/ in {directory} ({files_searched} files searched)"

    lines_out = [f"Found {len(matches)} matches across {files_searched} files:\n"]
    for m in matches:
        lines_out.append(f"── {m['file']}:{m['line']}")
        for ctx_line in m["context"]:
            lines_out.append(f"  {ctx_line}")
        lines_out.append("")

    output = "\n".join(lines_out)
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + f"\n... [truncated, {len(matches)} matches total]"
    return output


def _walk_files(root: Path, file_pattern: str):
    """Yield files matching pattern, skipping binary/hidden dirs."""
    if file_pattern == "*":
        globs = ["**/*"]
    elif "," in file_pattern:
        # Support "*.py,*.ts" syntax
        globs = [f"**/{p.strip()}" for p in file_pattern.split(",")]
    else:
        globs = [f"**/{file_pattern}"]

    seen = set()
    for glob_pat in globs:
        for fpath in root.glob(glob_pat):
            if fpath in seen or not fpath.is_file():
                continue
            seen.add(fpath)

            # Skip hidden/binary
            parts = fpath.relative_to(root).parts
            if any(p in SKIP_DIRS for p in parts):
                continue
            if fpath.suffix.lower() in SKIP_EXTS:
                continue

            yield fpath


# ── Memory Search ─────────────────────────────────────────

def _search_memory(params: dict) -> str:
    """Regex search over approved memory facts."""
    pattern_str = params.get("pattern", "")
    if not pattern_str:
        return "No pattern provided."

    regex = re.compile(pattern_str, re.IGNORECASE)

    try:
        from agent.subconscious.temp_memory.store import get_facts
        facts = get_facts(limit=500)
    except Exception as e:
        return f"Memory unavailable: {e}"

    matches = []
    for f in facts:
        text = f.text if hasattr(f, "text") else str(f)
        if regex.search(text):
            fid = f.id if hasattr(f, "id") else "?"
            matches.append(f"  [{fid}] {text}")
            if len(matches) >= MAX_MATCHES:
                break

    if not matches:
        return f"No memory facts matching /{pattern_str}/"

    return f"Memory matches ({len(matches)}):\n" + "\n".join(matches)


# ── Log / Conversation Search ────────────────────────────

def _search_logs(params: dict) -> str:
    """Regex search over conversation history."""
    pattern_str = params.get("pattern", "")
    limit = int(params.get("limit", "100"))
    if not pattern_str:
        return "No pattern provided."

    regex = re.compile(pattern_str, re.IGNORECASE)

    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, convo_id, user_message, assistant_message "
                "FROM convo_turns ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cur.fetchall()
    except Exception as e:
        return f"Log search unavailable: {e}"

    matches = []
    for row in rows:
        turn_id, convo_id, user_msg, asst_msg = row
        user_msg = user_msg or ""
        asst_msg = asst_msg or ""
        combined = f"{user_msg} {asst_msg}"
        if regex.search(combined):
            snippet = user_msg[:100]
            if asst_msg:
                snippet += f" → {asst_msg[:80]}"
            matches.append(f"  [turn:{turn_id}] {snippet}")
            if len(matches) >= MAX_MATCHES:
                break

    if not matches:
        return f"No conversation matches for /{pattern_str}/"

    return f"Conversation matches ({len(matches)}):\n" + "\n".join(matches)


# ── Concept Graph Search ─────────────────────────────────

def _search_concepts(params: dict) -> str:
    """Regex search over concept graph nodes."""
    pattern_str = params.get("pattern", "")
    if not pattern_str:
        return "No pattern provided."

    regex = re.compile(pattern_str, re.IGNORECASE)

    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            # Search concept nodes
            cur.execute(
                "SELECT DISTINCT source FROM concept_links "
                "UNION SELECT DISTINCT target FROM concept_links"
            )
            all_concepts = [row[0] for row in cur.fetchall()]
    except Exception as e:
        return f"Concept search unavailable: {e}"

    matches = [c for c in all_concepts if regex.search(c)]
    matches.sort()

    if not matches:
        return f"No concepts matching /{pattern_str}/"

    # For each match, show its top connections
    lines = [f"Matching concepts ({len(matches)}):"]
    try:
        from agent.threads.linking_core.schema import get_links_for_concept
        for concept in matches[:20]:
            links = get_links_for_concept(concept)
            neighbors = [f"{l['concept']}({l.get('strength', 0):.1f})" for l in links[:5]]
            neighbor_str = ", ".join(neighbors) if neighbors else "(isolated)"
            lines.append(f"  {concept} → {neighbor_str}")
    except Exception:
        for concept in matches[:30]:
            lines.append(f"  {concept}")

    return "\n".join(lines)
