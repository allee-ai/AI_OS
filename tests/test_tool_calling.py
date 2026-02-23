"""
Tests for the tool calling system.

Covers: scanner, safety allowlist, executables (file_read, file_write,
terminal, web_search), schema mode (Ollama JSON protocol), and integration.

Run: pytest tests/test_tool_calling.py -v
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Scanner tests
# ============================================================================

class TestScanner:
    """Test the :::execute::: block scanner."""

    def test_import(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls, replace_tool_calls_with_results
        assert callable(scan_for_tool_calls)
        assert callable(replace_tool_calls_with_results)

    def test_single_block(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        text = "Let me read that file.\n:::execute\ntool: file_read\naction: read_file\npath: /README.md\n:::\n"
        calls = scan_for_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].tool == "file_read"
        assert calls[0].action == "read_file"
        assert calls[0].params["path"] == "/README.md"

    def test_multiple_blocks(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        text = (
            "First I'll search.\n"
            ":::execute\ntool: web_search\naction: search\nquery: python asyncio\n:::\n"
            "Then I'll read a file.\n"
            ":::execute\ntool: file_read\naction: read_file\npath: /main.py\n:::\n"
        )
        calls = scan_for_tool_calls(text)
        assert len(calls) == 2
        assert calls[0].tool == "web_search"
        assert calls[1].tool == "file_read"

    def test_malformed_missing_tool(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        text = ":::execute\naction: read_file\npath: /README.md\n:::\n"
        calls = scan_for_tool_calls(text)
        assert len(calls) == 0, "Block missing 'tool:' should be skipped"

    def test_malformed_missing_action(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        text = ":::execute\ntool: file_read\npath: /README.md\n:::\n"
        calls = scan_for_tool_calls(text)
        assert len(calls) == 0, "Block missing 'action:' should be skipped"

    def test_empty_block(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        text = ":::execute\n\n:::\n"
        calls = scan_for_tool_calls(text)
        assert len(calls) == 0

    def test_no_blocks(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        text = "Just a normal message with no tool calls."
        calls = scan_for_tool_calls(text)
        assert len(calls) == 0

    def test_replace_with_results(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls, replace_tool_calls_with_results
        text = "Before.\n:::execute\ntool: file_read\naction: read_file\npath: /README.md\n:::\nAfter."
        calls = scan_for_tool_calls(text)
        result = replace_tool_calls_with_results(text, calls, ["# Hello World"])
        assert ":::result tool=file_read action=read_file" in result
        assert "# Hello World" in result
        assert "Before." in result
        assert "After." in result
        assert ":::execute" not in result

    def test_replace_preserves_order(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls, replace_tool_calls_with_results
        text = (
            "A\n:::execute\ntool: t1\naction: a1\n:::\n"
            "B\n:::execute\ntool: t2\naction: a2\n:::\nC"
        )
        calls = scan_for_tool_calls(text)
        result = replace_tool_calls_with_results(text, calls, ["result1", "result2"])
        # Results should appear in order
        pos1 = result.index("result1")
        pos2 = result.index("result2")
        assert pos1 < pos2

    def test_params_with_spaces(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        text = ":::execute\ntool: web_search\naction: search\nquery: how to use python asyncio tutorial\n:::\n"
        calls = scan_for_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].params["query"] == "how to use python asyncio tutorial"

    def test_positions_tracked(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        prefix = "Hello there. "
        block = ":::execute\ntool: t\naction: a\n:::"
        text = prefix + block
        calls = scan_for_tool_calls(text)
        assert len(calls) == 1
        assert calls[0].start_pos == len(prefix)
        assert calls[0].end_pos == len(text)


# ============================================================================
# Safety allowlist tests
# ============================================================================

class TestSafety:
    """Test the action safety allowlist."""

    def test_import(self):
        from agent.threads.form.tools.registry import is_action_safe, SAFE_ACTIONS, BLOCKED_ACTIONS
        assert callable(is_action_safe)
        assert isinstance(SAFE_ACTIONS, dict)
        assert isinstance(BLOCKED_ACTIONS, dict)

    def test_safe_read_actions(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("file_read", "read_file") is True
        assert is_action_safe("file_read", "list_directory") is True
        assert is_action_safe("file_read", "search_files") is True

    def test_safe_web_search(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("web_search", "search") is True

    def test_blocked_terminal(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("terminal", "run_command") is False
        assert is_action_safe("terminal", "kill_process") is False

    def test_blocked_file_write(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("file_write", "write_file") is False
        assert is_action_safe("file_write", "append_file") is False

    def test_safe_file_write_mkdir(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("file_write", "create_directory") is True

    def test_unknown_tool_blocked(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("nonexistent_tool", "anything") is False

    def test_unknown_action_blocked(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("file_read", "delete_file") is False

    def test_terminal_get_output_safe(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("terminal", "get_output") is True

    def test_memory_actions_safe(self):
        from agent.threads.form.tools.registry import is_action_safe
        assert is_action_safe("memory_identity", "get_identity") is True
        assert is_action_safe("memory_log", "search_logs") is True
        assert is_action_safe("memory_linking", "spread_activate") is True


# ============================================================================
# Executable tests — file_read
# ============================================================================

class TestFileRead:
    """Test the file_read executable."""

    def test_import(self):
        from agent.threads.form.tools.executables.file_read import run
        assert callable(run)

    def test_read_existing_file(self):
        from agent.threads.form.tools.executables.file_read import run
        result = run("read_file", {"path": "README.md"})
        assert len(result) > 0
        assert "error" not in result.lower() or "Error" not in result.split('\n')[0]

    def test_read_nonexistent_file(self):
        from agent.threads.form.tools.executables.file_read import run
        result = run("read_file", {"path": "DOES_NOT_EXIST_xyz123.txt"})
        assert "not found" in result.lower() or "error" in result.lower()

    def test_list_directory(self):
        from agent.threads.form.tools.executables.file_read import run
        result = run("list_directory", {"path": "."})
        assert "README.md" in result

    def test_search_files(self):
        from agent.threads.form.tools.executables.file_read import run
        result = run("search_files", {"pattern": "*.py"})
        # Should find at least some .py files
        assert ".py" in result

    def test_path_traversal_blocked(self):
        from agent.threads.form.tools.executables.file_read import run
        result = run("read_file", {"path": "../../etc/passwd"})
        assert "outside workspace" in result.lower() or "error" in result.lower()

    def test_unknown_action(self):
        from agent.threads.form.tools.executables.file_read import run
        result = run("delete_file", {"path": "README.md"})
        assert "unknown" in result.lower() or "not found" in result.lower() or "error" in result.lower()


# ============================================================================
# Executable tests — file_write
# ============================================================================

class TestFileWrite:
    """Test the file_write executable."""

    def test_import(self):
        from agent.threads.form.tools.executables.file_write import run
        assert callable(run)

    def test_create_directory(self, tmp_path, monkeypatch):
        from agent.threads.form.tools.executables import file_write
        monkeypatch.setattr(file_write, "WORKSPACE_ROOT", tmp_path)
        result = file_write.run("create_directory", {"path": "test_subdir/nested"})
        assert "created" in result.lower() or "error" not in result.lower()
        assert (tmp_path / "test_subdir" / "nested").is_dir()

    def test_write_file(self, tmp_path, monkeypatch):
        from agent.threads.form.tools.executables import file_write
        monkeypatch.setattr(file_write, "WORKSPACE_ROOT", tmp_path)
        result = file_write.run("write_file", {"path": "hello.txt", "content": "hello world"})
        assert (tmp_path / "hello.txt").read_text() == "hello world"

    def test_append_file(self, tmp_path, monkeypatch):
        from agent.threads.form.tools.executables import file_write
        monkeypatch.setattr(file_write, "WORKSPACE_ROOT", tmp_path)
        (tmp_path / "existing.txt").write_text("line1\n")
        file_write.run("append_file", {"path": "existing.txt", "content": "line2\n"})
        assert "line2" in (tmp_path / "existing.txt").read_text()

    def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        from agent.threads.form.tools.executables import file_write
        monkeypatch.setattr(file_write, "WORKSPACE_ROOT", tmp_path)
        result = file_write.run("write_file", {"path": "../../etc/evil", "content": "bad"})
        assert "outside workspace" in result.lower() or "error" in result.lower()


# ============================================================================
# Executable tests — terminal
# ============================================================================

class TestTerminal:
    """Test the terminal executable."""

    def test_import(self):
        from agent.threads.form.tools.executables.terminal import run
        assert callable(run)

    def test_run_echo(self, monkeypatch):
        from agent.threads.form.tools.executables import terminal
        monkeypatch.setattr(terminal, "WORKSPACE_ROOT", Path("/tmp"))
        result = terminal.run("run_command", {"command": "echo hello_tool_test"})
        assert "hello_tool_test" in result

    def test_timeout(self, monkeypatch):
        from agent.threads.form.tools.executables import terminal
        monkeypatch.setattr(terminal, "WORKSPACE_ROOT", Path("/tmp"))
        monkeypatch.setattr(terminal, "TIMEOUT", 1)
        result = terminal.run("run_command", {"command": "sleep 10"})
        assert "timed out" in result.lower() or "timeout" in result.lower()

    def test_get_output(self, monkeypatch):
        from agent.threads.form.tools.executables import terminal
        monkeypatch.setattr(terminal, "WORKSPACE_ROOT", Path("/tmp"))
        # Run a command first to populate _last_output
        terminal.run("run_command", {"command": "echo cached_output"})
        result = terminal.run("get_output", {})
        assert "cached_output" in result or "no previous" in result.lower()


# ============================================================================
# Executable tests — web_search
# ============================================================================

class TestWebSearch:
    """Test the web_search executable."""

    def test_import(self):
        from agent.threads.form.tools.executables.web_search import run
        assert callable(run)

    def test_search_returns_results(self):
        """Test that search produces results (requires duckduckgo-search)."""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            pytest.skip("duckduckgo-search not installed")
        
        from agent.threads.form.tools.executables.web_search import run
        result = run("search", {"query": "python programming language"})
        # Should return some text (titles/snippets)
        assert len(result) > 20

    def test_missing_query(self):
        from agent.threads.form.tools.executables.web_search import run
        result = run("search", {})
        assert "no query" in result.lower() or "error" in result.lower() or "missing" in result.lower()


# ============================================================================
# Integration: scanner + safety
# ============================================================================

class TestScannerSafetyIntegration:
    """Test that scanner output is correctly filtered by safety."""

    def test_safe_call_passes(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        from agent.threads.form.tools.registry import is_action_safe

        text = ":::execute\ntool: file_read\naction: read_file\npath: /README.md\n:::\n"
        calls = scan_for_tool_calls(text)
        assert len(calls) == 1
        assert is_action_safe(calls[0].tool, calls[0].action) is True

    def test_blocked_call_denied(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        from agent.threads.form.tools.registry import is_action_safe

        text = ":::execute\ntool: terminal\naction: run_command\ncommand: rm -rf /\n:::\n"
        calls = scan_for_tool_calls(text)
        assert len(calls) == 1
        assert is_action_safe(calls[0].tool, calls[0].action) is False

    def test_mixed_safe_and_blocked(self):
        from agent.threads.form.tools.scanner import scan_for_tool_calls
        from agent.threads.form.tools.registry import is_action_safe

        text = (
            ":::execute\ntool: file_read\naction: read_file\npath: /x\n:::\n"
            ":::execute\ntool: terminal\naction: run_command\ncommand: rm -rf /\n:::\n"
        )
        calls = scan_for_tool_calls(text)
        assert len(calls) == 2
        assert is_action_safe(calls[0].tool, calls[0].action) is True
        assert is_action_safe(calls[1].tool, calls[1].action) is False


# ============================================================================
# Schema mode — Ollama JSON tool calling protocol
# ============================================================================

class TestSchemaMode:
    """Test the Ollama JSON schema tool calling mode."""

    # ── to_ollama_tools() ────────────────────────────────────────────────────

    def test_to_ollama_tools_importable(self):
        from agent.threads.form.tools.registry import to_ollama_tools
        assert callable(to_ollama_tools)

    def test_to_ollama_tools_empty_list_when_no_tools(self, monkeypatch):
        """No runnable tools → empty list, no crash."""
        from agent.threads.form.tools import registry
        monkeypatch.setattr(registry, "get_runnable_tools", lambda: [])
        result = registry.to_ollama_tools()
        assert result == []

    def test_to_ollama_tools_structure(self):
        """Every entry must conform to Ollama function tool schema."""
        from unittest.mock import patch
        from agent.threads.form.tools.registry import (
            to_ollama_tools, ToolDefinition, ToolCategory,
        )
        fake = ToolDefinition(
            name="file_read",
            description="Read workspace files",
            category=ToolCategory.FILES,
            actions=["read_file", "list_directory"],
            run_file="file_read.py",
        )
        with patch.object(type(fake), "exists", new_callable=lambda: property(lambda s: True)):
            result = to_ollama_tools([fake])

        assert isinstance(result, list)
        assert len(result) > 0
        for entry in result:
            assert entry["type"] == "function"
            fn = entry["function"]
            assert "name" in fn
            assert "description" in fn
            params = fn["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_function_name_uses_double_underscore(self):
        """Function names must be ``tool__action`` (double underscore)."""
        from unittest.mock import patch
        from agent.threads.form.tools.registry import to_ollama_tools, ToolDefinition, ToolCategory
        fake = ToolDefinition(
            name="web_search",
            description="Search the web",
            category=ToolCategory.BROWSER,
            actions=["search"],
            run_file="web_search.py",
        )
        with patch.object(type(fake), "exists", new_callable=lambda: property(lambda s: True)):
            result = to_ollama_tools([fake])

        names = [e["function"]["name"] for e in result]
        assert "web_search__search" in names
        for name in names:
            assert "__" in name
            parts = name.split("__")
            assert len(parts) == 2

    def test_only_safe_actions_exported(self):
        """BLOCKED_ACTIONS must never appear in to_ollama_tools() output."""
        from unittest.mock import patch
        from agent.threads.form.tools.registry import (
            to_ollama_tools, ToolDefinition, ToolCategory, BLOCKED_ACTIONS,
        )
        # terminal has safe (get_output) and blocked (run_command, kill_process)
        fake = ToolDefinition(
            name="terminal",
            description="Execute shell commands",
            category=ToolCategory.AUTOMATION,
            actions=["run_command", "get_output", "kill_process"],
            run_file="terminal.py",
        )
        with patch.object(type(fake), "exists", new_callable=lambda: property(lambda s: True)):
            result = to_ollama_tools([fake])

        fn_names = [e["function"]["name"] for e in result]
        for blocked in BLOCKED_ACTIONS.get("terminal", []):
            assert f"terminal__{blocked}" not in fn_names
        assert "terminal__get_output" in fn_names

    def test_all_safe_actions_for_file_read(self):
        """All SAFE_ACTIONS for file_read should appear with correct names."""
        from unittest.mock import patch
        from agent.threads.form.tools.registry import (
            to_ollama_tools, ToolDefinition, ToolCategory, SAFE_ACTIONS,
        )
        safe_file_read = SAFE_ACTIONS.get("file_read", [])
        fake = ToolDefinition(
            name="file_read",
            description="Read workspace files",
            category=ToolCategory.FILES,
            actions=safe_file_read,
            run_file="file_read.py",
        )
        with patch.object(type(fake), "exists", new_callable=lambda: property(lambda s: True)):
            result = to_ollama_tools([fake])

        fn_names = {e["function"]["name"] for e in result}
        for action in safe_file_read:
            assert f"file_read__{action}" in fn_names

    # ── _get_tool_mode() ─────────────────────────────────────────────────────

    def test_get_tool_mode_default_is_text(self, monkeypatch):
        """Without any env var or DB config, mode defaults to 'text'."""
        monkeypatch.delenv("AIOS_TOOL_MODE", raising=False)
        from agent.agent import Agent
        a = Agent()
        assert a._get_tool_mode() == "text"

    def test_get_tool_mode_env_text(self, monkeypatch):
        monkeypatch.setenv("AIOS_TOOL_MODE", "text")
        from agent.agent import Agent
        assert Agent()._get_tool_mode() == "text"

    def test_get_tool_mode_env_schema(self, monkeypatch):
        monkeypatch.setenv("AIOS_TOOL_MODE", "schema")
        from agent.agent import Agent
        assert Agent()._get_tool_mode() == "schema"

    def test_get_tool_mode_invalid_env_falls_back(self, monkeypatch):
        """An invalid AIOS_TOOL_MODE value is ignored, returns 'text'."""
        monkeypatch.setenv("AIOS_TOOL_MODE", "garbage_value")
        from agent.agent import Agent
        result = Agent()._get_tool_mode()
        assert result in ("text", "schema")  # must be a valid mode
        # In test env with no DB config → falls to default 'text'
        assert result == "text"

    # ── _process_schema_tool_calls() ─────────────────────────────────────────

    def test_no_tool_calls_returns_content(self, monkeypatch):
        """When Ollama returns no tool_calls, content is returned directly."""
        from agent.agent import Agent
        a = Agent()
        calls = []

        def mock_ollama(model, messages, tools):
            calls.append(1)
            return {"content": "Plain answer, no tools needed.", "tool_calls": []}

        monkeypatch.setattr(a, "_call_ollama_with_tools", mock_ollama)
        result = a._process_schema_tool_calls("m", [], [])

        assert isinstance(result, str)
        assert len(result) > 0
        assert len(calls) == 1  # only one LLM call needed

    def test_blocked_action_not_executed(self, monkeypatch):
        """Blocked actions get a BLOCKED message; the executor is never called."""
        from agent.agent import Agent
        a = Agent()

        call_count = [0]
        def mock_ollama(model, messages, tools):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    "content": "",
                    "tool_calls": [{"function": {
                        "name": "terminal__run_command",
                        "arguments": {"command": "rm -rf /"},
                    }}],
                }
            return {"content": "Cannot run that.", "tool_calls": []}

        executed = []
        def mock_execute(tool, action, params):
            executed.append((tool, action))
            return {"success": True, "output": "executed"}

        import agent.threads.form.schema as form_schema
        monkeypatch.setattr(a, "_call_ollama_with_tools", mock_ollama)
        monkeypatch.setattr(form_schema, "execute_tool_action", mock_execute)

        messages: list = []
        a._process_schema_tool_calls("m", messages, [])

        # Blocked action must never reach the executor
        assert ("terminal", "run_command") not in executed
        # A tool result message with BLOCKED content must have been injected
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "BLOCKED" in tool_msgs[0]["content"]

    def test_safe_action_is_executed(self, monkeypatch):
        """Safe actions are executed and the result is injected as a tool message."""
        from agent.agent import Agent
        import agent.threads.form.schema as form_schema
        a = Agent()

        def mock_ollama(model, messages, tools):
            # First call: no tool message yet → return a tool call
            if not any(m.get("role") == "tool" for m in messages):
                return {
                    "content": "",
                    "tool_calls": [{"function": {
                        "name": "file_read__read_file",
                        "arguments": {"path": "README.md"},
                    }}],
                }
            return {"content": "Here is the summary.", "tool_calls": []}

        executed = []
        def mock_execute(tool, action, params):
            executed.append((tool, action, dict(params)))
            return {"success": True, "output": "# AI OS content"}

        monkeypatch.setattr(a, "_call_ollama_with_tools", mock_ollama)
        monkeypatch.setattr(form_schema, "execute_tool_action", mock_execute)

        messages: list = []
        result = a._process_schema_tool_calls("m", messages, [])

        assert ("file_read", "read_file", {"path": "README.md"}) in executed
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "AI OS content" in tool_msgs[0]["content"]
        assert isinstance(result, str)

    def test_bad_function_name_handled_gracefully(self, monkeypatch):
        """Function names without __ separator inject an error message, no crash."""
        from agent.agent import Agent
        a = Agent()

        call_count = [0]
        def mock_ollama(model, messages, tools):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"content": "", "tool_calls": [
                    {"function": {"name": "badname_no_separator", "arguments": {}}}
                ]}
            return {"content": "Handled.", "tool_calls": []}

        monkeypatch.setattr(a, "_call_ollama_with_tools", mock_ollama)
        messages: list = []
        result = a._process_schema_tool_calls("m", messages, [])

        assert isinstance(result, str)
        # An error tool message should have been appended
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "error" in tool_msgs[0]["content"].lower() or "invalid" in tool_msgs[0]["content"].lower()

    def test_max_rounds_respected(self, monkeypatch):
        """Tool loop exits after max_rounds even if model keeps returning tool_calls."""
        from agent.agent import Agent
        a = Agent()

        call_count = [0]
        def mock_ollama(model, messages, tools):
            call_count[0] += 1
            # Always return a tool call — loop must terminate
            return {
                "content": "",
                "tool_calls": [{"function": {
                    "name": "web_search__search",
                    "arguments": {"query": "test"},
                }}],
            }

        import agent.threads.form.schema as form_schema
        monkeypatch.setattr(a, "_call_ollama_with_tools", mock_ollama)
        monkeypatch.setattr(
            form_schema, "execute_tool_action",
            lambda t, a_, p: {"success": True, "output": "result"}
        )

        MAX = 3
        a._process_schema_tool_calls("m", [], [], max_rounds=MAX)
        # ollama is called MAX times (one per round) + 1 final call after loop → MAX+1
        assert call_count[0] == MAX + 1
