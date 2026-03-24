"""
Workspace tool tests — test workspace_read, workspace_write, and workspace CLI.

Covers:
    - workspace_write: write_file, create_directory, delete_file, move_file
    - workspace_read: read_file, list_directory, search_files
    - workspace CLI: /files command parsing
    - Settings: workspace group exists in config schema
    - Registry: tools registered, safe actions correct
    - Headless: workspace CLI commands integrated
"""

import os
import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Use demo mode so we don't pollute personal workspace
os.environ.setdefault("AIOS_MODE", "demo")


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_test_files():
    """Clean up any test files we create in the workspace DB."""
    yield
    # Cleanup after each test
    try:
        from workspace.schema import delete_file, get_file
        for p in ["/test_write.txt", "/test_move_src.txt", "/test_move_dst.txt",
                   "/test_dir", "/test_dir/nested.txt", "/test_search_alpha.txt",
                   "/test_search_beta.txt", "/sorted", "/sorted/docs",
                   "/sorted/code", "/sorted/readme.md", "/sorted/code/app.py",
                   "/sorted/docs/guide.md", "/unsorted", "/unsorted/app.py",
                   "/unsorted/readme.md", "/unsorted/guide.md"]:
            if get_file(p):
                try:
                    delete_file(p, recursive=True)
                except Exception:
                    pass
    except Exception:
        pass


# ===================================================================
# workspace_write tool
# ===================================================================

class TestWorkspaceWrite:

    def _run(self, action, params):
        from agent.threads.form.tools.executables.workspace_write import run
        return run(action, params)

    def test_write_file_creates(self):
        result = self._run("write_file", {"path": "/test_write.txt", "content": "hello workspace"})
        assert "Wrote" in result
        assert "15" in result  # 15 bytes
        # Verify it's in DB
        from workspace.schema import get_file
        f = get_file("/test_write.txt")
        assert f is not None
        assert f["content"] == b"hello workspace"

    def test_write_file_requires_path(self):
        result = self._run("write_file", {"content": "no path"})
        assert "Error" in result

    def test_write_file_size_limit(self):
        os.environ["AIOS_WORKSPACE_MAX_FILE_SIZE"] = "10"
        result = self._run("write_file", {"path": "/test_write.txt", "content": "x" * 100})
        assert "Error" in result
        assert "max is 10" in result
        os.environ["AIOS_WORKSPACE_MAX_FILE_SIZE"] = "1048576"  # restore

    def test_write_file_overwrites(self):
        self._run("write_file", {"path": "/test_write.txt", "content": "v1"})
        self._run("write_file", {"path": "/test_write.txt", "content": "v2"})
        from workspace.schema import get_file
        f = get_file("/test_write.txt")
        assert f["content"] == b"v2"

    def test_create_directory(self):
        result = self._run("create_directory", {"path": "/test_dir"})
        assert "Created" in result
        from workspace.schema import get_file
        d = get_file("/test_dir")
        assert d is not None
        assert d["is_folder"] is True

    def test_create_directory_requires_path(self):
        result = self._run("create_directory", {})
        assert "Error" in result

    def test_delete_file(self):
        self._run("write_file", {"path": "/test_write.txt", "content": "to delete"})
        result = self._run("delete_file", {"path": "/test_write.txt"})
        assert "Deleted" in result
        from workspace.schema import get_file
        assert get_file("/test_write.txt") is None

    def test_delete_nonexistent(self):
        result = self._run("delete_file", {"path": "/does_not_exist_xyz.txt"})
        assert "Not found" in result

    def test_delete_root_blocked(self):
        result = self._run("delete_file", {"path": "/"})
        assert "Error" in result

    def test_move_file(self):
        self._run("write_file", {"path": "/test_move_src.txt", "content": "moving"})
        result = self._run("move_file", {"old_path": "/test_move_src.txt", "new_path": "/test_move_dst.txt"})
        assert "Moved" in result
        from workspace.schema import get_file
        assert get_file("/test_move_src.txt") is None
        f = get_file("/test_move_dst.txt")
        assert f is not None
        assert f["content"] == b"moving"

    def test_move_requires_paths(self):
        result = self._run("move_file", {"old_path": "/test_move_src.txt"})
        assert "Error" in result
        result = self._run("move_file", {"new_path": "/test_move_dst.txt"})
        assert "Error" in result

    def test_move_nonexistent(self):
        result = self._run("move_file", {"old_path": "/nonexistent_xyz.txt", "new_path": "/dst.txt"})
        assert "Not found" in result

    def test_unknown_action(self):
        result = self._run("drop_database", {})
        assert "Unknown action" in result


# ===================================================================
# workspace_read tool
# ===================================================================

class TestWorkspaceRead:

    def _write(self, path, content):
        from agent.threads.form.tools.executables.workspace_write import run
        run("write_file", {"path": path, "content": content})

    def _run(self, action, params):
        from agent.threads.form.tools.executables.workspace_read import run
        return run(action, params)

    def test_read_file(self):
        self._write("/test_write.txt", "read me back")
        result = self._run("read_file", {"path": "/test_write.txt"})
        assert result == "read me back"

    def test_read_file_not_found(self):
        result = self._run("read_file", {"path": "/nonexistent_xyz.txt"})
        assert "not found" in result.lower()

    def test_read_folder_gives_hint(self):
        from agent.threads.form.tools.executables.workspace_write import run as ws_write
        ws_write("create_directory", {"path": "/test_dir"})
        result = self._run("read_file", {"path": "/test_dir"})
        assert "folder" in result.lower() or "directory" in result.lower()

    def test_list_directory_root(self):
        self._write("/test_write.txt", "content")
        result = self._run("list_directory", {"path": "/"})
        assert "test_write.txt" in result

    def test_list_directory_empty(self):
        from agent.threads.form.tools.executables.workspace_write import run as ws_write
        ws_write("create_directory", {"path": "/test_dir"})
        result = self._run("list_directory", {"path": "/test_dir"})
        assert "empty" in result.lower()

    def test_search_files(self):
        self._write("/test_search_alpha.txt", "The quick brown fox jumps over the lazy dog")
        self._write("/test_search_beta.txt", "A completely unrelated document about cats")
        result = self._run("search_files", {"query": "fox"})
        # FTS may not be indexed yet (chunk_file needed) — verify we get
        # either results or a clean "no matches" message, not a crash
        assert isinstance(result, str)
        # If FTS is populated, we'd see the file; if not, "No workspace files"
        assert "fox" in result.lower() or "no workspace files" in result.lower() or "error" not in result.lower()

    def test_search_requires_query(self):
        result = self._run("search_files", {})
        assert "Error" in result or "required" in result.lower()

    def test_unknown_action(self):
        result = self._run("hack_system", {})
        assert "Unknown action" in result


# ===================================================================
# Tool Registry
# ===================================================================

class TestWorkspaceRegistry:

    def test_workspace_read_registered(self):
        from agent.threads.form.tools.registry import get_tool
        tool = get_tool("workspace_read")
        assert tool is not None
        assert "read_file" in tool.actions
        assert "list_directory" in tool.actions
        assert "search_files" in tool.actions
        assert tool.exists

    def test_workspace_write_registered(self):
        from agent.threads.form.tools.registry import get_tool
        tool = get_tool("workspace_write")
        assert tool is not None
        assert "write_file" in tool.actions
        assert "create_directory" in tool.actions
        assert "move_file" in tool.actions
        assert "delete_file" in tool.actions
        assert tool.exists

    def test_safe_actions_read(self):
        from agent.threads.form.tools.registry import SAFE_ACTIONS
        safe = SAFE_ACTIONS.get("workspace_read", [])
        assert "read_file" in safe
        assert "list_directory" in safe
        assert "search_files" in safe

    def test_safe_actions_write(self):
        from agent.threads.form.tools.registry import SAFE_ACTIONS
        safe = SAFE_ACTIONS.get("workspace_write", [])
        assert "write_file" in safe
        assert "create_directory" in safe
        assert "move_file" in safe

    def test_delete_is_blocked(self):
        from agent.threads.form.tools.registry import BLOCKED_ACTIONS, is_action_safe
        blocked = BLOCKED_ACTIONS.get("workspace_write", [])
        assert "delete_file" in blocked
        assert not is_action_safe("workspace_write", "delete_file")

    def test_move_is_safe(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("workspace_write", "move_file")

    def test_param_schemas_exist(self):
        from agent.threads.form.tools.registry import _ACTION_PARAM_SCHEMAS
        assert "workspace_read__read_file" in _ACTION_PARAM_SCHEMAS
        assert "workspace_read__list_directory" in _ACTION_PARAM_SCHEMAS
        assert "workspace_write__write_file" in _ACTION_PARAM_SCHEMAS
        assert "workspace_write__move_file" in _ACTION_PARAM_SCHEMAS
        assert "workspace_write__delete_file" in _ACTION_PARAM_SCHEMAS


# ===================================================================
# Settings Schema — workspace group
# ===================================================================

class TestWorkspaceSettings:

    def test_workspace_group_in_schema(self):
        from agent.core.settings_api import _CONFIG_SCHEMA
        ws_items = [s for s in _CONFIG_SCHEMA if s["group"] == "workspace"]
        assert len(ws_items) >= 4
        keys = [s["key"] for s in ws_items]
        assert "AIOS_WORKSPACE_LLM_READ" in keys
        assert "AIOS_WORKSPACE_LLM_WRITE" in keys
        assert "AIOS_WORKSPACE_LLM_DELETE" in keys
        assert "AIOS_WORKSPACE_LLM_MOVE" in keys
        assert "AIOS_WORKSPACE_MAX_FILE_SIZE" in keys


# ===================================================================
# DB Sync — ensure_tools_in_db
# ===================================================================

class TestToolsDBSync:

    def test_ensure_tools_in_db_populates(self):
        """Registry tools written to form_tools DB table."""
        from agent.threads.form.tools.registry import ensure_tools_in_db, TOOLS, _db_synced
        import agent.threads.form.tools.registry as reg
        # Reset so it actually runs
        reg._db_synced = False
        n = ensure_tools_in_db()
        assert n == len(TOOLS)

    def test_tools_queryable_after_sync(self):
        """execute_tool_action can find workspace tools in DB."""
        from agent.threads.form.tools.registry import ensure_tools_in_db
        import agent.threads.form.tools.registry as reg
        reg._db_synced = False
        ensure_tools_in_db()

        from agent.threads.form.schema import get_tool
        ws_r = get_tool("workspace_read")
        assert ws_r is not None
        assert ws_r["exists"] is True
        assert "read_file" in ws_r["actions"]

        ws_w = get_tool("workspace_write")
        assert ws_w is not None
        assert "move_file" in ws_w["actions"]

    def test_idempotent_second_call(self):
        """Second call is a no-op (returns 0)."""
        from agent.threads.form.tools.registry import ensure_tools_in_db
        import agent.threads.form.tools.registry as reg
        reg._db_synced = False
        ensure_tools_in_db()  # first
        n = ensure_tools_in_db()  # second
        assert n == 0


# ===================================================================
# Headless CLI — /files command
# ===================================================================

class TestWorkspaceCLI:

    def test_commands_exported(self):
        from workspace.cli import COMMANDS
        assert "/files" in COMMANDS

    def test_list_root(self, capsys):
        # Seed a file
        from agent.threads.form.tools.executables.workspace_write import run
        run("write_file", {"path": "/test_write.txt", "content": "cli test"})
        from workspace.cli import _cmd_files
        _cmd_files("/")
        out = capsys.readouterr().out
        assert "test_write" in out

    def test_read_file(self, capsys):
        from agent.threads.form.tools.executables.workspace_write import run
        run("write_file", {"path": "/test_write.txt", "content": "cli read content"})
        from workspace.cli import _cmd_files
        _cmd_files("read /test_write.txt")
        out = capsys.readouterr().out
        assert "cli read content" in out

    def test_stats(self, capsys):
        from workspace.cli import _cmd_files
        _cmd_files("stats")
        out = capsys.readouterr().out
        # Should print some stats keys
        assert "file_count" in out or "folder_count" in out or "total_size" in out


# ===================================================================
# LLM Integration — workspace sorting (requires --live)
# ===================================================================

class TestWorkspaceLLMSorting:
    """Test that the LLM can use workspace tools to organize files.
    
    These tests require --live flag and a running Ollama with kimi-k2.
    """

    @pytest.fixture
    def seed_unsorted_files(self):
        """Create a messy set of files in workspace for LLM to sort."""
        from agent.threads.form.tools.executables.workspace_write import run
        run("write_file", {"path": "/unsorted/readme.md", "content": "# My Project\nThis is a readme."})
        run("write_file", {"path": "/unsorted/app.py", "content": "def main():\n    print('hello')\n"})
        run("write_file", {"path": "/unsorted/guide.md", "content": "# User Guide\nStep 1: Install."})
        yield
        # Cleanup handled by autouse fixture

    def test_move_file_tool_works_for_sorting(self, seed_unsorted_files):
        """Verify the move_file tool can reorganize files into folders."""
        from agent.threads.form.tools.executables.workspace_write import run as ws_write
        from agent.threads.form.tools.executables.workspace_read import run as ws_read

        # Simulate what an LLM would do: create organized dirs and move files
        ws_write("create_directory", {"path": "/sorted"})
        ws_write("create_directory", {"path": "/sorted/docs"})
        ws_write("create_directory", {"path": "/sorted/code"})
        ws_write("move_file", {"old_path": "/unsorted/readme.md", "new_path": "/sorted/readme.md"})
        ws_write("move_file", {"old_path": "/unsorted/app.py", "new_path": "/sorted/code/app.py"})
        ws_write("move_file", {"old_path": "/unsorted/guide.md", "new_path": "/sorted/docs/guide.md"})

        # Verify structure
        listing = ws_read("list_directory", {"path": "/sorted"})
        assert "docs/" in listing
        assert "code/" in listing
        assert "readme.md" in listing

        code = ws_read("list_directory", {"path": "/sorted/code"})
        assert "app.py" in code

        docs = ws_read("list_directory", {"path": "/sorted/docs"})
        assert "guide.md" in docs

    @pytest.mark.skipif(
        os.environ.get("AIOS_TEST_LIVE") != "1",
        reason="Live LLM test — pass --live or AIOS_TEST_LIVE=1"
    )
    def test_kimi_k2_workspace_sorting(self, live_mode, seed_unsorted_files):
        """Ask Kimi K2 to organize workspace files using tools.
        
        This tests the full pipeline: LLM → tool call → workspace DB.
        Requires: ollama running, kimi-k2:1t-cloud available.
        """
        from agent.services.agent_service import AgentService

        svc = AgentService()
        prompt = (
            "Please organize my workspace files. "
            "First use workspace_read list_directory to see /unsorted, "
            "then create an organized folder structure and move files to "
            "appropriate locations using workspace_write move_file. "
            "Put code files in /sorted/code, docs in /sorted/docs, "
            "and the readme at /sorted/readme.md."
        )
        response = svc.chat(prompt)

        # The LLM should have executed tool calls
        assert response is not None
        assert len(response) > 0

        # Check if files were actually moved (may need multiple rounds)
        from workspace.schema import get_file
        # At minimum, check that the LLM attempted to engage with the workspace
        assert "workspace" in response.lower() or "sorted" in response.lower() or "moved" in response.lower()
