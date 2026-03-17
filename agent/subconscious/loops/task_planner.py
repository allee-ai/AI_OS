"""
Task Planner — Context-Aware Multi-Step Task Execution
========================================================
Decomposes goals into steps, executes them using available tools,
and reports results. Can be triggered manually or by the thought loop.

Architecture:
    1. Goal → LLM decomposes into ordered steps
    2. For each step: gather context → select tool → execute → checkpoint
    3. After all steps: synthesize results → report
    4. Failures are retried once, then the task is marked failed with partial results

DB Table:
    tasks(id, goal, steps JSON, status, current_step, results JSON, 
          context_summary, created_at, updated_at)
"""

import json
import re
import ast
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .base import BackgroundLoop, LoopConfig


# ── Default prompts (editable at runtime) ───────────────────

DEFAULT_PROMPTS = {
    "plan": """You are the task planning module of a personal AI assistant.
Decompose this goal into concrete, ordered steps that can be executed.

Each step must be a dict with:
- "description": what this step does (1 sentence)
- "tool": the tool name to use (or "llm" for reasoning/writing tasks, "none" for no-action steps)
- "action": the specific action to call on the tool
- "params": dict of parameters for the tool action
- "depends_on": list of step indices this depends on (0-indexed), or [] if none

Rules:
- Keep it to 2-6 steps. Simpler is better.
- Use tool names and actions exactly as shown above.
- For research/analysis/writing tasks, use "llm" as the tool.
- If a step needs output from a previous step, reference it in depends_on.
- Be specific with params - include file paths, search terms, etc.

Output ONLY a Python list. No explanation.""",

    "execute_llm": """You are a personal AI assistant executing a task step.
Complete this step thoroughly. Be specific and actionable.
Output your result directly — no preamble, no \"here is the result\".""",

    "synthesize": """Summarize the results of this completed task.
Write a concise summary (2-4 sentences) of what was accomplished.
If any steps failed, mention what didn't work. Be direct.""",
}


# ─────────────────────────────────────────────────────────────
# Task DB helpers
# ─────────────────────────────────────────────────────────────

TASK_STATUSES = ["pending", "planning", "executing", "completed", "failed", "cancelled"]


def _ensure_tasks_table() -> None:
    """Create tasks table if it doesn't exist."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    steps TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'pending',
                    current_step INTEGER NOT NULL DEFAULT 0,
                    results TEXT NOT NULL DEFAULT '[]',
                    context_summary TEXT,
                    source TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[TaskPlanner] Failed to create table: {e}")


def create_task(goal: str, source: str = "manual") -> Dict[str, Any]:
    """Create a new task. Returns the task dict with id."""
    _ensure_tasks_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO tasks (goal, source) VALUES (?, ?)",
                (goal.strip(), source)
            )
            conn.commit()
            task_id = cur.lastrowid
            return {
                "id": task_id,
                "goal": goal.strip(),
                "steps": [],
                "status": "pending",
                "current_step": 0,
                "results": [],
                "context_summary": None,
                "source": source,
            }
    except Exception as e:
        raise RuntimeError(f"Failed to create task: {e}")


def get_tasks(status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """Get tasks, optionally filtered by status."""
    _ensure_tasks_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            if status:
                cur.execute(
                    "SELECT id, goal, steps, status, current_step, results, "
                    "context_summary, source, created_at, updated_at "
                    "FROM tasks WHERE status = ? ORDER BY id DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cur.execute(
                    "SELECT id, goal, steps, status, current_step, results, "
                    "context_summary, source, created_at, updated_at "
                    "FROM tasks ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            return [_row_to_task(r) for r in cur.fetchall()]
    except Exception:
        return []


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Get a single task by ID."""
    _ensure_tasks_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, goal, steps, status, current_step, results, "
                "context_summary, source, created_at, updated_at "
                "FROM tasks WHERE id = ?",
                (task_id,)
            )
            row = cur.fetchone()
            return _row_to_task(row) if row else None
    except Exception:
        return None


def update_task_status(task_id: int, status: str, **kwargs) -> bool:
    """Update task status and optional fields (steps, current_step, results, context_summary)."""
    _ensure_tasks_table()
    if status not in TASK_STATUSES:
        return False
    try:
        from data.db import get_connection
        from contextlib import closing
        
        sets = ["status = ?", "updated_at = datetime('now')"]
        params: list = [status]
        
        if "steps" in kwargs:
            sets.append("steps = ?")
            params.append(json.dumps(kwargs["steps"]))
        if "current_step" in kwargs:
            sets.append("current_step = ?")
            params.append(kwargs["current_step"])
        if "results" in kwargs:
            sets.append("results = ?")
            params.append(json.dumps(kwargs["results"]))
        if "context_summary" in kwargs:
            sets.append("context_summary = ?")
            params.append(kwargs["context_summary"])
        
        params.append(task_id)
        
        with closing(get_connection()) as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
            conn.commit()
            return True
    except Exception:
        return False


def cancel_task(task_id: int) -> bool:
    """Cancel a task (only if pending or executing)."""
    task = get_task(task_id)
    if not task or task["status"] not in ("pending", "planning", "executing"):
        return False
    return update_task_status(task_id, "cancelled")


def _row_to_task(row) -> Dict[str, Any]:
    """Convert a DB row tuple to a task dict."""
    return {
        "id": row[0],
        "goal": row[1],
        "steps": json.loads(row[2]) if row[2] else [],
        "status": row[3],
        "current_step": row[4],
        "results": json.loads(row[5]) if row[5] else [],
        "context_summary": row[6],
        "source": row[7],
        "created_at": row[8],
        "updated_at": row[9],
    }


# ─────────────────────────────────────────────────────────────
# TaskPlanner class
# ─────────────────────────────────────────────────────────────

class TaskPlanner(BackgroundLoop):
    """
    Context-aware task planner and executor.
    
    Periodically checks for pending tasks, decomposes them into steps
    using the LLM, and executes each step using available tools.
    
    Can also execute a single task on-demand via execute_task().
    
    Flow:
        1. Pick oldest pending task
        2. Gather context (identity, recent convos, available tools)
        3. LLM decomposes goal → ordered steps with tool assignments
        4. Execute each step: tool call → capture result → checkpoint
        5. Synthesize final result summary
        6. Mark complete (or failed with partial results)
    """
    
    def __init__(self, interval: float = 30.0, model: Optional[str] = None, enabled: bool = True):
        config = LoopConfig(
            interval_seconds=interval,
            name="task_planner",
            enabled=enabled,
        )
        super().__init__(config, self._check_and_execute)
        self._model = model
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._currently_executing: Optional[int] = None
        self._prompts: Dict[str, str] = {k: v for k, v in DEFAULT_PROMPTS.items()}
    
    @property
    def model(self) -> str:
        import os
        if self._model:
            return self._model
        return os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    
    @model.setter
    def model(self, value: str) -> None:
        self._model = value
    
    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["model"] = self.model
        base["tasks_completed"] = self._tasks_completed
        base["tasks_failed"] = self._tasks_failed
        base["currently_executing"] = self._currently_executing
        base["prompts"] = {k: v for k, v in getattr(self, '_prompts', DEFAULT_PROMPTS).items()}
        return base
    
    # ── Main loop tick ──────────────────────────────────────
    
    def _check_and_execute(self) -> None:
        """Check for pending tasks and execute the oldest one."""
        pending = get_tasks(status="pending", limit=1)
        if not pending:
            return
        
        task = pending[0]
        self.execute_task(task["id"])
    
    # ── Public API ──────────────────────────────────────────
    
    def execute_task(self, task_id: int) -> Dict[str, Any]:
        """
        Execute a task end-to-end: plan → execute steps → report.
        
        Can be called from the background loop or on-demand from API.
        Returns the final task state dict.
        """
        task = get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        
        if task["status"] not in ("pending", "executing"):
            return {"error": f"Task status is '{task['status']}', cannot execute"}
        
        self._currently_executing = task_id
        
        try:
            # Phase 1: Gather context
            context = self._gather_context(task["goal"])
            update_task_status(task_id, "planning", context_summary=context["summary"])
            
            # Phase 2: Decompose into steps
            if not task["steps"]:
                steps = self._plan_steps(task["goal"], context)
                if not steps:
                    update_task_status(task_id, "failed", results=[{
                        "step": 0, "error": "Failed to decompose goal into steps"
                    }])
                    self._tasks_failed += 1
                    return get_task(task_id)
                
                update_task_status(task_id, "executing", steps=steps, current_step=0)
                task = get_task(task_id)
            else:
                update_task_status(task_id, "executing")
                task = get_task(task_id)
            
            # Phase 3: Execute each step
            results = task.get("results", [])
            steps = task["steps"]
            
            for i in range(task["current_step"], len(steps)):
                step = steps[i]
                update_task_status(task_id, "executing", current_step=i)
                
                result = self._execute_step(step, results, context)
                results.append(result)
                
                # Checkpoint after each step
                update_task_status(task_id, "executing", current_step=i + 1, results=results)
                
                # On failure: retry once, then stop
                if not result.get("success"):
                    retry_result = self._execute_step(step, results, context, is_retry=True)
                    if retry_result.get("success"):
                        results[-1] = retry_result
                        update_task_status(task_id, "executing", results=results)
                    else:
                        results[-1] = retry_result
                        update_task_status(
                            task_id, "failed",
                            current_step=i + 1,
                            results=results,
                        )
                        self._tasks_failed += 1
                        self._log_task_event(task_id, "failed", f"Step {i+1} failed: {retry_result.get('error', 'unknown')}")
                        return get_task(task_id)
            
            # Phase 4: Synthesize final summary
            summary = self._synthesize_results(task["goal"], steps, results)
            results.append({"step": "summary", "output": summary, "success": True})
            
            update_task_status(task_id, "completed", results=results)
            self._tasks_completed += 1
            self._log_task_event(task_id, "completed", f"Completed {len(steps)} steps")
            
            # Broadcast completion
            self._broadcast_task_update(task_id, "completed", summary)
            
            return get_task(task_id)
        
        except Exception as e:
            update_task_status(task_id, "failed", results=[{
                "step": "error", "error": str(e), "success": False
            }])
            self._tasks_failed += 1
            return get_task(task_id)
        
        finally:
            self._currently_executing = None
    
    # ── Context gathering ───────────────────────────────────
    
    def _gather_context(self, goal: str) -> Dict[str, Any]:
        """Gather relevant context for planning a task."""
        ctx: Dict[str, Any] = {"summary": "", "tools": [], "identity": [], "recent": []}
        
        # Available tools
        try:
            from agent.threads.form.tools.registry import get_available_tools, format_tools_for_prompt
            tools = get_available_tools()
            ctx["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "actions": t.actions,
                    "category": t.category.value,
                }
                for t in tools
            ]
            ctx["tools_prompt"] = format_tools_for_prompt(tools, level=2)
        except Exception:
            ctx["tools_prompt"] = "No tools available."
        
        # User identity for personalization
        try:
            from agent.threads.identity.schema import pull_profile_facts
            facts = pull_profile_facts(profile_id="primary_user", limit=10)
            ctx["identity"] = [
                f"{f.get('key', '')}: {f.get('l1_value', '')}"
                for f in facts if f.get('l1_value')
            ]
        except Exception:
            pass
        
        # Recent conversations for context
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT user_message, assistant_message
                    FROM convo_turns ORDER BY id DESC LIMIT 3
                """)
                for row in cur.fetchall():
                    t = f"User: {row[0]}"
                    if row[1]:
                        t += f"\nAssistant: {row[1][:150]}"
                    ctx["recent"].append(t)
        except Exception:
            pass
        
        # Build summary string
        parts = [f"Goal: {goal}"]
        if ctx["identity"]:
            parts.append(f"User context: {'; '.join(ctx['identity'][:5])}")
        if ctx["recent"]:
            parts.append(f"Recent conversation context available ({len(ctx['recent'])} turns)")
        parts.append(f"Available tools: {len(ctx.get('tools', []))}")
        ctx["summary"] = " | ".join(parts)
        
        # When context_aware, inject the full orchestrator STATE block
        state_block = self._get_state(goal)
        if state_block:
            ctx["state"] = state_block
        
        return ctx
    
    # ── Step planning ───────────────────────────────────────
    
    def _plan_steps(self, goal: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use LLM to decompose a goal into executable steps."""
        
        identity_block = ""
        if context.get("identity"):
            identity_block = "\n".join(context["identity"][:5])
        
        recent_block = ""
        if context.get("recent"):
            recent_block = "\n---\n".join(context["recent"])
        
        tools_block = context.get("tools_prompt", "No tools available.")
        
        # Full consciousness context when available
        state_block = context.get("state", "")
        state_section = ""
        if state_block:
            state_section = f"""
CONSCIOUSNESS CONTEXT (your identity, user profile, concept graph, recent history):
\"\"\"
{state_block}
\"\"\"
"""
        
        prompt = f"""{getattr(self, '_prompts', DEFAULT_PROMPTS).get("plan", DEFAULT_PROMPTS["plan"])}

GOAL: {goal}
{state_section}

{f"USER CONTEXT:{chr(10)}{identity_block}" if identity_block else ""}

{f"RECENT CONVERSATION:{chr(10)}{recent_block}" if recent_block else ""}

AVAILABLE TOOLS:
{tools_block}

Python list:"""
        
        try:
            raw = self._call_model(prompt)
            steps = self._parse_list(raw)
            
            if not steps:
                return []
            
            # Validate and normalize steps
            validated = []
            for i, step in enumerate(steps):
                if not isinstance(step, dict):
                    continue
                validated.append({
                    "index": i,
                    "description": step.get("description", f"Step {i+1}"),
                    "tool": step.get("tool", "llm"),
                    "action": step.get("action", ""),
                    "params": step.get("params", {}),
                    "depends_on": step.get("depends_on", []),
                })
            
            return validated[:6]  # Hard cap at 6 steps
            
        except Exception as e:
            print(f"[TaskPlanner] Planning error: {e}")
            return []
    
    # ── Step execution ──────────────────────────────────────
    
    def _execute_step(
        self,
        step: Dict[str, Any],
        previous_results: List[Dict[str, Any]],
        context: Dict[str, Any],
        is_retry: bool = False,
    ) -> Dict[str, Any]:
        """Execute a single step. Returns result dict with success flag."""
        
        tool_name = step.get("tool", "llm")
        action = step.get("action", "")
        params = step.get("params", {})
        description = step.get("description", "")
        
        # Normalize LLM-hallucinated tool aliases
        _LLM_ALIASES = {"ask_llm": "llm", "reason": "llm", "think": "llm", "generate": "llm"}
        tool_name = _LLM_ALIASES.get(tool_name, tool_name)
        
        # Inject previous step results into params if referenced
        depends = step.get("depends_on", [])
        prev_context = ""
        for dep_idx in depends:
            if dep_idx < len(previous_results) and previous_results[dep_idx].get("success"):
                output = previous_results[dep_idx].get("output", "")
                prev_context += f"\n[Step {dep_idx + 1} result]: {str(output)[:500]}\n"
        
        try:
            if tool_name == "llm":
                # LLM reasoning step — no tool, just think
                output = self._llm_reasoning_step(description, params, prev_context, context)
                return {
                    "step": step.get("index", 0),
                    "description": description,
                    "tool": "llm",
                    "output": output,
                    "success": True,
                }
            
            elif tool_name == "none":
                return {
                    "step": step.get("index", 0),
                    "description": description,
                    "tool": "none",
                    "output": "No-op step completed.",
                    "success": True,
                }
            
            else:
                # Real tool execution
                from agent.threads.form.tools.executor import execute_tool
                from agent.threads.form.tools.registry import is_action_safe
                
                # Safety check
                if not is_action_safe(tool_name, action):
                    return {
                        "step": step.get("index", 0),
                        "description": description,
                        "tool": tool_name,
                        "action": action,
                        "output": None,
                        "error": f"Action '{action}' on tool '{tool_name}' is not in the safe list",
                        "success": False,
                    }
                
                # Add previous context to params if relevant
                if prev_context and "context" not in params:
                    params["context"] = prev_context.strip()
                
                result = execute_tool(tool_name, action, params)
                
                return {
                    "step": step.get("index", 0),
                    "description": description,
                    "tool": tool_name,
                    "action": action,
                    "output": str(result.output)[:2000] if result.output else None,
                    "error": result.error if not result.success else None,
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                }
        
        except Exception as e:
            return {
                "step": step.get("index", 0),
                "description": description,
                "tool": tool_name,
                "error": str(e),
                "success": False,
            }
    
    def _llm_reasoning_step(
        self,
        description: str,
        params: Dict[str, Any],
        prev_context: str,
        context: Dict[str, Any],
    ) -> str:
        """Execute a pure-LLM reasoning step (writing, analysis, synthesis)."""
        
        identity_block = ""
        if context.get("identity"):
            identity_block = "User context: " + "; ".join(context["identity"][:3])
        
        custom_prompt = params.get("prompt", "")
        
        prompt = f"""{getattr(self, '_prompts', DEFAULT_PROMPTS).get("execute_llm", DEFAULT_PROMPTS["execute_llm"])}

STEP: {description}
{f"ADDITIONAL INSTRUCTIONS: {custom_prompt}" if custom_prompt else ""}
{f"CONTEXT FROM PREVIOUS STEPS: {prev_context}" if prev_context else ""}
{identity_block}"""
        
        return self._call_model(prompt)
    
    # ── Result synthesis ────────────────────────────────────
    
    def _synthesize_results(
        self,
        goal: str,
        steps: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
    ) -> str:
        """Synthesize all step results into a final summary."""
        
        steps_summary = []
        for i, (step, result) in enumerate(zip(steps, results)):
            status = "✓" if result.get("success") else "✗"
            output = str(result.get("output", result.get("error", "")))[:300]
            steps_summary.append(f"Step {i+1} [{status}] {step.get('description', '')}: {output}")
        
        prompt = f"""{getattr(self, '_prompts', DEFAULT_PROMPTS).get("synthesize", DEFAULT_PROMPTS["synthesize"])}

GOAL: {goal}

STEP RESULTS:
{chr(10).join(steps_summary)}"""
        
        try:
            return self._call_model(prompt)
        except Exception:
            # Fallback: mechanical summary
            succeeded = sum(1 for r in results if r.get("success"))
            return f"Completed {succeeded}/{len(steps)} steps for: {goal}"
    
    # ── LLM calling ─────────────────────────────────────────
    
    def _call_model(self, prompt: str) -> str:
        """Call the LLM."""
        import os
        provider = os.getenv("AIOS_EXTRACT_PROVIDER", os.getenv("AIOS_MODEL_PROVIDER", "ollama"))
        
        if provider == "openai":
            return self._call_openai(prompt)
        return self._call_ollama(prompt)
    
    def _call_ollama(self, prompt: str) -> str:
        from .base import acquire_ollama_gate, release_ollama_gate
        import ollama
        if not acquire_ollama_gate():
            raise RuntimeError("Ollama gate timeout")
        try:
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.2}
            )
            return response["message"]["content"].strip()
        finally:
            release_ollama_gate()
    
    def _call_openai(self, prompt: str) -> str:
        import os, requests
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = os.getenv("OPENAI_API_KEY", "")
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    
    # ── Parsing ─────────────────────────────────────────────
    
    def _parse_list(self, raw: str) -> List[Dict[str, Any]]:
        """Parse LLM output into a Python list of dicts."""
        if not raw:
            return []
        
        raw = raw.strip()
        
        code_match = re.search(r'```(?:python)?\s*([\s\S]*?)```', raw)
        if code_match:
            raw = code_match.group(1).strip()
        
        list_start = raw.find('[')
        if list_start < 0:
            return []
        raw = raw[list_start:]
        
        bracket_count = 0
        end_pos = 0
        for i, char in enumerate(raw):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    end_pos = i + 1
                    break
        if end_pos > 0:
            raw = raw[:end_pos]
        
        try:
            result = ast.literal_eval(raw)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)]
        except (ValueError, SyntaxError):
            pass
        
        try:
            fixed = raw.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(fixed)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)]
        except (ValueError, SyntaxError):
            pass
        
        return []
    
    # ── Logging & broadcasting ──────────────────────────────
    
    def _log_task_event(self, task_id: int, status: str, message: str) -> None:
        """Log a task event to the event log."""
        try:
            from agent.threads.log import log_event
            log_event(
                f"task:{task_id}",
                "task_planner",
                f"[{status}] {message}"
            )
        except Exception:
            pass
    
    def _broadcast_task_update(self, task_id: int, status: str, summary: str) -> None:
        """Broadcast task update to connected WebSocket clients."""
        try:
            import asyncio
            from chat.api import websocket_manager
            
            message = {
                "type": "task_update",
                "task_id": task_id,
                "status": status,
                "summary": summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(websocket_manager.broadcast(message), loop)
                    return
            except RuntimeError:
                pass
            
            try:
                new_loop = asyncio.new_event_loop()
                new_loop.run_until_complete(websocket_manager.broadcast(message))
                new_loop.close()
            except Exception:
                pass
                
        except Exception:
            pass
