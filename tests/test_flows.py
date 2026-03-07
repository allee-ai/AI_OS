"""
Flow tests — end-to-end pipelines through the real demo DB.

Every test works with the mock ``ollama.chat`` by default.
Run ``pytest --live`` to use a real Ollama instance instead.

Flows tested:
  1. Memory pipeline    (message → extract → temp_memory → approve)
  2. Reflex pipeline    (create trigger → emit event → dispatch by response_mode)
  3. Chat round-trip    (send_message → context assembly → response → DB persist)
  4. Feed pipeline      (emit → dedup → handler callback)
  5. Concept learning   (record concepts → graph links → spread_activate retrieval)
"""

import asyncio
import json
import pytest
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ===================================================================
# 1. Memory Pipeline
# ===================================================================

class TestMemoryPipeline:
    """message → MemoryLoop extract → temp_memory → approve."""

    def test_add_fact_persists(self):
        from agent.subconscious.temp_memory.store import add_fact, get_facts

        fact = add_fact(
            session_id="test_flow",
            text="User likes Python",
            source="test",
            metadata={"hier_key": "user.preference.python"},
        )
        assert fact.id is not None
        assert fact.text == "User likes Python"

        # Should appear in get_facts
        facts = get_facts(limit=200)
        ids = [f.id for f in facts]
        assert fact.id in ids

    def test_extract_facts_from_text(self):
        """MemoryLoop._extract_facts_from_text returns parsed facts (mock or live)."""
        from agent.subconscious.loops import MemoryLoop

        ml = MemoryLoop.__new__(MemoryLoop)
        ml._model = None

        facts = ml._extract_facts_from_text(
            "I'm building a project called TaskMaster and I love coffee while coding.",
            session_id="test_flow",
        )
        assert isinstance(facts, list)
        # Mock returns 1 fact; live may return more
        assert len(facts) >= 1
        assert "key" in facts[0]
        assert "text" in facts[0]

    def test_extracted_keys_are_flat(self):
        """Fact keys should be flat labels, not hierarchical dot-paths."""
        from agent.subconscious.loops import MemoryLoop

        ml = MemoryLoop.__new__(MemoryLoop)
        ml._model = None

        facts = ml._extract_facts_from_text(
            "User: My name is Jordan and I work at Acme Corp as a software engineer.",
            session_id="test_flat_keys",
        )
        assert isinstance(facts, list)
        for f in facts:
            key = f.get("key", "")
            # Keys must not contain dots (flat, not hierarchical)
            assert "." not in key, f"Key should be flat, got: {key}"

    def test_validate_fact_strips_hierarchy(self):
        """_validate_fact normalises dotted keys to their final segment."""
        from agent.subconscious.loops import MemoryLoop

        ml = MemoryLoop.__new__(MemoryLoop)
        ml._model = None

        fact = {"key": "user.preference.coffee", "text": "User enjoys coffee while coding"}
        result = ml._validate_fact(fact)
        assert result is True
        assert fact["key"] == "coffee", f"Expected 'coffee', got '{fact['key']}'"

    def test_extract_with_cloud_model(self, live_mode):
        """Extract facts using a cloud model (only runs with --live)."""
        if not live_mode:
            pytest.skip("cloud test requires --live")

        from agent.subconscious.loops import MemoryLoop
        import os

        ml = MemoryLoop.__new__(MemoryLoop)
        # Use a cloud model available in ollama list
        ml._model = os.environ.get("AIOS_EXTRACT_MODEL", "gpt-oss:20b-cloud")

        facts = ml._extract_facts_from_text(
            "User: I'm a machine learning engineer and I love hiking on weekends.",
            session_id="test_cloud",
        )
        assert isinstance(facts, list)
        assert len(facts) >= 1
        for f in facts:
            assert "." not in f.get("key", ""), f"Cloud model key should be flat: {f.get('key')}"
            assert len(f.get("text", "")) >= 10

    def test_call_model_provider_routing(self):
        """_call_model routes to the correct provider based on env."""
        from agent.subconscious.loops import MemoryLoop
        import os

        ml = MemoryLoop.__new__(MemoryLoop)
        ml._model = None

        # Default provider should be ollama
        assert ml.provider == os.environ.get(
            "AIOS_EXTRACT_PROVIDER",
            os.environ.get("AIOS_MODEL_PROVIDER", "ollama")
        ).lower()

    def test_approve_fact(self):
        from agent.subconscious.temp_memory.store import add_fact, approve_fact, get_facts

        fact = add_fact(
            session_id="test_flow_approve",
            text="User prefers dark mode",
            source="test",
        )
        result = approve_fact(fact.id)
        assert result is True

    def test_reject_fact(self):
        from agent.subconscious.temp_memory.store import add_fact, reject_fact

        fact = add_fact(
            session_id="test_flow_reject",
            text="Noise data",
            source="test",
        )
        result = reject_fact(fact.id)
        assert result is True

    def test_stats_reflect_additions(self):
        from agent.subconscious.temp_memory.store import get_stats

        stats = get_stats()
        assert isinstance(stats, dict)
        assert "total" in stats or "count" in stats or len(stats) > 0


# ===================================================================
# 2. Reflex Pipeline
# ===================================================================

class TestReflexPipeline:
    """create trigger → emit event → dispatch by response_mode."""

    def _cleanup_trigger(self, trigger_id):
        from agent.threads.reflex.schema import delete_trigger
        delete_trigger(trigger_id)

    def test_create_trigger_with_response_mode(self):
        from agent.threads.reflex.schema import create_trigger, get_trigger

        tid = create_trigger(
            name="test_agent_mode",
            feed_name="email",
            event_type="email_received",
            tool_name="",
            tool_action="",
            response_mode="agent",
        )
        try:
            trigger = get_trigger(tid)
            assert trigger is not None
            assert trigger["response_mode"] == "agent"
            assert trigger["enabled"] == 1
        finally:
            self._cleanup_trigger(tid)

    def test_tool_mode_dispatch(self):
        """Tool-mode trigger calls execute_tool_action."""
        from agent.threads.reflex.schema import create_trigger
        from agent.threads.reflex.executor import execute_matching_triggers

        tid = create_trigger(
            name="test_tool_dispatch",
            feed_name="test_feed",
            event_type="test_event",
            tool_name="web_search",
            tool_action="search",
            response_mode="tool",
        )
        try:
            results = _run(execute_matching_triggers(
                feed_name="test_feed",
                event_type="test_event",
                event_payload={"query": "hello"},
            ))
            assert len(results) >= 1
            r = [r for r in results if r["trigger_id"] == tid][0]
            assert r["status"] in ("executed", "failed")
        finally:
            self._cleanup_trigger(tid)

    def test_notify_mode_dispatch(self):
        from agent.threads.reflex.schema import create_trigger
        from agent.threads.reflex.executor import execute_matching_triggers

        tid = create_trigger(
            name="test_notify_dispatch",
            feed_name="test_feed_n",
            event_type="test_event_n",
            tool_name="",
            tool_action="",
            response_mode="notify",
        )
        try:
            results = _run(execute_matching_triggers(
                feed_name="test_feed_n",
                event_type="test_event_n",
                event_payload={"info": "something happened"},
            ))
            assert len(results) >= 1
            r = [r for r in results if r["trigger_id"] == tid][0]
            assert r["status"] == "executed"
        finally:
            self._cleanup_trigger(tid)

    def test_condition_filters_mismatch(self):
        from agent.threads.reflex.schema import create_trigger
        from agent.threads.reflex.executor import execute_matching_triggers

        tid = create_trigger(
            name="test_cond_filter",
            feed_name="test_cond",
            event_type="test_cond_ev",
            tool_name="web_search",
            tool_action="search",
            condition={"field": "payload.subject", "operator": "contains", "value": "urgent"},
            response_mode="tool",
        )
        try:
            # Non-matching payload → should be skipped
            results = _run(execute_matching_triggers(
                feed_name="test_cond",
                event_type="test_cond_ev",
                event_payload={"payload": {"subject": "meeting notes"}},
            ))
            assert len(results) >= 1
            r = [r for r in results if r["trigger_id"] == tid][0]
            assert r["status"] == "skipped"
        finally:
            self._cleanup_trigger(tid)

    def test_protocol_install(self):
        """Protocol template creates trigger bundle."""
        from agent.threads.reflex.api import PROTOCOL_TEMPLATES
        from agent.threads.reflex.schema import create_trigger, get_trigger, delete_trigger

        template = PROTOCOL_TEMPLATES["morning_briefing"]
        created = []
        try:
            for trig_def in template:
                tid = create_trigger(
                    name=trig_def["name"],
                    feed_name=trig_def["feed_name"],
                    event_type=trig_def["event_type"],
                    tool_name=trig_def.get("tool_name", ""),
                    tool_action=trig_def.get("tool_action", ""),
                    trigger_type=trig_def.get("trigger_type", "webhook"),
                    cron_expression=trig_def.get("cron_expression"),
                    response_mode=trig_def.get("response_mode", "tool"),
                    priority=trig_def.get("priority", 5),
                )
                created.append(tid)

            for tid in created:
                t = get_trigger(tid)
                assert t is not None
                assert t["response_mode"] == "agent"
        finally:
            for tid in created:
                delete_trigger(tid)


# ===================================================================
# 3. Chat Round-Trip
# ===================================================================

class TestChatRoundTrip:
    """send_message → context assembly → response → DB persist."""

    def test_send_message_returns_response(self, agent_service):
        msg = _run(agent_service.send_message("Hello, what is your name?"))
        assert msg is not None
        assert msg.role == "assistant"
        assert len(msg.content) > 0

    def test_message_history_grows(self, agent_service):
        _run(agent_service.send_message("First message"))
        _run(agent_service.send_message("Second message"))
        # Should have at least 4 entries (2 user + 2 assistant)
        assert len(agent_service.message_history) >= 4

    def test_conversation_persisted_to_db(self, agent_service):
        _run(agent_service.send_message("Persist this"))
        try:
            from chat.schema import get_conversation
            convo = get_conversation(agent_service.session_id)
            assert convo is not None
        except ImportError:
            pytest.skip("chat.schema not available")

    def test_context_assembly_runs(self, agent_service):
        """Agent should have consciousness context assembled."""
        # After a message, the agent should have been called with context
        assert agent_service.agent is not None
        # The subconscious should be awake
        try:
            from agent.subconscious.orchestrator import get_subconscious
            sub = get_subconscious()
            state = sub.build_context(level=2)
            # build_context may return a string or a dict
            assert state is not None
            assert len(str(state)) > 0
        except ImportError:
            pytest.skip("subconscious not available")


# ===================================================================
# 4. Feed Pipeline
# ===================================================================

class TestFeedPipeline:
    """emit → dedup → handler callback."""

    def test_emit_event_returns_feed_event(self):
        from Feeds.events import emit_event, EventPriority

        event = emit_event(
            feed_name="test",
            event_type="test_ping",
            payload={"msg": "hello"},
            priority=EventPriority.NORMAL,
            event_id="test_001",
        )
        assert event.feed_name == "test"
        assert event.event_type == "test_ping"
        assert event.payload["msg"] == "hello"

    def test_dedup_rejects_duplicate(self):
        from Feeds.polling import _is_new

        # First time → new
        assert _is_new("test_dedup", "unique_id_abc") is True
        # Second time → duplicate
        assert _is_new("test_dedup", "unique_id_abc") is False

    def test_handler_receives_event(self):
        from Feeds.events import emit_event, register_handler

        received = []
        register_handler(lambda ev: received.append(ev), feed_name="test_handler_feed", event_type="ping")

        emit_event(
            feed_name="test_handler_feed",
            event_type="ping",
            payload={"data": 1},
        )
        assert len(received) == 1
        assert received[0].event_type == "ping"

    def test_event_logged(self):
        """Emitted events should be logged to the event log."""
        from Feeds.events import emit_event

        # This should not raise even if log thread is unavailable
        event = emit_event(
            feed_name="test_log",
            event_type="log_test",
            payload={"check": True},
            event_id="log_test_001",
        )
        assert event is not None


# ===================================================================
# 5. Concept Learning
# ===================================================================

class TestConceptLearning:
    """record concepts → graph links → spread_activate retrieval."""

    def test_extract_concepts_from_text(self):
        from agent.threads.linking_core.schema import extract_concepts_from_text

        concepts = extract_concepts_from_text("python programming and machine learning")
        assert isinstance(concepts, list)
        assert len(concepts) >= 1

    def test_create_and_retrieve_link(self):
        from agent.threads.linking_core.schema import create_link, get_links_for_concept

        create_link("test_coffee", "test_coding", strength=0.8)
        links = get_links_for_concept("test_coffee")
        targets = [l["concept"] for l in links]
        assert "test_coding" in targets

    def test_spread_activate_from_seed(self):
        from agent.threads.linking_core.schema import create_link, spread_activate

        # Build a small graph
        create_link("test_python", "test_backend", strength=0.9)
        create_link("test_backend", "test_api", strength=0.7)

        scores = spread_activate(["test_python"], max_hops=2)
        assert isinstance(scores, list)
        # Direct neighbor should be activated
        concepts = [s["concept"] for s in scores]
        assert "test_backend" in concepts

    def test_record_conversation_concepts(self):
        from agent.threads.linking_core.schema import (
            extract_and_record_conversation_concepts,
        )

        messages = [
            {"role": "user", "content": "I use Python for data science projects"},
            {"role": "assistant", "content": "Python is great for data science!"},
        ]
        extract_and_record_conversation_concepts(messages)

        # Should have created some links (concepts co-occur)
        # We check that the function ran without error — exact links depend on extraction
        # In live mode this will create real concept links
        assert True  # no exception = pass
