"""
Tests for Custom Chain-of-Thought Loops
========================================
Covers CustomLoop class, DB persistence, CRUD functions,
LoopManager integration, and API endpoints.

Run: pytest tests/test_custom_loops.py -v
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("AIOS_MODE", "demo")


# ─────────────────────────────────────────────────────────────
# CustomLoop Class — creation, properties, stats
# ─────────────────────────────────────────────────────────────

class TestCustomLoopInit:
    """Test creating CustomLoop instances."""

    def test_basic_creation(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(
            name="test-loop",
            source="convos",
            target="temp_memory",
            interval=60.0,
            prompt="Extract key topics.",
        )
        assert loop.config.name == "test-loop"
        assert loop.source == "convos"
        assert loop.target == "temp_memory"
        assert loop.config.interval_seconds == 60.0
        assert loop.prompt == "Extract key topics."

    def test_model_default(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="m1", source="convos", prompt="test")
        model = loop.model
        assert isinstance(model, str)
        assert len(model) > 0

    def test_model_override(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="m2", source="convos", model="phi3:mini", prompt="test")
        assert loop.model == "phi3:mini"

    def test_model_setter(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="m3", source="convos", prompt="test")
        loop.model = "llama3:8b"
        assert loop.model == "llama3:8b"

    def test_stats_include_custom_fields(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(
            name="stat-loop",
            source="feeds",
            target="log",
            prompt="Analyze feeds for sentiment.",
        )
        stats = loop.stats
        assert stats["source"] == "feeds"
        assert stats["target"] == "log"
        assert stats["is_custom"] is True
        assert "prompt_preview" in stats
        assert stats["prompt_preview"].startswith("Analyze feeds")

    def test_to_config_dict(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(
            name="cfg-loop",
            source="identity",
            target="temp_memory",
            interval=120.0,
            model="qwen2.5:7b",
            prompt="Review identity facts for consistency.",
        )
        cfg = loop.to_config_dict()
        assert cfg["name"] == "cfg-loop"
        assert cfg["source"] == "identity"
        assert cfg["target"] == "temp_memory"
        assert cfg["interval_seconds"] == 120.0
        assert cfg["model"] == "qwen2.5:7b"
        assert "consistency" in cfg["prompt"]


class TestCustomLoopParsing:
    """Test the _parse_results method."""

    def test_parse_valid_list(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="p1", source="convos", prompt="test")
        result = loop._parse_results('[{"key": "a.b", "text": "fact one"}]')
        assert len(result) == 1
        assert result[0]["text"] == "fact one"

    def test_parse_empty_list(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="p2", source="convos", prompt="test")
        result = loop._parse_results('[]')
        assert result == []

    def test_parse_code_block(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="p3", source="convos", prompt="test")
        raw = '```python\n[{"key": "x", "text": "from block"}]\n```'
        result = loop._parse_results(raw)
        assert len(result) == 1
        assert result[0]["text"] == "from block"

    def test_parse_garbage(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="p4", source="convos", prompt="test")
        result = loop._parse_results("no valid data here")
        assert result == []

    def test_parse_filters_no_text(self):
        from agent.subconscious.loops import CustomLoop
        loop = CustomLoop(name="p5", source="convos", prompt="test")
        raw = '[{"key": "a"}, {"key": "b", "text": "valid"}]'
        result = loop._parse_results(raw)
        assert len(result) == 1
        assert result[0]["text"] == "valid"


# ─────────────────────────────────────────────────────────────
# DB Persistence — CRUD functions
# ─────────────────────────────────────────────────────────────

class TestCustomLoopCRUD:
    """Test save/get/delete custom loop configs in DB."""

    def test_save_and_get(self):
        from agent.subconscious.loops import save_custom_loop_config, get_custom_loop_config
        save_custom_loop_config(
            name="crud-test",
            source="convos",
            target="temp_memory",
            interval=60.0,
            model="test-model",
            prompt="Extract topics.",
        )
        cfg = get_custom_loop_config("crud-test")
        assert cfg is not None
        assert cfg["name"] == "crud-test"
        assert cfg["source"] == "convos"
        assert cfg["target"] == "temp_memory"
        assert cfg["interval_seconds"] == 60.0
        assert cfg["model"] == "test-model"
        assert cfg["enabled"] is True

    def test_get_all(self):
        from agent.subconscious.loops import save_custom_loop_config, get_custom_loop_configs
        save_custom_loop_config(
            name="crud-all-1", source="convos", target="temp_memory",
            interval=30.0, model=None, prompt="p1",
        )
        save_custom_loop_config(
            name="crud-all-2", source="feeds", target="log",
            interval=120.0, model="m2", prompt="p2",
        )
        configs = get_custom_loop_configs()
        names = [c["name"] for c in configs]
        assert "crud-all-1" in names
        assert "crud-all-2" in names

    def test_update_existing(self):
        from agent.subconscious.loops import save_custom_loop_config, get_custom_loop_config
        save_custom_loop_config(
            name="crud-update", source="convos", target="temp_memory",
            interval=60.0, model=None, prompt="v1",
        )
        # Update it
        save_custom_loop_config(
            name="crud-update", source="feeds", target="log",
            interval=120.0, model="new-model", prompt="v2",
        )
        cfg = get_custom_loop_config("crud-update")
        assert cfg["source"] == "feeds"
        assert cfg["target"] == "log"
        assert cfg["prompt"] == "v2"
        assert cfg["model"] == "new-model"

    def test_delete(self):
        from agent.subconscious.loops import (
            save_custom_loop_config, delete_custom_loop_config, get_custom_loop_config
        )
        save_custom_loop_config(
            name="crud-del", source="convos", target="temp_memory",
            interval=60.0, model=None, prompt="deletable",
        )
        ok = delete_custom_loop_config("crud-del")
        assert ok is True
        cfg = get_custom_loop_config("crud-del")
        assert cfg is None

    def test_delete_nonexistent(self):
        from agent.subconscious.loops import delete_custom_loop_config
        ok = delete_custom_loop_config("nonexistent-loop-xyz")
        assert ok is False


class TestCustomLoopValidation:
    """Test validation in save_custom_loop_config."""

    def test_invalid_source(self):
        from agent.subconscious.loops import save_custom_loop_config
        with pytest.raises(ValueError, match="Invalid source"):
            save_custom_loop_config(
                name="bad-src", source="twitter", target="temp_memory",
                interval=60.0, model=None, prompt="test",
            )

    def test_invalid_target(self):
        from agent.subconscious.loops import save_custom_loop_config
        with pytest.raises(ValueError, match="Invalid target"):
            save_custom_loop_config(
                name="bad-tgt", source="convos", target="email",
                interval=60.0, model=None, prompt="test",
            )

    def test_interval_too_low(self):
        from agent.subconscious.loops import save_custom_loop_config
        with pytest.raises(ValueError, match="Interval"):
            save_custom_loop_config(
                name="bad-int", source="convos", target="temp_memory",
                interval=2.0, model=None, prompt="test",
            )

    def test_empty_prompt(self):
        from agent.subconscious.loops import save_custom_loop_config
        with pytest.raises(ValueError, match="Prompt"):
            save_custom_loop_config(
                name="bad-prm", source="convos", target="temp_memory",
                interval=60.0, model=None, prompt="",
            )

    def test_empty_name(self):
        from agent.subconscious.loops import save_custom_loop_config
        with pytest.raises(ValueError, match="Name"):
            save_custom_loop_config(
                name="", source="convos", target="temp_memory",
                interval=60.0, model=None, prompt="test",
            )


# ─────────────────────────────────────────────────────────────
# LoopManager — add, remove, load_custom_loops
# ─────────────────────────────────────────────────────────────

class TestLoopManagerCustom:
    """Test LoopManager with custom loops."""

    def test_add_and_get_custom(self):
        from agent.subconscious.loops import LoopManager, CustomLoop
        mgr = LoopManager()
        loop = CustomLoop(name="mgr-test", source="convos", prompt="test")
        mgr.add(loop)
        found = mgr.get_loop("mgr-test")
        assert found is not None
        assert found.config.name == "mgr-test"

    def test_remove_custom(self):
        from agent.subconscious.loops import LoopManager, CustomLoop
        mgr = LoopManager()
        loop = CustomLoop(name="mgr-rm", source="convos", prompt="test")
        mgr.add(loop)
        assert mgr.remove("mgr-rm") is True
        assert mgr.get_loop("mgr-rm") is None

    def test_remove_nonexistent(self):
        from agent.subconscious.loops import LoopManager
        mgr = LoopManager()
        assert mgr.remove("nope") is False

    def test_stats_include_custom(self):
        from agent.subconscious.loops import LoopManager, CustomLoop, MemoryLoop
        mgr = LoopManager()
        mgr.add(MemoryLoop(interval=999))
        mgr.add(CustomLoop(name="cust1", source="feeds", prompt="analyze"))
        stats = mgr.get_stats()
        names = [s["name"] for s in stats]
        assert "memory" in names
        assert "cust1" in names
        # Custom loop should have is_custom flag
        cust_stat = [s for s in stats if s["name"] == "cust1"][0]
        assert cust_stat["is_custom"] is True

    def test_load_custom_loops_from_db(self):
        from agent.subconscious.loops import (
            LoopManager, save_custom_loop_config, delete_custom_loop_config
        )
        # Save a config to DB
        save_custom_loop_config(
            name="load-test-loop", source="convos", target="temp_memory",
            interval=999.0, model=None, prompt="test load",
        )
        
        mgr = LoopManager()
        loaded = mgr.load_custom_loops()
        assert loaded >= 1
        
        found = mgr.get_loop("load-test-loop")
        assert found is not None
        
        # Clean up - stop loops
        mgr.stop_all()
        delete_custom_loop_config("load-test-loop")


# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

class TestConstants:
    """Test that source/target lists are properly defined."""

    def test_sources_defined(self):
        from agent.subconscious.loops import CUSTOM_LOOP_SOURCES
        assert "convos" in CUSTOM_LOOP_SOURCES
        assert "feeds" in CUSTOM_LOOP_SOURCES
        assert "identity" in CUSTOM_LOOP_SOURCES
        assert "temp_memory" in CUSTOM_LOOP_SOURCES
        assert "log" in CUSTOM_LOOP_SOURCES

    def test_targets_defined(self):
        from agent.subconscious.loops import CUSTOM_LOOP_TARGETS
        assert "temp_memory" in CUSTOM_LOOP_TARGETS
        assert "log" in CUSTOM_LOOP_TARGETS


# ─────────────────────────────────────────────────────────────
# API Endpoint Tests
# ─────────────────────────────────────────────────────────────

class TestCustomLoopAPI:
    """Test the custom loop REST endpoints."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from fastapi.testclient import TestClient
        from agent.subconscious.api import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def test_list_custom_loops(self):
        res = self.client.get("/api/subconscious/loops/custom")
        assert res.status_code == 200
        data = res.json()
        assert "custom_loops" in data
        assert "available_sources" in data
        assert "available_targets" in data
        assert isinstance(data["available_sources"], list)

    def test_create_custom_loop(self):
        res = self.client.post(
            "/api/subconscious/loops/custom",
            json={
                "name": "api-test-loop",
                "source": "convos",
                "target": "temp_memory",
                "interval": 120,
                "prompt": "Extract entity names from conversations.",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "created"
        assert data["loop"]["name"] == "api-test-loop"
        assert data["loop"]["source"] == "convos"

        # Clean up
        from agent.subconscious.loops import delete_custom_loop_config
        delete_custom_loop_config("api-test-loop")

    def test_create_missing_fields(self):
        res = self.client.post(
            "/api/subconscious/loops/custom",
            json={"name": "bad"},
        )
        assert res.status_code == 400

    def test_create_builtin_name_conflict(self):
        res = self.client.post(
            "/api/subconscious/loops/custom",
            json={
                "name": "memory",
                "source": "convos",
                "prompt": "test",
            },
        )
        assert res.status_code == 400
        assert "conflicts" in res.json()["detail"]

    def test_create_invalid_source(self):
        res = self.client.post(
            "/api/subconscious/loops/custom",
            json={
                "name": "bad-source-loop",
                "source": "twitter",
                "prompt": "test",
            },
        )
        assert res.status_code == 400

    def test_update_custom_loop(self):
        # Create first
        from agent.subconscious.loops import save_custom_loop_config
        save_custom_loop_config(
            name="api-update-loop", source="convos", target="temp_memory",
            interval=60.0, model=None, prompt="original prompt",
        )

        res = self.client.put(
            "/api/subconscious/loops/custom/api-update-loop",
            json={"interval": 180, "prompt": "updated prompt"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "updated"

        # Verify
        from agent.subconscious.loops import get_custom_loop_config
        cfg = get_custom_loop_config("api-update-loop")
        assert cfg["interval_seconds"] == 180.0
        assert cfg["prompt"] == "updated prompt"

        # Clean up
        from agent.subconscious.loops import delete_custom_loop_config
        delete_custom_loop_config("api-update-loop")

    def test_update_nonexistent(self):
        res = self.client.put(
            "/api/subconscious/loops/custom/no-such-loop",
            json={"interval": 60},
        )
        assert res.status_code == 404

    def test_delete_custom_loop(self):
        from agent.subconscious.loops import save_custom_loop_config
        save_custom_loop_config(
            name="api-del-loop", source="convos", target="temp_memory",
            interval=60.0, model=None, prompt="to delete",
        )

        res = self.client.delete("/api/subconscious/loops/custom/api-del-loop")
        assert res.status_code == 200
        assert res.json()["status"] == "deleted"

    def test_delete_nonexistent(self):
        res = self.client.delete("/api/subconscious/loops/custom/no-such-loop")
        assert res.status_code == 404
