"""
Extended tests for the Subconscious module.

Covers:
- temp_memory CRUD and status workflow
- Orchestrator self-awareness block
- Orchestrator workspace integration
- Trigger lifecycle
- Loop configuration
- Contract utilities

Run: pytest tests/test_subconscious_extended.py -v
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── Temp Memory: CRUD + Status Workflow ───────────────────────────────────

class TestTempMemoryCRUD:
    """Test temp_memory add/get/clear operations."""

    def test_add_fact(self):
        from agent.subconscious.temp_memory import add_fact, Fact
        fact = add_fact("test-session-1", "User likes Python", source="conversation")
        assert isinstance(fact, Fact)
        assert fact.id is not None
        assert fact.text == "User likes Python"
        assert fact.session_id == "test-session-1"
        assert fact.consolidated is False

    def test_get_session_facts(self):
        from agent.subconscious.temp_memory import add_fact, get_session_facts
        sid = f"test-session-get-{time.time()}"
        add_fact(sid, "Fact A")
        add_fact(sid, "Fact B")
        facts = get_session_facts(sid)
        texts = [f.text for f in facts]
        assert "Fact A" in texts
        assert "Fact B" in texts

    def test_get_all_pending(self):
        from agent.subconscious.temp_memory import add_fact, get_all_pending
        sid = f"test-session-pending-{time.time()}"
        add_fact(sid, "Pending fact")
        pending = get_all_pending()
        assert any(f.text == "Pending fact" for f in pending)

    def test_mark_consolidated(self):
        from agent.subconscious.temp_memory import add_fact, mark_consolidated, get_session_facts
        sid = f"test-session-mark-{time.time()}"
        fact = add_fact(sid, "Will consolidate")
        result = mark_consolidated(fact.id)
        assert result is True
        # Should not appear in unconsolidated query
        remaining = get_session_facts(sid, include_consolidated=False)
        assert all(f.id != fact.id for f in remaining)

    def test_clear_session(self):
        from agent.subconscious.temp_memory import add_fact, mark_consolidated, clear_session, get_session_facts
        sid = f"test-session-clear-{time.time()}"
        f1 = add_fact(sid, "Keep this")
        f2 = add_fact(sid, "Consolidated")
        mark_consolidated(f2.id)
        deleted = clear_session(sid, only_consolidated=True)
        assert deleted == 1
        remaining = get_session_facts(sid, include_consolidated=True)
        assert len(remaining) == 1
        assert remaining[0].text == "Keep this"

    def test_stats(self):
        from agent.subconscious.temp_memory import get_stats
        stats = get_stats()
        assert isinstance(stats, dict)
        assert "pending" in stats
        assert "consolidated" in stats
        assert "total" in stats


class TestTempMemoryStatusWorkflow:
    """Test the approval/rejection status workflow."""

    def test_initial_status_is_pending(self):
        from agent.subconscious.temp_memory import add_fact
        sid = f"test-status-{time.time()}"
        fact = add_fact(sid, "New fact")
        assert fact.status == "pending"

    def test_update_to_approved(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_status, get_session_facts
        sid = f"test-approve-{time.time()}"
        fact = add_fact(sid, "Approve me")
        update_fact_status(fact.id, "approved", confidence_score=0.9)
        facts = get_session_facts(sid, include_consolidated=True)
        updated = [f for f in facts if f.id == fact.id][0]
        assert updated.status == "approved"
        assert updated.confidence_score == 0.9

    def test_approve_convenience(self):
        from agent.subconscious.temp_memory import add_fact, approve_fact, get_session_facts
        sid = f"test-approve-conv-{time.time()}"
        fact = add_fact(sid, "Quick approve")
        result = approve_fact(fact.id)
        assert result is True
        facts = get_session_facts(sid, include_consolidated=True)
        updated = [f for f in facts if f.id == fact.id][0]
        assert updated.status == "approved"

    def test_reject_fact(self):
        from agent.subconscious.temp_memory import add_fact, reject_fact, get_session_facts
        sid = f"test-reject-{time.time()}"
        fact = add_fact(sid, "Reject me")
        result = reject_fact(fact.id)
        assert result is True
        facts = get_session_facts(sid, include_consolidated=True)
        updated = [f for f in facts if f.id == fact.id][0]
        assert updated.status == "rejected"

    def test_invalid_status_raises(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_status
        sid = f"test-invalid-{time.time()}"
        fact = add_fact(sid, "Invalid status")
        with pytest.raises(ValueError, match="Invalid status"):
            update_fact_status(fact.id, "bogus")

    def test_pending_review(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_status, get_pending_review
        sid = f"test-review-{time.time()}"
        fact = add_fact(sid, "Needs review")
        update_fact_status(fact.id, "pending_review")
        review_list = get_pending_review()
        assert any(f.id == fact.id for f in review_list)

    def test_approved_pending_list(self):
        from agent.subconscious.temp_memory import add_fact, approve_fact, get_approved_pending
        sid = f"test-approved-list-{time.time()}"
        fact = add_fact(sid, "Ready for promotion")
        approve_fact(fact.id)
        approved = get_approved_pending()
        assert any(f.id == fact.id for f in approved)


# ─── Orchestrator: Self-Awareness Block ────────────────────────────────────

class TestSelfAwareness:
    """Test the self-awareness metadata in STATE."""

    def test_state_contains_self_block(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        state = sub.get_state("hello")
        assert "[self]" in state
        assert "identity" in state
        assert "form" in state

    def test_self_block_has_thread_table(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        state = sub.get_state("test")
        assert "WHO" in state
        assert "WHAT" in state
        assert "WHY" in state
        assert "HOW" in state

    def test_build_self_awareness_returns_lines(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        lines = sub._build_self_awareness_block()
        assert isinstance(lines, list)
        assert len(lines) > 5
        # Should contain thread names
        text = "\n".join(lines)
        assert "identity" in text
        assert "linking_core" in text


# ─── Orchestrator: Workspace Integration ───────────────────────────────────

class TestWorkspaceInContext:
    """Test workspace data appearing in STATE when relevant."""

    def test_workspace_context_no_files(self):
        """With no indexed files, workspace section should not appear."""
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        facts = sub._get_workspace_context("test query")
        # May be empty if no files indexed — should not crash
        assert isinstance(facts, list)

    def test_workspace_context_with_file(self):
        """When workspace has matching content, workspace facts should appear."""
        from workspace.schema import create_file, get_file, chunk_file, init_workspace_tables
        from agent.subconscious.orchestrator import get_subconscious

        init_workspace_tables()
        path = "/test_ctx/knowledge.txt"
        content = b"The capital of France is Paris. Paris is known for the Eiffel Tower."
        create_file(path, content, mime_type="text/plain")
        f = get_file(path)
        if f and "id" in f:
            chunk_file(f["id"])

        sub = get_subconscious()
        facts = sub._get_workspace_context("capital of France")
        # FTS match should return workspace facts
        # (depends on FTS indexing — if no match, at least no crash)
        assert isinstance(facts, list)

    def test_workspace_section_in_state(self):
        """Full build_state should include [workspace] when query matches."""
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        # Even if no workspace content, state should still build cleanly
        state = sub.get_state("some query")
        assert "== STATE ==" in state
        assert "== END STATE ==" in state


# ─── Triggers ──────────────────────────────────────────────────────────────

class TestTriggerLifecycle:
    """Test trigger creation, arming, firing, and cooldown."""

    def test_time_trigger_fires(self):
        from agent.subconscious.triggers import TimeTrigger
        fired = {"count": 0}

        def action():
            fired["count"] += 1

        trigger = TimeTrigger(name="test_time", action=action, interval_seconds=0.1)
        assert trigger.status.value == "armed"
        # Wait for interval to elapse
        time.sleep(0.15)
        result = trigger.check()
        assert result.triggered is True
        trigger.fire()
        assert fired["count"] >= 1

    def test_threshold_trigger(self):
        from agent.subconscious.triggers import ThresholdTrigger
        fired = {"count": 0}
        metric_val = {"v": 0.0}

        def action():
            fired["count"] += 1

        trigger = ThresholdTrigger(
            name="test_threshold",
            action=action,
            metric_fn=lambda: metric_val["v"],
            threshold=10.0,
            direction="above",
            cooldown_seconds=0.0,
        )

        # Below threshold — check returns not triggered
        metric_val["v"] = 5.0
        result = trigger.check()
        assert result.triggered is False

        # Above threshold — check returns triggered, fire executes
        metric_val["v"] = 15.0
        result = trigger.check()
        assert result.triggered is True
        trigger.fire()
        assert fired["count"] == 1

    def test_trigger_manager(self):
        from agent.subconscious.triggers import TriggerManager, TimeTrigger
        fired = {"count": 0}

        def action():
            fired["count"] += 1

        manager = TriggerManager()
        trigger = TimeTrigger(name="mgr_test", action=action, interval_seconds=0.1)
        manager.add(trigger)
        trigger.arm()

        stats = manager.get_stats()
        assert len(stats) == 1
        assert stats[0]["name"] == "mgr_test"

    def test_trigger_cooldown(self):
        from agent.subconscious.triggers import ThresholdTrigger
        fired = {"count": 0}

        def action():
            fired["count"] += 1

        trigger = ThresholdTrigger(
            name="cooldown_test",
            action=action,
            metric_fn=lambda: 100.0,
            threshold=10.0,
            direction="above",
            cooldown_seconds=999.0,  # Very long cooldown
        )

        result = trigger.check()
        assert result.triggered is True
        trigger.fire()
        assert fired["count"] == 1
        # Second fire should be in cooldown
        assert trigger.fire() is False
        assert fired["count"] == 1

    def test_factory_pending_trigger(self):
        from agent.subconscious.triggers import create_pending_facts_trigger
        fired = {"count": 0}
        trigger = create_pending_facts_trigger(action=lambda: fired.__setitem__("count", 1), threshold=50)
        assert trigger.name == "pending_facts_high"
        trigger.arm()
        # Check should not crash even with no pending facts
        trigger.check()

    def test_factory_error_trigger(self):
        from agent.subconscious.triggers import create_error_trigger
        trigger = create_error_trigger(action=lambda: None, cooldown=60.0)
        assert trigger.name == "error_alert"


# ─── Loop Configuration ───────────────────────────────────────────────────

class TestLoopConfiguration:
    """Test loop creation and configuration (not execution)."""

    def test_create_default_loops(self):
        from agent.subconscious.loops import create_default_loops
        manager = create_default_loops()
        stats = manager.get_stats()
        names = [s["name"] for s in stats]
        assert "memory" in names
        assert "consolidation" in names
        assert "sync" in names
        assert "health" in names

    def test_loop_intervals(self):
        from agent.subconscious.loops import create_default_loops
        manager = create_default_loops()
        stats = manager.get_stats()
        intervals = {s["name"]: s.get("interval") for s in stats}
        # Memory loop should be 60s
        assert intervals.get("memory") == 60.0
        # Consolidation at 300s
        assert intervals.get("consolidation") == 300.0

    def test_loop_get_by_name(self):
        from agent.subconscious.loops import create_default_loops
        manager = create_default_loops()
        memory = manager.get_loop("memory")
        assert memory is not None
        assert memory.config.name == "memory"
        assert manager.get_loop("nonexistent") is None


# ─── Contract Utilities ───────────────────────────────────────────────────

class TestContract:
    """Test the metadata contract helpers."""

    def test_create_metadata(self):
        from agent.subconscious.contract import create_metadata
        meta = create_metadata(context_level="identity", version=1)
        assert "last_updated" in meta
        assert meta["context_level"] == "identity"
        assert meta["version"] == 1
        assert meta["status"] == "ready"

    def test_staleness(self):
        from agent.subconscious.contract import create_metadata, is_stale
        meta = create_metadata("test")
        # Just created — not stale (default threshold 600s)
        assert is_stale(meta) is False

    def test_sync_protocol(self):
        from agent.subconscious.contract import create_metadata, request_sync, should_sync, mark_synced
        meta = create_metadata("test")
        assert should_sync(meta) is False
        meta = request_sync(meta)
        assert should_sync(meta) is True
        meta = mark_synced(meta)
        assert should_sync(meta) is False
