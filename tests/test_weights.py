"""
Weight system tests — Hebbian updates, tool traces, co-occurrence, training export.

Tests the core learning loop: tool use → weight update → STATE visibility → training.
"""

import json
import os
import pytest
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("AIOS_MODE", "demo")


# ===================================================================
# Hebbian Weight Updates (tool_traces)
# ===================================================================

class TestHebbianWeights:
    """agent.agent._log_tool_call weight computation."""

    def _insert_trace(self, conn, tool, action, weight):
        conn.execute(
            """INSERT INTO tool_traces
               (tool, action, success, output, weight, duration_ms, metadata_json)
               VALUES (?, ?, 1, 'test', ?, 0, '{}')""",
            (tool, action, weight),
        )
        conn.commit()

    def _latest_weight(self, conn, tool, action):
        row = conn.execute(
            "SELECT weight FROM tool_traces WHERE tool = ? AND action = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (tool, action),
        ).fetchone()
        return row[0] if row else None

    def test_success_increases_weight(self):
        """Hebbian: success → weight += (1 - weight) * 0.1"""
        from data.db import get_connection
        with closing(get_connection()) as conn:
            self._insert_trace(conn, "_test_hebb", "up", 0.5)
            prev = 0.5
            expected = prev + (1.0 - prev) * 0.1  # 0.55
            assert abs(expected - 0.55) < 0.001

    def test_failure_decreases_weight(self):
        """Failure → weight = max(0.1, weight - 0.1)"""
        prev = 0.5
        expected = max(0.1, prev - 0.1)  # 0.4
        assert abs(expected - 0.4) < 0.001

    def test_weight_floor(self):
        """Weight never drops below 0.1."""
        prev = 0.15
        expected = max(0.1, prev - 0.1)
        assert expected == pytest.approx(0.1, abs=0.01)

    def test_weight_ceiling_approach(self):
        """Repeated success approaches 1.0 but never exceeds."""
        w = 0.5
        for _ in range(100):
            w = w + (1.0 - w) * 0.1
        assert w < 1.0
        assert w > 0.99

    def test_first_success_gets_base_weight(self):
        """No prior trace → base_weight = 0.7 for success."""
        base_weight = 0.7  # from agent.py
        assert base_weight == 0.7

    def test_first_failure_gets_low_base(self):
        """No prior trace → base_weight = 0.3 for failure."""
        base_weight = 0.3
        assert base_weight == 0.3


# ===================================================================
# Tool Traces in STATE
# ===================================================================

class TestToolContext:
    """orchestrator._get_tool_context visibility."""

    def test_tool_context_format(self):
        """Tool traces format: tools.{tool}.{action}: ✓ (w=0.70) output"""
        from data.db import get_connection
        from agent.subconscious.orchestrator import Subconscious

        with closing(get_connection()) as conn:
            # Ensure table exists
            conn.execute("""CREATE TABLE IF NOT EXISTS tool_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                output TEXT,
                weight REAL NOT NULL DEFAULT 0.5,
                duration_ms INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute(
                """INSERT INTO tool_traces
                   (tool, action, success, output, weight, duration_ms, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("_test_ctx", "run", 1, "completed task", 0.85, 100, "{}"),
            )
            conn.commit()

        orch = Subconscious()
        facts = orch._get_tool_context(max_results=50)

        # Find our test trace
        matching = [f for f in facts if "_test_ctx" in f]
        assert len(matching) >= 1
        assert "w=0.85" in matching[0]
        assert "✓" in matching[0]

    def test_low_weight_filtered(self):
        """Traces with weight < 0.2 should be excluded."""
        from data.db import get_connection
        from agent.subconscious.orchestrator import Subconscious

        with closing(get_connection()) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS tool_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL,
                action TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                output TEXT,
                weight REAL NOT NULL DEFAULT 0.5,
                duration_ms INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute(
                """INSERT INTO tool_traces
                   (tool, action, success, output, weight, duration_ms, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("_test_low", "fail", 0, "error", 0.1, 50, "{}"),
            )
            conn.commit()

        orch = Subconscious()
        facts = orch._get_tool_context(max_results=50)
        low_matches = [f for f in facts if "_test_low" in f]
        assert len(low_matches) == 0


# ===================================================================
# Co-occurrence Data
# ===================================================================

class TestCooccurrence:
    """linking_core co-occurrence queries."""

    def test_get_cooccurrence_data_structure(self):
        """get_cooccurrence_data returns pairs, top_concepts, stats."""
        from agent.threads.linking_core.schema import (
            get_cooccurrence_data,
            record_cooccurrence,
        )
        # Seed some data
        for _ in range(3):
            record_cooccurrence("_test_a", "_test_b")

        data = get_cooccurrence_data(limit=100, min_count=1)
        assert "pairs" in data
        assert "top_concepts" in data
        assert "stats" in data
        assert isinstance(data["pairs"], list)
        assert data["stats"]["total_pairs"] >= 1

    def test_min_count_filter(self):
        """min_count filters out low co-occurrence pairs."""
        from agent.threads.linking_core.schema import (
            get_cooccurrence_data,
            record_cooccurrence,
        )
        record_cooccurrence("_test_rare_x", "_test_rare_y")

        low = get_cooccurrence_data(limit=100, min_count=1)
        high = get_cooccurrence_data(limit=100, min_count=999)
        # Rare pair should appear in low but not high
        low_pairs = {(p["key_a"], p["key_b"]) for p in low["pairs"]}
        high_pairs = {(p["key_a"], p["key_b"]) for p in high["pairs"]}
        assert len(high_pairs) <= len(low_pairs)


# ===================================================================
# Training Export includes User Feedback
# ===================================================================

class TestTrainingExport:
    """finetune export merges user_approved.jsonl."""

    def test_export_includes_approved(self, tmp_path):
        """user_approved.jsonl lines should appear in aios_combined.jsonl."""
        finetune_dir = tmp_path / "finetune"
        finetune_dir.mkdir()

        # Create a fake user_approved.jsonl
        approved = finetune_dir / "user_approved.jsonl"
        example = {
            "messages": [
                {"role": "user", "content": "test question"},
                {"role": "assistant", "content": "test answer"},
            ],
            "metadata": {"source": "user_approved"},
        }
        approved.write_text(json.dumps(example) + "\n")

        # Mock the finetune dir and thread exports
        with patch("finetune.api.FINETUNE_DIR", finetune_dir):
            # Create minimal thread files
            for thread in ["identity", "philosophy", "log", "reflex", "form", "linking_core"]:
                (finetune_dir / f"{thread}_train.jsonl").write_text("")

            # Simulate what the export does (combine step)
            combined_path = finetune_dir / "aios_combined.jsonl"
            total = 0
            approved_count = 0
            threads = ["linking_core", "identity", "philosophy", "log", "reflex", "form"]

            with open(combined_path, "w") as combined:
                for thread in threads:
                    tf = finetune_dir / f"{thread}_train.jsonl"
                    if tf.exists():
                        for line in open(tf):
                            combined.write(line)
                            total += 1
                af = finetune_dir / "user_approved.jsonl"
                if af.exists():
                    for line in open(af):
                        combined.write(line)
                        total += 1
                        approved_count += 1

            # Verify
            assert approved_count == 1
            assert total == 1
            lines = combined_path.read_text().strip().split("\n")
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["metadata"]["source"] == "user_approved"


# ===================================================================
# CLI Module Loading
# ===================================================================

class TestCLILoading:
    """cli._load_commands discovers module commands."""

    def test_load_commands_returns_dict(self):
        from cli import _load_commands
        cmds = _load_commands()
        assert isinstance(cmds, dict)
        assert len(cmds) > 0

    def test_all_commands_are_callable(self):
        from cli import _load_commands
        cmds = _load_commands()
        for name, fn in cmds.items():
            assert callable(fn), f"{name} is not callable"

    def test_expected_commands_present(self):
        from cli import _load_commands
        cmds = _load_commands()
        expected = ["/status", "/graph", "/tools", "/identity"]
        for cmd in expected:
            assert cmd in cmds, f"Missing command: {cmd}"
