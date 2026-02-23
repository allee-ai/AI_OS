"""
Tests for Subconscious Visibility & Editability
================================================
Covers the new fact review queue (approve/reject/edit/delete),
loop configuration (interval, pause/resume, model),
unprocessed conversation queue tracking, and API endpoints.

Run: pytest tests/test_subconscious_visibility.py -v
"""

import os
import sys
import sqlite3
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import closing

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("AIOS_MODE", "demo")


# ─────────────────────────────────────────────────────────────
# Temp Fact CRUD — update_fact_text, delete_fact
# ─────────────────────────────────────────────────────────────

class TestUpdateFactText:
    """Test editing a fact's text before it enters long-term memory."""

    def test_update_existing_fact(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_text, get_facts
        f = add_fact("vis-edit", "Original text", source="test")
        ok = update_fact_text(f.id, "Corrected text")
        assert ok is True
        # Verify updated
        facts = get_facts(limit=100, include_consolidated=True)
        found = [x for x in facts if x.id == f.id]
        assert len(found) == 1
        assert found[0].text == "Corrected text"

    def test_update_nonexistent_fact(self):
        from agent.subconscious.temp_memory import update_fact_text
        ok = update_fact_text(999999, "New text")
        assert ok is False

    def test_update_empty_text_raises(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_text
        f = add_fact("vis-empty", "Some fact", source="test")
        with pytest.raises(ValueError, match="empty"):
            update_fact_text(f.id, "")

    def test_update_whitespace_only_raises(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_text
        f = add_fact("vis-ws", "Some fact", source="test")
        with pytest.raises(ValueError, match="empty"):
            update_fact_text(f.id, "   ")

    def test_update_strips_whitespace(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_text, get_facts
        f = add_fact("vis-strip", "Orig", source="test")
        update_fact_text(f.id, "  Trimmed text  ")
        facts = get_facts(limit=100, include_consolidated=True)
        found = [x for x in facts if x.id == f.id]
        assert found[0].text == "Trimmed text"


class TestDeleteFact:
    """Test deleting a fact from temp memory."""

    def test_delete_existing_fact(self):
        from agent.subconscious.temp_memory import add_fact, delete_fact, get_facts
        f = add_fact("vis-del", "To be deleted", source="test")
        ok = delete_fact(f.id)
        assert ok is True
        facts = get_facts(limit=100, include_consolidated=True)
        assert not any(x.id == f.id for x in facts)

    def test_delete_nonexistent_fact(self):
        from agent.subconscious.temp_memory import delete_fact
        ok = delete_fact(999999)
        assert ok is False


# ─────────────────────────────────────────────────────────────
# Fact Review Workflow — approve, reject via API store functions
# ─────────────────────────────────────────────────────────────

class TestFactReviewWorkflow:
    """End-to-end fact review: create → edit → approve/reject."""

    def test_approve_flow(self):
        from agent.subconscious.temp_memory import add_fact, update_fact_text, approve_fact, get_facts
        f = add_fact("vis-flow-a", "User likes dogs", source="test")
        update_fact_text(f.id, "User prefers large dogs")
        approve_fact(f.id)
        facts = get_facts(limit=100, include_consolidated=True)
        found = [x for x in facts if x.id == f.id]
        assert found[0].status == "approved"
        assert found[0].text == "User prefers large dogs"

    def test_reject_flow(self):
        from agent.subconscious.temp_memory import add_fact, reject_fact, get_facts
        f = add_fact("vis-flow-r", "Junk fact", source="test")
        reject_fact(f.id)
        facts = get_facts(limit=100, include_consolidated=True)
        found = [x for x in facts if x.id == f.id]
        assert found[0].status == "rejected"

    def test_edit_then_approve(self):
        from agent.subconscious.temp_memory import (
            add_fact, update_fact_text, approve_fact, get_approved_pending
        )
        f = add_fact("vis-flow-ea", "Wrong text", source="test")
        update_fact_text(f.id, "Corrected text here")
        approve_fact(f.id)
        approved = get_approved_pending()
        found = [x for x in approved if x.id == f.id]
        assert len(found) == 1
        assert found[0].text == "Corrected text here"


# ─────────────────────────────────────────────────────────────
# MemoryLoop — model property, persisted turn_id, unprocessed
# ─────────────────────────────────────────────────────────────

class TestMemoryLoopModel:
    """Test model selection on the memory loop."""

    def test_default_model(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=60.0)
        # Should fall back to env or default
        model = loop.model
        assert isinstance(model, str)
        assert len(model) > 0

    def test_set_model(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=60.0)
        loop.model = "llama3:8b"
        assert loop.model == "llama3:8b"

    def test_model_in_stats(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=60.0, model="mistral:7b")
        stats = loop.stats
        assert stats["model"] == "mistral:7b"

    def test_model_init_param(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=30.0, model="phi3:mini")
        assert loop.model == "phi3:mini"

    def test_env_fallback(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=60.0)
        loop._model = None  # Clear any override
        with patch.dict(os.environ, {"AIOS_EXTRACT_MODEL": "gemma2:9b"}):
            assert loop.model == "gemma2:9b"


class TestMemoryLoopTurnTracking:
    """Test that _last_processed_turn_id persists and unprocessed count works."""

    def test_save_and_load_turn_id(self):
        from agent.subconscious.loops import MemoryLoop
        loop1 = MemoryLoop(interval=60.0)
        loop1._save_last_turn_id(42)
        # New loop should load the saved value
        loop2 = MemoryLoop(interval=60.0)
        loaded = loop2._load_last_turn_id()
        assert loaded == 42

    def test_unprocessed_count_is_int(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=60.0)
        count = loop.get_unprocessed_count()
        assert isinstance(count, int)
        assert count >= 0

    def test_stats_include_unprocessed(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=60.0)
        stats = loop.stats
        assert "unprocessed_turns" in stats
        assert "last_processed_turn_id" in stats
        assert isinstance(stats["unprocessed_turns"], int)


# ─────────────────────────────────────────────────────────────
# Loop Config — interval update, pause/resume
# ─────────────────────────────────────────────────────────────

class TestLoopConfigEditing:
    """Test editing loop intervals and pause/resume."""

    def test_update_interval(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=60.0)
        assert loop.config.interval_seconds == 60.0
        loop.config.interval_seconds = 30.0
        assert loop.config.interval_seconds == 30.0

    def test_pause_and_resume(self):
        from agent.subconscious.loops import MemoryLoop, LoopStatus
        loop = MemoryLoop(interval=9999)  # Long interval so it doesn't fire
        loop.start()
        assert loop.status == LoopStatus.RUNNING
        loop.pause()
        assert loop.status == LoopStatus.PAUSED
        loop.resume()
        assert loop.status == LoopStatus.RUNNING
        loop.stop()
        assert loop.status == LoopStatus.STOPPED

    def test_interval_change_reflected_in_stats(self):
        from agent.subconscious.loops import MemoryLoop
        loop = MemoryLoop(interval=120.0)
        loop.config.interval_seconds = 45.0
        stats = loop.stats
        assert stats["interval"] == 45.0


# ─────────────────────────────────────────────────────────────
# API Endpoint Tests (via FastAPI TestClient)
# ─────────────────────────────────────────────────────────────

class TestFactAPIEndpoints:
    """Test the new temp-facts REST endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Create test client and seed a test fact."""
        from fastapi.testclient import TestClient
        from agent.subconscious.api import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        
        # Seed a fact
        from agent.subconscious.temp_memory import add_fact
        self.fact = add_fact("api-test", "User likes coffee", source="test")

    def test_get_temp_facts(self):
        res = self.client.get("/api/subconscious/temp-facts")
        assert res.status_code == 200
        data = res.json()
        assert "stats" in data
        assert "recent" in data

    def test_approve_fact(self):
        res = self.client.post(f"/api/subconscious/temp-facts/{self.fact.id}/approve")
        assert res.status_code == 200
        assert res.json()["status"] == "approved"

    def test_reject_fact(self):
        from agent.subconscious.temp_memory import add_fact
        f = add_fact("api-rej", "Junk", source="test")
        res = self.client.post(f"/api/subconscious/temp-facts/{f.id}/reject")
        assert res.status_code == 200
        assert res.json()["status"] == "rejected"

    def test_edit_fact(self):
        res = self.client.put(
            f"/api/subconscious/temp-facts/{self.fact.id}",
            json={"text": "User prefers espresso"}
        )
        assert res.status_code == 200
        assert res.json()["text"] == "User prefers espresso"

    def test_edit_fact_empty_text(self):
        res = self.client.put(
            f"/api/subconscious/temp-facts/{self.fact.id}",
            json={"text": ""}
        )
        assert res.status_code == 400

    def test_delete_fact(self):
        from agent.subconscious.temp_memory import add_fact
        f = add_fact("api-del", "Temp fact", source="test")
        res = self.client.delete(f"/api/subconscious/temp-facts/{f.id}")
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

    def test_approve_nonexistent(self):
        res = self.client.post("/api/subconscious/temp-facts/999999/approve")
        assert res.status_code == 404

    def test_approve_all(self):
        res = self.client.post("/api/subconscious/temp-facts/approve-all")
        assert res.status_code == 200
        assert "approved" in res.json()

    def test_reject_all(self):
        res = self.client.post("/api/subconscious/temp-facts/reject-all")
        assert res.status_code == 200
        assert "rejected" in res.json()


class TestQueueAPI:
    """Test the /queue endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from agent.subconscious.api import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_queue_endpoint(self):
        res = self.client.get("/api/subconscious/queue")
        assert res.status_code == 200
        data = res.json()
        assert "unprocessed" in data
        assert "total_turns" in data
        assert isinstance(data["unprocessed"], int)
