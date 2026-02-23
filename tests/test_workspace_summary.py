"""
Workspace Summary & State Preview Tests
========================================
Tests for workspace summarization, file metadata helpers,
summarizer prompt CRUD, orchestrator L1/L2/L3, and state preview.
"""

import os
import pytest
import tempfile

# Force test DB
os.environ.setdefault("AIOS_DB_PATH", os.path.join(tempfile.mkdtemp(), "test_ws.db"))


# ─────────────────────────────────────────────────────────────
# Schema helpers
# ─────────────────────────────────────────────────────────────

class TestFileSummary:
    """Tests for update/get file summary."""

    def setup_method(self):
        from workspace.schema import init_workspace_tables, create_file
        init_workspace_tables()
        create_file("/docs/readme.md", b"# Hello\nThis is a readme.", "text/markdown")

    def test_update_and_get_summary(self):
        from workspace.schema import update_file_summary, get_file_summary
        ok = update_file_summary("/docs/readme.md", "A readme file.")
        assert ok is True
        assert get_file_summary("/docs/readme.md") == "A readme file."

    def test_get_summary_returns_none_for_missing(self):
        from workspace.schema import get_file_summary
        assert get_file_summary("/does/not/exist.txt") is None

    def test_update_summary_returns_false_for_missing(self):
        from workspace.schema import update_file_summary
        assert update_file_summary("/nope.txt", "summary") is False

    def test_summary_appears_in_metadata(self):
        from workspace.schema import update_file_summary, get_all_files_metadata
        update_file_summary("/docs/readme.md", "A readme file.")
        meta = get_all_files_metadata()
        found = [m for m in meta if m["path"] == "/docs/readme.md"]
        assert len(found) == 1
        assert found[0]["summary"] == "A readme file."


class TestAllFilesMetadata:
    """Tests for get_all_files_metadata."""

    def setup_method(self):
        from workspace.schema import init_workspace_tables, create_file
        from data.db import get_connection
        from contextlib import closing
        init_workspace_tables()
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM workspace_files")
            conn.commit()
        create_file("/a.txt", b"aaa", "text/plain")
        create_file("/b.txt", b"bbb", "text/plain")
        create_file("/c.txt", b"ccc", "text/plain")

    def test_returns_all_files(self):
        from workspace.schema import get_all_files_metadata
        meta = get_all_files_metadata()
        paths = [m["path"] for m in meta]
        assert "/a.txt" in paths
        assert "/b.txt" in paths
        assert "/c.txt" in paths

    def test_limit_param(self):
        from workspace.schema import get_all_files_metadata
        meta = get_all_files_metadata(limit=2)
        assert len(meta) == 2

    def test_metadata_keys(self):
        from workspace.schema import get_all_files_metadata
        meta = get_all_files_metadata()
        for m in meta:
            assert "path" in m
            assert "name" in m
            assert "size" in m
            assert "mime_type" in m
            assert "summary" in m


# ─────────────────────────────────────────────────────────────
# Summarizer prompt CRUD
# ─────────────────────────────────────────────────────────────

class TestSummarizerPrompt:
    """Tests for get/set summarizer prompt."""

    def setup_method(self):
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS settings "
                "(key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.execute("DELETE FROM settings WHERE key = 'workspace_summary_prompt'")
            conn.commit()

    def test_default_prompt(self):
        from workspace.summarizer import get_summary_prompt
        prompt = get_summary_prompt()
        assert "Summarize" in prompt

    def test_set_and_get_prompt(self):
        from workspace.summarizer import set_summary_prompt, get_summary_prompt
        ok = set_summary_prompt("Custom prompt.")
        assert ok is True
        assert get_summary_prompt() == "Custom prompt."

    def test_set_prompt_overwrites(self):
        from workspace.summarizer import set_summary_prompt, get_summary_prompt
        set_summary_prompt("First")
        set_summary_prompt("Second")
        assert get_summary_prompt() == "Second"

    def test_summarize_text_empty_returns_none(self):
        from workspace.summarizer import summarize_text
        assert summarize_text("") is None
        assert summarize_text(None) is None


# ─────────────────────────────────────────────────────────────
# Orchestrator workspace context
# ─────────────────────────────────────────────────────────────

class TestWorkspaceContext:
    """Tests for _get_workspace_context L1/L2/L3."""

    def setup_method(self):
        from workspace.schema import init_workspace_tables, create_file, update_file_summary
        from data.db import get_connection
        from contextlib import closing
        init_workspace_tables()
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM workspace_files")
            conn.commit()
        create_file("/project/main.py", b"print('hello world')", "text/plain")
        update_file_summary("/project/main.py", "Entry point that prints hello.")

    def test_no_fts_returns_metadata(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        ctx = sub._get_workspace_context("completely unrelated query xyz")
        # Returns a list of context lines
        assert isinstance(ctx, list)
        assert len(ctx) > 0

    def test_context_includes_file_info(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        ctx = sub._get_workspace_context("hello")
        assert isinstance(ctx, list)
        # Should mention our file
        joined = " ".join(ctx)
        assert "main.py" in joined


# ─────────────────────────────────────────────────────────────
# State Preview
# ─────────────────────────────────────────────────────────────

class TestStatePreview:
    """Tests for preview_state()."""

    def test_preview_returns_required_keys(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        result = sub.preview_state("test query")
        assert "query" in result
        assert "thread_scores" in result
        assert "state_block" in result
        assert "total_tokens" in result
        assert "thresholds" in result

    def test_preview_query_echoed(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        result = sub.preview_state("my test")
        assert result["query"] == "my test"

    def test_preview_thread_scores_are_dict(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        result = sub.preview_state("hello")
        assert isinstance(result["thread_scores"], dict)

    def test_preview_state_block_is_string(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        result = sub.preview_state("hello")
        assert isinstance(result["state_block"], str)

    def test_preview_tokens_is_int(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        result = sub.preview_state("hello")
        assert isinstance(result["total_tokens"], int)
        assert result["total_tokens"] >= 0

    def test_preview_thresholds_has_levels(self):
        from agent.subconscious.orchestrator import get_subconscious
        sub = get_subconscious()
        result = sub.preview_state("hello")
        thresholds = result["thresholds"]
        assert "L1" in thresholds
        assert "L2" in thresholds
        assert "L3" in thresholds
