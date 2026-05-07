"""
copilot_executor — VM-side autonomous worker for copilot_request cards.

The reframe: phone submits a request → droplet outbox stores it → this
loop tick (running inside aios-loops.service on the VM) picks it up,
classifies it, and either:

  EXECUTE lane  — small, well-scoped tasks Ollama can reliably do:
                  prose/markdown edits, summaries, drafts, append-to-log,
                  restructure existing text. Acts directly, writes the
                  result to the appropriate workspace file (or a new
                  file in workspace/_copilot_results/), closes the card,
                  pings.

  PLAN lane     — anything code-shaped or risky: writes a structured
                  plan as a workspace file (so when laptop opens, it
                  shows up), leaves the card in 'planned' status, pings
                  with "drafted plan, awaiting laptop review."

This is the difference between an autonomous prose-editor (the VM can
own that) and a code-refactor (which still needs Cade-at-laptop or
Copilot-on-laptop). It chooses honestly which lane each card belongs in.

Single tick is bounded: at most N cards per pass, with a per-card
timeout, so a stuck Ollama call can't lock the supervisor.
"""

from __future__ import annotations

import json
import os
import re
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from data.db import get_connection

from .schema import get_card, resolve_card

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "workspace"
RESULTS_DIR = WORKSPACE / "_copilot_results"
PLANS_DIR = WORKSPACE / "_copilot_plans"

# ── Tunables ────────────────────────────────────────────────────────

MAX_CARDS_PER_PASS = int(os.getenv("AIOS_EXEC_MAX_CARDS", "1"))
PER_CARD_TIMEOUT_S = float(os.getenv("AIOS_EXEC_TIMEOUT_S", "60"))
EXECUTOR_ENABLED = os.getenv("AIOS_EXEC_ENABLED", "1") == "1"

# Cloud-tagged Ollama model. Routes through the local Ollama daemon
# (which forwards :*-cloud tags to Ollama Cloud — already signed in on
# the droplet), so we still call generate(provider="ollama", ...) but
# never burn the small VM CPU. Override with AIOS_EXEC_MODEL.
#
# Rate-limit awareness: Ollama Cloud has its own per-account caps.
# MAX_CARDS_PER_PASS=1 + a 15s tick = at most 4 calls/min from the
# executor lane. Background reflection loops (separate, future) need
# their own slower budget.
EXEC_MODEL = os.getenv("AIOS_EXEC_MODEL", "gpt-oss:120b-cloud")

# Heuristic classifier signals. Anything matching CODE_SIGNALS gets routed
# to the PLAN lane no matter what; the EXECUTE lane is only for
# prose-shaped work the small models can actually do well.
CODE_SIGNALS = (
    r"\brefactor\b",
    r"\bimplement\b",
    r"\bbuild (a|an|the)\b",
    r"\badd (an? )?(api|endpoint|table|column|migration|service|loop|adapter)\b",
    r"\bwire\b.*\bup\b",
    r"\bdebug\b",
    r"\bfix (the )?bug\b",
    r"\.py\b|\.tsx?\b|\.jsx?\b|\.css\b",
    r"\bdatabase\b|\bschema\b|\bsqlite\b",
    r"\bdeploy\b|\bsystemd\b|\bdocker\b",
)

PROSE_SIGNALS = (
    r"\bdraft\b|\brewrite\b|\bsummari[sz]e\b|\bsummary\b|\bcondense\b",
    r"\bnotes?\b|\bcheatsheet\b|\bone[- ]pager\b|\bbrief\b|\bjournal\b",
    r"\bemail\b.*\b(to|for)\b|\breply\b|\bmessage\b",
    r"\bedit\b.*\b\.md\b",
    r"\bappend\b|\badd a (line|note|entry|section|paragraph|bullet)\b",
    r"\bclean up\b.*\b(text|copy|wording)\b",
    r"\b(\d+[- ])?bullet(s)?\b|\blist( of)?\b",
    r"\boutline\b|\bagenda\b|\btalking points\b|\bscript\b",
)


# ── Card selection ──────────────────────────────────────────────────

def _next_card() -> Optional[Dict[str, Any]]:
    """Pull the highest-priority pending copilot_request card."""
    with closing(get_connection(readonly=True)) as conn:
        row = conn.execute(
            "SELECT id FROM outbox "
            "WHERE motor='copilot_request' AND status='pending' "
            "ORDER BY priority DESC, created_at ASC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    cid = int(row["id"] if not isinstance(row, tuple) else row[0])
    return get_card(cid)


# ── Classification ──────────────────────────────────────────────────

def classify(card: Dict[str, Any]) -> str:
    """Return 'execute' | 'plan' for a copilot_request card.

    Pure heuristic — no LLM call. Any code signal defaults to plan;
    explicit prose signals route to execute. Everything else defaults
    to plan, because plan is the safer fallback (we never destroy
    work in plan mode).
    """
    blob = " ".join((card.get("title") or "", card.get("body") or "")).lower()
    for pat in CODE_SIGNALS:
        if re.search(pat, blob):
            return "plan"
    for pat in PROSE_SIGNALS:
        if re.search(pat, blob):
            return "execute"
    return "plan"


# ── Workspace targeting ─────────────────────────────────────────────

_PATH_HINT_RE = re.compile(
    r"(?:edit|update|append.*?to|in)\s+([A-Za-z0-9_./-]+\.(?:md|txt|csv|json))",
    re.IGNORECASE,
)

def _find_target_file(card: Dict[str, Any]) -> Optional[Path]:
    """Try to extract a target file path from the card text.

    Only matches files that already exist under workspace/. Refuses to
    point outside the workspace as a guardrail — the executor never
    touches code, configs, or data dirs.
    """
    blob = (card.get("title") or "") + "\n" + (card.get("body") or "")
    for m in _PATH_HINT_RE.finditer(blob):
        rel = m.group(1).lstrip("/")
        # try as-given, then under workspace/
        candidates = [ROOT / rel]
        if not rel.startswith("workspace/"):
            candidates.append(WORKSPACE / rel)
        for p in candidates:
            try:
                resolved = p.resolve()
                # must be within workspace/
                if WORKSPACE.resolve() in resolved.parents and resolved.exists():
                    return resolved
            except Exception:
                continue
    return None


# ── Lane: EXECUTE (prose) ───────────────────────────────────────────

def _execute_prose(card: Dict[str, Any]) -> Dict[str, Any]:
    """Run a prose-shaped task with Ollama. Writes the result to a file
    in workspace/ and returns metadata about what changed.

    Provider is hard-pinned to ``ollama`` here (not role-resolved) so a
    misconfigured PLANNER/MEMORY role default can never accidentally
    burn cloud credits on phone-submitted prose work.
    """
    from agent.services.llm import generate

    target = _find_target_file(card)
    title = card.get("title") or ""
    body = card.get("body") or ""

    if target:
        existing = ""
        try:
            existing = target.read_text()[:8000]
        except Exception:
            existing = ""
        prompt = (
            f"You are AIOS acting on behalf of Cade. He sent a request from "
            f"his phone:\n\n"
            f"REQUEST TITLE: {title}\n"
            f"REQUEST BODY: {body}\n\n"
            f"You are editing this existing file: {target.relative_to(ROOT)}\n\n"
            f"=== CURRENT CONTENTS ===\n{existing}\n=== END ===\n\n"
            f"Produce the FULL UPDATED file contents. No commentary, no code "
            f"fences, no explanation — output only what the file should be "
            f"after your edit. Preserve the existing structure and tone."
        )
        result = generate(prompt, provider="ollama", model=EXEC_MODEL,
                          max_tokens=2048, temperature=0.4)
        # Strip wrapping code fences if the model added them anyway.
        result = re.sub(r"^```[a-z]*\n", "", result.strip())
        result = re.sub(r"\n```$", "", result.strip())
        backup = target.with_suffix(target.suffix + ".pre_aios.bak")
        try:
            backup.write_text(target.read_text())
        except Exception:
            pass
        target.write_text(result)
        return {
            "lane": "execute",
            "action": "edited_file",
            "path": str(target.relative_to(ROOT)),
            "backup": str(backup.relative_to(ROOT)),
            "bytes_out": len(result),
        }

    # No target file → produce a new artifact in workspace/_copilot_results/
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prompt = (
        f"You are AIOS acting on behalf of Cade. He sent this request "
        f"from his phone:\n\n"
        f"TITLE: {title}\n"
        f"BODY: {body}\n\n"
        f"Produce the artifact he's asking for in clean Markdown. No "
        f"meta-commentary, no 'here is your...' framing — just the work."
    )
    result = generate(prompt, provider="ollama", model=EXEC_MODEL,
                      max_tokens=2048, temperature=0.5)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50] or "result"
    out_path = RESULTS_DIR / f"{int(card['id']):04d}-{slug}.md"
    header = (
        f"# {title}\n\n"
        f"_AIOS produced this on the VM in response to a phone request._\n"
        f"_card #{card['id']} • {time.strftime('%Y-%m-%d %H:%M:%S')}_\n\n"
        f"---\n\n"
    )
    out_path.write_text(header + result.strip() + "\n")
    return {
        "lane": "execute",
        "action": "created_file",
        "path": str(out_path.relative_to(ROOT)),
        "bytes_out": len(result),
    }


# ── Lane: PLAN (code / risky) ───────────────────────────────────────

def _plan_for_laptop(card: Dict[str, Any]) -> Dict[str, Any]:
    """Use Ollama to draft a structured plan. Stage as workspace file
    so when laptop opens, Copilot-in-VS-Code sees the plan and can
    execute it. Card stays open under status='pending'; we add a
    resolution_note marker indicating a plan was drafted.

    Provider hard-pinned to ``ollama`` — same reason as _execute_prose.
    """
    from agent.services.llm import generate

    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    title = card.get("title") or ""
    body = card.get("body") or ""

    prompt = (
        "You are AIOS scoping a code/system task for a senior engineer "
        "(Cade) who will execute it later. The user submitted from his "
        "phone:\n\n"
        f"TITLE: {title}\n"
        f"BODY: {body}\n\n"
        "Produce a focused plan with these sections:\n"
        "  1. Restated goal (one sentence)\n"
        "  2. Files likely to change (best guess, file paths)\n"
        "  3. Key questions / unknowns\n"
        "  4. Suggested step order (bullets, max 6)\n"
        "  5. Risk level: low | medium | high (with one-line reason)\n\n"
        "Be terse. Do not write code. Output Markdown."
    )
    plan_md = generate(prompt, provider="ollama", model=EXEC_MODEL,
                       max_tokens=1200, temperature=0.3)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50] or "plan"
    out = PLANS_DIR / f"{int(card['id']):04d}-{slug}.md"
    header = (
        f"# Plan: {title}\n\n"
        f"_Drafted by AIOS on the VM. Awaiting laptop review._\n"
        f"_card #{card['id']} • {time.strftime('%Y-%m-%d %H:%M:%S')}_\n\n"
        f"## Original request\n\n{body or '(no body)'}\n\n---\n\n"
    )
    out.write_text(header + plan_md.strip() + "\n")
    return {
        "lane": "plan",
        "action": "drafted_plan",
        "path": str(out.relative_to(ROOT)),
        "bytes_out": len(plan_md),
    }


# ── Resolution + ping ───────────────────────────────────────────────

def _ping(message: str, priority: str = "info",
          context: Optional[Dict[str, Any]] = None) -> None:
    """Best-effort write to notifications table so the phone surfaces it."""
    try:
        with closing(get_connection()) as conn:
            conn.execute(
                "INSERT INTO notifications (type, message, priority, context) "
                "VALUES (?, ?, ?, ?)",
                ("copilot_executor", message, priority,
                 json.dumps(context or {})),
            )
            conn.commit()
    except Exception:
        pass


def _close_with_outcome(card_id: int, outcome: Dict[str, Any]) -> None:
    """Approve the card with a structured note carrying outcome metadata."""
    note = json.dumps(outcome)
    resolve_card(card_id, status="approved", note=note)


# ── Public entrypoint ───────────────────────────────────────────────

def tick_once() -> Dict[str, Any]:
    """Process up to MAX_CARDS_PER_PASS pending copilot_requests.

    Returns a summary dict for the supervisor's heartbeat log:
        { "executed": N, "planned": M, "errors": K, "skipped_disabled": bool }
    """
    if not EXECUTOR_ENABLED:
        return {"executed": 0, "planned": 0, "errors": 0,
                "skipped_disabled": True}

    executed = 0
    planned = 0
    errors = 0

    for _ in range(MAX_CARDS_PER_PASS):
        card = _next_card()
        if not card:
            break

        cid = int(card["id"])
        lane = classify(card)
        started = time.time()
        try:
            if lane == "execute":
                outcome = _execute_prose(card)
                executed += 1
            else:
                outcome = _plan_for_laptop(card)
                planned += 1
            outcome["elapsed_s"] = round(time.time() - started, 2)
        except Exception as e:  # noqa: BLE001
            errors += 1
            outcome = {
                "lane": lane,
                "action": "error",
                "error": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - started, 2),
            }

        _close_with_outcome(cid, outcome)

        # Ping the operator with a one-liner.
        title = (card.get("title") or "")[:80]
        if outcome.get("action") == "edited_file":
            msg = f"AIOS edited {outcome['path']}  (re: {title})"
            prio = "info"
        elif outcome.get("action") == "created_file":
            msg = f"AIOS produced {outcome['path']}  (re: {title})"
            prio = "info"
        elif outcome.get("action") == "drafted_plan":
            msg = (
                f"AIOS drafted plan {outcome['path']} — needs laptop "
                f"to execute.  (re: {title})"
            )
            prio = "info"
        else:
            msg = f"AIOS hit error on '{title}': {outcome.get('error','?')}"
            prio = "warn"

        _ping(msg, priority=prio, context={
            "card_id": cid,
            "lane": lane,
            **{k: v for k, v in outcome.items() if k != "error"},
        })

    return {
        "executed": executed,
        "planned": planned,
        "errors": errors,
        "skipped_disabled": False,
    }


__all__ = ["tick_once", "classify", "MAX_CARDS_PER_PASS", "EXECUTOR_ENABLED"]
