"""
Task Planner tests — CRUD + execute pipeline + --live integration.

Mock mode (default):
    Tests task creation, retrieval, status updates, cancellation,
    and the full execute_task pipeline with a mocked LLM.

Live mode (``pytest --live`` or ``AIOS_TEST_LIVE=1``):
    Runs a real task pipeline against the configured LLM
    (Kimi K2, OpenAI-compat, or Ollama).
"""

import json
import os
import pytest
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import patch, MagicMock


# ── helpers ──────────────────────────────────────────────────

def _tp():
    """Construct a TaskPlanner without starting the loop."""
    from agent.subconscious.loops.task_planner import TaskPlanner
    tp = TaskPlanner.__new__(TaskPlanner)
    tp._model = None
    tp._tasks_completed = 0
    tp._tasks_failed = 0
    tp._currently_executing = None
    return tp


# Canned LLM responses for mock tests
_PLAN_RESPONSE = json.dumps([
    {
        "description": "Search for information about AI OS",
        "tool": "llm",
        "action": "",
        "params": {"prompt": "Summarize what AI OS is"},
        "depends_on": [],
    },
    {
        "description": "Summarize key findings",
        "tool": "llm",
        "action": "",
        "params": {"prompt": "Summarize the research"},
        "depends_on": [0],
    },
])

_LLM_STEP_RESPONSE = "AI OS is a personal cognitive architecture that augments human intelligence."
_SYNTHESIS_RESPONSE = "Completed research on AI OS. The system is a cognitive architecture for personal AI."


def _mock_call_model(self, prompt: str) -> str:
    """Route canned responses based on prompt content."""
    if "Decompose this goal" in prompt:
        return _PLAN_RESPONSE
    if "Summarize the results" in prompt:
        return _SYNTHESIS_RESPONSE
    return _LLM_STEP_RESPONSE


# ===================================================================
# 1. Task CRUD
# ===================================================================

class TestTaskCRUD:
    """create / get / list / update / cancel tasks."""

    def test_create_task(self):
        from agent.subconscious.loops.task_planner import create_task
        task = create_task("Test goal", source="test")
        assert task["id"] is not None
        assert task["goal"] == "Test goal"
        assert task["status"] == "pending"
        assert task["source"] == "test"
        assert task["steps"] == []
        assert task["results"] == []

    def test_get_task(self):
        from agent.subconscious.loops.task_planner import create_task, get_task
        task = create_task("Lookup task", source="test")
        fetched = get_task(task["id"])
        assert fetched is not None
        assert fetched["id"] == task["id"]
        assert fetched["goal"] == "Lookup task"

    def test_get_task_missing(self):
        from agent.subconscious.loops.task_planner import get_task
        assert get_task(999999) is None

    def test_get_tasks_all(self):
        from agent.subconscious.loops.task_planner import create_task, get_tasks
        create_task("Task A", source="test")
        create_task("Task B", source="test")
        tasks = get_tasks(limit=100)
        assert len(tasks) >= 2

    def test_get_tasks_by_status(self):
        from agent.subconscious.loops.task_planner import create_task, get_tasks
        create_task("Pending task", source="test")
        pending = get_tasks(status="pending")
        assert len(pending) >= 1
        assert all(t["status"] == "pending" for t in pending)

    def test_update_task_status(self):
        from agent.subconscious.loops.task_planner import create_task, get_task, update_task_status
        task = create_task("Update me", source="test")
        ok = update_task_status(task["id"], "executing", current_step=1)
        assert ok is True
        fetched = get_task(task["id"])
        assert fetched["status"] == "executing"
        assert fetched["current_step"] == 1

    def test_update_task_with_steps_and_results(self):
        from agent.subconscious.loops.task_planner import create_task, get_task, update_task_status
        task = create_task("Steps test", source="test")
        steps = [{"description": "Step 1", "tool": "llm"}]
        results = [{"step": 0, "output": "done", "success": True}]
        update_task_status(task["id"], "completed", steps=steps, results=results)
        fetched = get_task(task["id"])
        assert fetched["status"] == "completed"
        assert len(fetched["steps"]) == 1
        assert len(fetched["results"]) == 1

    def test_update_invalid_status_rejected(self):
        from agent.subconscious.loops.task_planner import create_task, update_task_status
        task = create_task("Bad status", source="test")
        ok = update_task_status(task["id"], "invalid_status")
        assert ok is False

    def test_cancel_pending_task(self):
        from agent.subconscious.loops.task_planner import create_task, get_task, cancel_task
        task = create_task("Cancel me", source="test")
        ok = cancel_task(task["id"])
        assert ok is True
        fetched = get_task(task["id"])
        assert fetched["status"] == "cancelled"

    def test_cancel_completed_task_fails(self):
        from agent.subconscious.loops.task_planner import create_task, update_task_status, cancel_task
        task = create_task("Already done", source="test")
        update_task_status(task["id"], "completed")
        ok = cancel_task(task["id"])
        assert ok is False

    def test_cancel_nonexistent_task_fails(self):
        from agent.subconscious.loops.task_planner import cancel_task
        assert cancel_task(999999) is False

    def test_task_statuses_constant(self):
        from agent.subconscious.loops.task_planner import TASK_STATUSES
        assert "pending" in TASK_STATUSES
        assert "completed" in TASK_STATUSES
        assert "failed" in TASK_STATUSES
        assert "cancelled" in TASK_STATUSES


# ===================================================================
# 2. _parse_list (deterministic, no LLM needed)
# ===================================================================

class TestParseList:
    """TaskPlanner._parse_list handles various LLM output formats."""

    def test_clean_python_list(self):
        tp = _tp()
        result = tp._parse_list('[{"a": 1}, {"b": 2}]')
        assert len(result) == 2
        assert result[0]["a"] == 1

    def test_code_fence_wrapped(self):
        tp = _tp()
        raw = '```python\n[{"step": "do it"}]\n```'
        result = tp._parse_list(raw)
        assert len(result) == 1
        assert result[0]["step"] == "do it"

    def test_preamble_before_list(self):
        tp = _tp()
        raw = 'Here are the steps:\n[{"x": 1}]'
        result = tp._parse_list(raw)
        assert len(result) == 1

    def test_empty_input(self):
        tp = _tp()
        assert tp._parse_list("") == []
        assert tp._parse_list(None) == []

    def test_no_list_in_text(self):
        tp = _tp()
        assert tp._parse_list("Just some text with no list.") == []

    def test_filters_non_dicts(self):
        tp = _tp()
        result = tp._parse_list('[{"valid": true}, "not a dict", 42]')
        assert len(result) == 1
        assert result[0]["valid"] is True

    def test_json_booleans_converted(self):
        """LLMs sometimes output JSON-style true/false/null."""
        tp = _tp()
        raw = '[{"enabled": true, "value": null}]'
        result = tp._parse_list(raw)
        assert len(result) == 1
        assert result[0]["enabled"] is True
        assert result[0]["value"] is None

    def test_real_plan_format(self):
        """Matches the exact format _plan_steps expects back."""
        tp = _tp()
        result = tp._parse_list(_PLAN_RESPONSE)
        assert len(result) == 2
        assert result[0]["tool"] == "llm"
        assert result[1]["depends_on"] == [0]


# ===================================================================
# 3. Full Execute Pipeline (mocked LLM, mocked tools)
# ===================================================================

class TestExecutePipeline:
    """TaskPlanner.execute_task end-to-end with mocked _call_model."""

    @patch.object(
        __import__("agent.subconscious.loops.task_planner", fromlist=["TaskPlanner"]).TaskPlanner,
        "_call_model",
        _mock_call_model,
    )
    def test_execute_task_completes(self):
        """Full pipeline: create → plan → execute steps → synthesize."""
        from agent.subconscious.loops.task_planner import TaskPlanner, create_task, get_task

        tp = TaskPlanner(interval=999, enabled=False)

        task = create_task("Research AI OS architecture", source="test")
        result = tp.execute_task(task["id"])

        assert result["status"] == "completed"
        assert len(result["steps"]) == 2
        assert len(result["results"]) == 3  # 2 steps + 1 summary
        assert result["results"][-1]["step"] == "summary"
        assert tp._tasks_completed >= 1

    @patch.object(
        __import__("agent.subconscious.loops.task_planner", fromlist=["TaskPlanner"]).TaskPlanner,
        "_call_model",
        _mock_call_model,
    )
    def test_execute_task_sets_context_summary(self):
        from agent.subconscious.loops.task_planner import TaskPlanner, create_task, get_task

        tp = TaskPlanner(interval=999, enabled=False)
        task = create_task("Check context summary", source="test")
        result = tp.execute_task(task["id"])

        assert result["context_summary"] is not None
        assert "Goal:" in result["context_summary"]

    @patch.object(
        __import__("agent.subconscious.loops.task_planner", fromlist=["TaskPlanner"]).TaskPlanner,
        "_call_model",
        _mock_call_model,
    )
    def test_execute_task_not_found(self):
        from agent.subconscious.loops.task_planner import TaskPlanner
        tp = TaskPlanner(interval=999, enabled=False)
        result = tp.execute_task(999999)
        assert "error" in result

    @patch.object(
        __import__("agent.subconscious.loops.task_planner", fromlist=["TaskPlanner"]).TaskPlanner,
        "_call_model",
        _mock_call_model,
    )
    def test_execute_already_completed(self):
        from agent.subconscious.loops.task_planner import TaskPlanner, create_task, update_task_status
        tp = TaskPlanner(interval=999, enabled=False)
        task = create_task("Already done", source="test")
        update_task_status(task["id"], "completed")
        result = tp.execute_task(task["id"])
        assert "error" in result

    def test_execute_step_llm_type(self):
        """LLM-type step calls _llm_reasoning_step."""
        tp = _tp()
        step = {"index": 0, "description": "Think about X", "tool": "llm", "action": "", "params": {}, "depends_on": []}
        with patch.object(type(tp), "_call_model", _mock_call_model):
            result = tp._execute_step(step, [], {"identity": [], "recent": []})
        assert result["success"] is True
        assert result["tool"] == "llm"
        assert len(result["output"]) > 0

    def test_execute_step_none_type(self):
        """'none' tool type is a no-op."""
        tp = _tp()
        step = {"index": 0, "description": "No action", "tool": "none", "action": "", "params": {}, "depends_on": []}
        result = tp._execute_step(step, [], {})
        assert result["success"] is True
        assert result["tool"] == "none"

    def test_execute_step_tool_type_safe(self):
        """Real tool execution when action is marked safe."""

        @dataclass
        class FakeToolResult:
            tool_name: str = "file_read"
            action: str = "read"
            output: Any = "file content here"
            error: Optional[str] = None
            duration_ms: float = 5.0

            @property
            def success(self):
                return self.error is None

        tp = _tp()
        step = {
            "index": 0,
            "description": "Read a file",
            "tool": "file_read",
            "action": "read",
            "params": {"path": "/tmp/test.txt"},
            "depends_on": [],
        }

        with patch("agent.threads.form.tools.executor.execute_tool", return_value=FakeToolResult()), \
             patch("agent.threads.form.tools.registry.is_action_safe", return_value=True):
            result = tp._execute_step(step, [], {})

        assert result["success"] is True
        assert result["output"] == "file content here"
        assert result["tool"] == "file_read"

    def test_execute_step_tool_unsafe(self):
        """Unsafe tool+action is rejected."""
        tp = _tp()
        step = {
            "index": 0,
            "description": "Dangerous action",
            "tool": "terminal",
            "action": "exec",
            "params": {"command": "rm -rf /"},
            "depends_on": [],
        }

        with patch("agent.threads.form.tools.registry.is_action_safe", return_value=False):
            result = tp._execute_step(step, [], {})

        assert result["success"] is False
        assert "not in the safe list" in result["error"]

    def test_execute_step_injects_previous_context(self):
        """Steps with depends_on get previous results injected."""
        tp = _tp()
        step = {
            "index": 1,
            "description": "Summarize previous",
            "tool": "llm",
            "action": "",
            "params": {},
            "depends_on": [0],
        }
        previous = [{"success": True, "output": "First step produced data XYZ"}]

        with patch.object(type(tp), "_call_model", _mock_call_model):
            result = tp._execute_step(step, previous, {"identity": [], "recent": []})

        assert result["success"] is True

    def test_plan_steps_returns_validated_list(self):
        """_plan_steps returns normalized step dicts."""
        tp = _tp()
        ctx = {"identity": [], "recent": [], "tools_prompt": "No tools.", "tools": []}
        with patch.object(type(tp), "_call_model", _mock_call_model):
            steps = tp._plan_steps("Research AI OS", ctx)
        assert len(steps) == 2
        # Validate normalization
        for step in steps:
            assert "index" in step
            assert "description" in step
            assert "tool" in step
            assert "params" in step

    def test_plan_steps_caps_at_six(self):
        """Even if LLM returns more than 6, we cap."""
        tp = _tp()
        big_plan = json.dumps([{"description": f"Step {i}", "tool": "llm"} for i in range(10)])

        def _return_big(self_inner, prompt):
            if "Decompose" in prompt:
                return big_plan
            return "ok"

        ctx = {"identity": [], "recent": [], "tools_prompt": "", "tools": []}
        with patch.object(type(tp), "_call_model", _return_big):
            steps = tp._plan_steps("Many steps", ctx)
        assert len(steps) <= 6

    def test_plan_steps_returns_empty_on_bad_llm(self):
        """If LLM returns garbage, _plan_steps returns []."""
        tp = _tp()
        ctx = {"identity": [], "recent": [], "tools_prompt": "", "tools": []}
        with patch.object(type(tp), "_call_model", lambda s, p: "I don't understand"):
            steps = tp._plan_steps("Bad goal", ctx)
        assert steps == []

    def test_synthesize_results_fallback(self):
        """When LLM raises, we get the mechanical fallback summary."""
        tp = _tp()
        steps = [{"description": "Run test"}]
        results = [{"success": True, "output": "ok"}]

        def _explode(self_inner, prompt):
            raise RuntimeError("LLM is down")

        with patch.object(type(tp), "_call_model", _explode):
            summary = tp._synthesize_results("Do stuff", steps, results)
        assert "1/1 steps" in summary

    @patch.object(
        __import__("agent.subconscious.loops.task_planner", fromlist=["TaskPlanner"]).TaskPlanner,
        "_call_model",
        _mock_call_model,
    )
    def test_execute_task_step_failure_retries(self):
        """A failing step is retried once; second failure → task fails."""
        from agent.subconscious.loops.task_planner import TaskPlanner, create_task

        tp = TaskPlanner(interval=999, enabled=False)
        task = create_task("Fail task", source="test")

        call_count = [0]
        original_execute_step = tp._execute_step

        def _failing_step(step, prev, ctx, is_retry=False):
            if step.get("index", 0) == 0:
                call_count[0] += 1
                return {"step": 0, "error": "Tool crashed", "success": False}
            return original_execute_step(step, prev, ctx, is_retry=is_retry)

        with patch.object(tp, "_execute_step", side_effect=_failing_step):
            result = tp.execute_task(task["id"])

        assert result["status"] == "failed"
        # Step 0 tried twice (original + retry)
        assert call_count[0] == 2

    @patch.object(
        __import__("agent.subconscious.loops.task_planner", fromlist=["TaskPlanner"]).TaskPlanner,
        "_call_model",
        _mock_call_model,
    )
    def test_stats_after_execution(self):
        """Stats reflect completed tasks."""
        from agent.subconscious.loops.task_planner import TaskPlanner, create_task

        tp = TaskPlanner(interval=999, enabled=False)
        task = create_task("Stats test", source="test")
        tp.execute_task(task["id"])

        stats = tp.stats
        assert stats["tasks_completed"] >= 1
        assert stats["currently_executing"] is None


# ===================================================================
# 4. Context Gathering
# ===================================================================

class TestGatherContext:
    """_gather_context collects tools, identity, recent convos."""

    def test_gather_context_returns_dict(self):
        tp = _tp()
        ctx = tp._gather_context("Test goal")
        assert isinstance(ctx, dict)
        assert "summary" in ctx
        assert "tools" in ctx
        assert "identity" in ctx
        assert "recent" in ctx
        assert "Goal: Test goal" in ctx["summary"]

    def test_gather_context_survives_import_errors(self):
        """Even when imports fail, _gather_context produces a usable context."""
        tp = _tp()
        with patch("agent.threads.form.tools.registry.get_available_tools", side_effect=ImportError):
            ctx = tp._gather_context("Test goal")
        assert "summary" in ctx
        assert ctx["tools_prompt"] == "No tools available."


# ===================================================================
# 5. Live Pipeline (--live or AIOS_TEST_LIVE=1)
# ===================================================================

class TestLiveTaskPipeline:
    """End-to-end task pipeline against a real LLM.

    Requires:
        pytest --live
        # or
        AIOS_TEST_LIVE=1 pytest tests/test_task_planner.py

    Optionally configure:
        AIOS_EXTRACT_PROVIDER=openai
        OPENAI_BASE_URL=https://api.moonshot.cn/v1   # kimi k2
        OPENAI_API_KEY=sk-...
        AIOS_MODEL_NAME=kimi-k2
    """

    @pytest.mark.skipif(
        not os.environ.get("AIOS_TEST_LIVE"),
        reason="Live task pipeline requires --live flag or AIOS_TEST_LIVE=1",
    )
    def test_live_simple_task(self, live_mode):
        """Create and execute a simple task with a real LLM."""
        if not live_mode:
            pytest.skip("requires --live")

        from agent.subconscious.loops.task_planner import TaskPlanner, create_task, get_task

        tp = TaskPlanner(interval=999, enabled=False)

        task = create_task("List 3 benefits of open-source software", source="live_test")
        result = tp.execute_task(task["id"])

        # Verify pipeline completed
        assert result["status"] in ("completed", "failed"), f"Unexpected status: {result['status']}"

        if result["status"] == "completed":
            assert len(result["steps"]) >= 1, "Should have at least 1 step"
            assert len(result["results"]) >= 2, "Should have step results + summary"
            # Summary should be a real sentence
            summary = result["results"][-1].get("output", "")
            assert len(summary) > 20, f"Summary too short: {summary}"
            print(f"\n[LIVE] Task completed with {len(result['steps'])} steps")
            print(f"[LIVE] Summary: {summary[:200]}")
        else:
            # Even failures should have partial info
            print(f"\n[LIVE] Task failed. Results: {json.dumps(result['results'], indent=2)[:500]}")
            assert len(result["results"]) >= 1

    @pytest.mark.skipif(
        not os.environ.get("AIOS_TEST_LIVE"),
        reason="Live task pipeline requires --live flag or AIOS_TEST_LIVE=1",
    )
    def test_live_plan_quality(self, live_mode):
        """Verify that the LLM produces reasonable step plans."""
        if not live_mode:
            pytest.skip("requires --live")

        from agent.subconscious.loops.task_planner import TaskPlanner

        tp = TaskPlanner(interval=999, enabled=False)
        ctx = tp._gather_context("Write a haiku about programming")
        steps = tp._plan_steps("Write a haiku about programming", ctx)

        assert isinstance(steps, list)
        assert len(steps) >= 1, "LLM should produce at least 1 step"
        assert len(steps) <= 6, "Steps should be capped at 6"

        for step in steps:
            assert "description" in step
            assert "tool" in step
            assert len(step["description"]) > 5, f"Step description too short: {step['description']}"

        print(f"\n[LIVE] Plan produced {len(steps)} steps:")
        for s in steps:
            print(f"  [{s['tool']}] {s['description']}")
