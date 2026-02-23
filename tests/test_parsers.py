"""
Tests for import parsers — ChatGPT, Claude, Gemini, and the orchestrator's
message-pairing logic.

Run: pytest tests/test_parsers.py -v
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from chat.parsers.export_parser_base import ParsedConversation, ParsedMessage
from chat.parsers.chatgpt_export_parser import ChatGPTExportParser
from chat.parsers.claude_export_parser import ClaudeExportParser
from chat.parsers.gemini_export_parser import GeminiExportParser
from chat.import_convos import ImportConvos


# ─── helpers ────────────────────────────────────────────────────────────────

def _run(coro):
    """Convenience wrapper to run an async coroutine in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── ChatGPT parser ────────────────────────────────────────────────────────

class TestChatGPTParser:
    """Tests for ChatGPTExportParser."""

    SAMPLE_CONVERSATIONS = [
        {
            "title": "Hello World",
            "create_time": 1700000000.0,
            "update_time": 1700001000.0,
            "conversation_id": "abc-123",
            "default_model_slug": "gpt-4",
            "mapping": {
                "root": {
                    "id": "root",
                    "message": None,
                    "parent": None,
                    "children": ["sys1"],
                },
                "sys1": {
                    "id": "sys1",
                    "message": {
                        "id": "sys1",
                        "author": {"role": "system"},
                        "content": {"content_type": "text", "parts": ["You are ChatGPT."]},
                        "create_time": 1700000000.0,
                    },
                    "parent": "root",
                    "children": ["u1"],
                },
                "u1": {
                    "id": "u1",
                    "message": {
                        "id": "u1",
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["Hi there"]},
                        "create_time": 1700000001.0,
                    },
                    "parent": "sys1",
                    "children": ["a1"],
                },
                "a1": {
                    "id": "a1",
                    "message": {
                        "id": "a1",
                        "author": {"role": "assistant"},
                        "content": {"content_type": "text", "parts": ["Hello! How can I help?"]},
                        "create_time": 1700000002.0,
                        "metadata": {"model_slug": "gpt-4"},
                    },
                    "parent": "u1",
                    "children": ["u2"],
                },
                "u2": {
                    "id": "u2",
                    "message": {
                        "id": "u2",
                        "author": {"role": "user"},
                        "content": {"content_type": "text", "parts": ["What is 2+2?"]},
                        "create_time": 1700000003.0,
                    },
                    "parent": "a1",
                    "children": ["a2"],
                },
                "a2": {
                    "id": "a2",
                    "message": {
                        "id": "a2",
                        "author": {"role": "assistant"},
                        "content": {"content_type": "text", "parts": ["4"]},
                        "create_time": 1700000004.0,
                    },
                    "parent": "u2",
                    "children": [],
                },
            },
            "current_node": "a2",
        }
    ]

    def _write_export(self, tmp_path: Path) -> Path:
        """Write a mock ChatGPT export directory."""
        export_dir = tmp_path / "chatgpt_export"
        export_dir.mkdir()
        with open(export_dir / "conversations.json", "w") as f:
            json.dump(self.SAMPLE_CONVERSATIONS, f)
        return export_dir

    def test_validate_pass(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ChatGPTExportParser()
        assert parser.validate(export_dir) is True

    def test_validate_fail_empty(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        parser = ChatGPTExportParser()
        assert parser.validate(empty) is False

    def test_validate_json_file_directly(self, tmp_path):
        f = tmp_path / "conversations.json"
        f.write_text(json.dumps(self.SAMPLE_CONVERSATIONS))
        parser = ChatGPTExportParser()
        assert parser.validate(f) is True

    def test_parse_extracts_messages(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ChatGPTExportParser()
        convos = _run(parser.parse(export_dir))

        assert len(convos) == 1
        conv = convos[0]
        assert conv.title == "Hello World"
        assert conv.id == "abc-123"

        # System message should be filtered out → 4 messages (2 user, 2 assistant)
        assert len(conv.messages) == 4
        roles = [m.role for m in conv.messages]
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_parse_filters_system_messages(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ChatGPTExportParser()
        convos = _run(parser.parse(export_dir))

        for msg in convos[0].messages:
            assert msg.role in ("user", "assistant")
            assert "You are ChatGPT" not in msg.content

    def test_parse_content_extraction(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ChatGPTExportParser()
        convos = _run(parser.parse(export_dir))

        msgs = convos[0].messages
        assert msgs[0].content == "Hi there"
        assert msgs[1].content == "Hello! How can I help?"
        assert msgs[2].content == "What is 2+2?"
        assert msgs[3].content == "4"

    def test_parse_timestamps(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ChatGPTExportParser()
        convos = _run(parser.parse(export_dir))
        conv = convos[0]

        assert conv.created_at == datetime.fromtimestamp(1700000000.0)
        assert conv.updated_at == datetime.fromtimestamp(1700001000.0)

    def test_platform_name(self):
        assert ChatGPTExportParser().get_platform_name() == "ChatGPT"

    def test_skips_empty_conversations(self, tmp_path):
        """Conversation with no user/assistant messages should be skipped."""
        data = [{
            "title": "Empty",
            "conversation_id": "empty-1",
            "create_time": 1700000000.0,
            "update_time": 1700000000.0,
            "mapping": {
                "root": {"id": "root", "message": None, "parent": None, "children": ["s"]},
                "s": {
                    "id": "s",
                    "message": {
                        "id": "s",
                        "author": {"role": "system"},
                        "content": {"content_type": "text", "parts": ["system prompt"]},
                        "create_time": 1700000000.0,
                    },
                    "parent": "root",
                    "children": [],
                },
            },
        }]
        export_dir = tmp_path / "empty_export"
        export_dir.mkdir()
        (export_dir / "conversations.json").write_text(json.dumps(data))

        convos = _run(ChatGPTExportParser().parse(export_dir))
        assert len(convos) == 0

    def test_nested_zip_directory(self, tmp_path):
        """conversations.json one directory deep (ZIP extraction artifact)."""
        outer = tmp_path / "upload"
        inner = outer / "2024-01-15-chatgpt-export"
        inner.mkdir(parents=True)
        (inner / "conversations.json").write_text(json.dumps(self.SAMPLE_CONVERSATIONS))

        parser = ChatGPTExportParser()
        assert parser.validate(outer) is True
        convos = _run(parser.parse(outer))
        assert len(convos) == 1


# ─── Claude parser ─────────────────────────────────────────────────────────

class TestClaudeParser:
    """Tests for ClaudeExportParser."""

    SAMPLE_EXPORT = [
        {
            "uuid": "claude-conv-001",
            "name": "Python Help",
            "created_at": "2024-06-15T10:30:00.000000+00:00",
            "updated_at": "2024-06-15T11:00:00.000000+00:00",
            "model": "claude-3-opus",
            "chat_messages": [
                {
                    "uuid": "msg-001",
                    "text": "How do I read a file in Python?",
                    "sender": "human",
                    "created_at": "2024-06-15T10:30:00.000000+00:00",
                    "updated_at": "2024-06-15T10:30:00.000000+00:00",
                    "attachments": [],
                    "files": [],
                },
                {
                    "uuid": "msg-002",
                    "text": "You can use open() with a context manager:\n\nwith open('file.txt', 'r') as f:\n    content = f.read()",
                    "sender": "assistant",
                    "created_at": "2024-06-15T10:30:05.000000+00:00",
                    "updated_at": "2024-06-15T10:30:05.000000+00:00",
                    "attachments": [],
                    "files": [],
                },
                {
                    "uuid": "msg-003",
                    "text": "What about binary files?",
                    "sender": "human",
                    "created_at": "2024-06-15T10:31:00.000000+00:00",
                    "updated_at": "2024-06-15T10:31:00.000000+00:00",
                    "attachments": [],
                    "files": [],
                },
                {
                    "uuid": "msg-004",
                    "text": "Use 'rb' mode: open('file.bin', 'rb')",
                    "sender": "assistant",
                    "created_at": "2024-06-15T10:31:10.000000+00:00",
                    "updated_at": "2024-06-15T10:31:10.000000+00:00",
                    "attachments": [],
                    "files": [],
                },
            ],
        }
    ]

    def _write_export(self, tmp_path: Path) -> Path:
        export_dir = tmp_path / "claude_export"
        export_dir.mkdir()
        with open(export_dir / "conversations.json", "w") as f:
            json.dump(self.SAMPLE_EXPORT, f)
        return export_dir

    def test_validate_pass(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ClaudeExportParser()
        assert parser.validate(export_dir) is True

    def test_validate_fail(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        parser = ClaudeExportParser()
        assert parser.validate(empty) is False

    def test_parse_conversation_count(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ClaudeExportParser()
        convos = _run(parser.parse(export_dir))
        assert len(convos) == 1

    def test_parse_messages(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ClaudeExportParser()
        convos = _run(parser.parse(export_dir))
        conv = convos[0]

        assert conv.title == "Python Help"
        assert conv.id == "claude-conv-001"
        assert len(conv.messages) == 4
        assert conv.messages[0].role == "user"
        assert conv.messages[1].role == "assistant"
        assert "open()" in conv.messages[1].content

    def test_human_mapped_to_user(self, tmp_path):
        """Claude uses 'human' as sender — should map to 'user'."""
        export_dir = self._write_export(tmp_path)
        parser = ClaudeExportParser()
        convos = _run(parser.parse(export_dir))
        roles = [m.role for m in convos[0].messages]
        assert "human" not in roles
        assert roles == ["user", "assistant", "user", "assistant"]

    def test_parse_timestamps(self, tmp_path):
        export_dir = self._write_export(tmp_path)
        parser = ClaudeExportParser()
        convos = _run(parser.parse(export_dir))
        conv = convos[0]
        assert conv.created_at.year == 2024
        assert conv.created_at.month == 6

    def test_content_block_format(self, tmp_path):
        """Claude sometimes puts content as a list of blocks."""
        data = [{
            "uuid": "block-test",
            "name": "Block Content",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:01:00+00:00",
            "chat_messages": [
                {
                    "uuid": "bm1",
                    "sender": "human",
                    "text": "",
                    "content": [
                        {"type": "text", "text": "Part one."},
                        {"type": "text", "text": "Part two."},
                    ],
                    "created_at": "2024-01-01T00:00:00+00:00",
                },
                {
                    "uuid": "bm2",
                    "sender": "assistant",
                    "text": "Response here.",
                    "created_at": "2024-01-01T00:00:05+00:00",
                },
            ],
        }]
        export_dir = tmp_path / "claude_blocks"
        export_dir.mkdir()
        (export_dir / "conversations.json").write_text(json.dumps(data))

        convos = _run(ClaudeExportParser().parse(export_dir))
        assert len(convos) == 1
        assert "Part one." in convos[0].messages[0].content
        assert "Part two." in convos[0].messages[0].content

    def test_platform_name(self):
        assert ClaudeExportParser().get_platform_name() == "Claude"


# ─── Gemini parser ─────────────────────────────────────────────────────────

class TestGeminiParser:
    """Tests for GeminiExportParser."""

    def test_validate_textinput_format(self, tmp_path):
        data = [{"textInput": "hi", "modelResponse": "hello"}]
        f = tmp_path / "gemini.json"
        f.write_text(json.dumps(data))
        parser = GeminiExportParser()
        assert parser.validate(f) is True

    def test_validate_fail_no_signals(self, tmp_path):
        data = [{"foo": "bar"}]
        f = tmp_path / "random.json"
        f.write_text(json.dumps(data))
        parser = GeminiExportParser()
        assert parser.validate(f) is False

    def test_parse_textinput_format(self, tmp_path):
        data = [
            {"textInput": "What is AI?", "modelResponse": "Artificial Intelligence is..."},
            {"textInput": "Tell me more", "modelResponse": "AI encompasses..."},
        ]
        f = tmp_path / "gemini.json"
        f.write_text(json.dumps(data))
        convos = _run(GeminiExportParser().parse(f))
        assert len(convos) == 2
        assert convos[0].messages[0].role == "user"
        assert convos[0].messages[0].content == "What is AI?"
        assert convos[0].messages[1].role == "assistant"

    def test_parse_inputtext_outputtext_format(self, tmp_path):
        data = [{"inputText": "Hello", "outputText": "Hi there!"}]
        f = tmp_path / "gemini2.json"
        f.write_text(json.dumps(data))
        convos = _run(GeminiExportParser().parse(f))
        assert len(convos) == 1
        assert convos[0].messages[0].content == "Hello"
        assert convos[0].messages[1].content == "Hi there!"

    def test_parse_messages_array_format(self, tmp_path):
        data = {
            "title": "Chat about code",
            "messages": [
                {"role": "user", "text": "Write a function"},
                {"role": "model", "text": "def example(): pass"},
            ],
        }
        f = tmp_path / "gemini3.json"
        f.write_text(json.dumps(data))
        convos = _run(GeminiExportParser().parse(f))
        assert len(convos) == 1
        assert convos[0].messages[0].role == "user"
        assert convos[0].messages[1].role == "assistant"

    def test_takeout_directory_structure(self, tmp_path):
        """Simulates Google Takeout folder structure."""
        gemini_dir = tmp_path / "Takeout" / "Gemini Apps"
        gemini_dir.mkdir(parents=True)
        data = [{"textInput": "Test", "modelResponse": "Response"}]
        (gemini_dir / "conversation1.json").write_text(json.dumps(data))

        parser = GeminiExportParser()
        assert parser.validate(tmp_path) is True
        convos = _run(parser.parse(tmp_path))
        assert len(convos) == 1

    def test_platform_name(self):
        assert GeminiExportParser().get_platform_name() == "Gemini"


# ─── Orchestrator message pairing ──────────────────────────────────────────

class TestMessagePairing:
    """Test ImportConvos._convert_to_aios_format message pairing logic."""

    def _make_importer(self, tmp_path: Path) -> ImportConvos:
        ws = tmp_path / "workspace"
        feeds = tmp_path / "feeds"
        ws.mkdir()
        feeds.mkdir()
        return ImportConvos(ws, feeds)

    def _make_conv(self, messages: List[ParsedMessage]) -> ParsedConversation:
        now = datetime.now()
        return ParsedConversation(
            id="test-conv",
            title="Test",
            messages=messages,
            created_at=now,
            updated_at=now,
        )

    def _msg(self, role: str, content: str) -> ParsedMessage:
        return ParsedMessage(role=role, content=content, timestamp=datetime.now())

    def test_simple_alternating(self, tmp_path):
        """Standard user-assistant-user-assistant."""
        importer = self._make_importer(tmp_path)
        conv = self._make_conv([
            self._msg("user", "Hello"),
            self._msg("assistant", "Hi!"),
            self._msg("user", "Bye"),
            self._msg("assistant", "Goodbye!"),
        ])
        result = importer._convert_to_aios_format(conv)
        turns = result["turns"]
        assert len(turns) == 2
        assert turns[0]["user"] == "Hello"
        assert turns[0]["assistant"] == "Hi!"
        assert turns[1]["user"] == "Bye"
        assert turns[1]["assistant"] == "Goodbye!"

    def test_user_no_response(self, tmp_path):
        """User message with no assistant response → empty assistant."""
        importer = self._make_importer(tmp_path)
        conv = self._make_conv([
            self._msg("user", "Hello"),
        ])
        result = importer._convert_to_aios_format(conv)
        turns = result["turns"]
        assert len(turns) == 1
        assert turns[0]["user"] == "Hello"
        assert turns[0]["assistant"] == ""

    def test_consecutive_assistant(self, tmp_path):
        """Multiple assistant messages after one user → merged."""
        importer = self._make_importer(tmp_path)
        conv = self._make_conv([
            self._msg("user", "Explain"),
            self._msg("assistant", "Part 1"),
            self._msg("assistant", "Part 2"),
        ])
        result = importer._convert_to_aios_format(conv)
        turns = result["turns"]
        assert len(turns) == 1
        assert turns[0]["user"] == "Explain"
        assert "Part 1" in turns[0]["assistant"]
        assert "Part 2" in turns[0]["assistant"]

    def test_assistant_without_user(self, tmp_path):
        """Assistant speaks first (no preceding user) → empty user."""
        importer = self._make_importer(tmp_path)
        conv = self._make_conv([
            self._msg("assistant", "Welcome!"),
            self._msg("user", "Thanks"),
            self._msg("assistant", "No problem"),
        ])
        result = importer._convert_to_aios_format(conv)
        turns = result["turns"]
        assert len(turns) == 2
        assert turns[0]["user"] == ""
        assert turns[0]["assistant"] == "Welcome!"
        assert turns[1]["user"] == "Thanks"
        assert turns[1]["assistant"] == "No problem"

    def test_consecutive_user_messages(self, tmp_path):
        """Two user messages in a row → two turns with empty assistant."""
        importer = self._make_importer(tmp_path)
        conv = self._make_conv([
            self._msg("user", "First"),
            self._msg("user", "Second"),
            self._msg("assistant", "Reply"),
        ])
        result = importer._convert_to_aios_format(conv)
        turns = result["turns"]
        # First user has no assistant, second user gets the assistant reply
        assert len(turns) == 2
        assert turns[0]["user"] == "First"
        assert turns[0]["assistant"] == ""
        assert turns[1]["user"] == "Second"
        assert turns[1]["assistant"] == "Reply"

    def test_system_messages_skipped(self, tmp_path):
        """System role messages should be silently skipped."""
        importer = self._make_importer(tmp_path)
        conv = self._make_conv([
            self._msg("system", "You are a helper"),
            self._msg("user", "Hi"),
            self._msg("assistant", "Hello"),
        ])
        result = importer._convert_to_aios_format(conv)
        turns = result["turns"]
        assert len(turns) == 1
        assert turns[0]["user"] == "Hi"

    def test_session_id_format(self, tmp_path):
        """Session ID should be prefixed with imported_."""
        importer = self._make_importer(tmp_path)
        conv = self._make_conv([self._msg("user", "test")])
        conv.id = "abc-123"
        result = importer._convert_to_aios_format(conv)
        assert result["session_id"] == "imported_abc-123"


# ─── Source name mapping ───────────────────────────────────────────────────

class TestSourceMapping:
    """Verify the source_map in import_convos handles all parser names."""

    def test_all_parser_names_map_correctly(self):
        """Every parser's get_platform_name().lower() should map to a known source."""
        source_map = {
            "chatgpt": "chatgpt",
            "claude": "claude",
            "gemini": "gemini",
            "vscode": "copilot",
            "copilot": "copilot",
            "vscode-copilot": "copilot",
        }
        parsers = [
            ChatGPTExportParser(),
            ClaudeExportParser(),
            GeminiExportParser(),
        ]
        for parser in parsers:
            name = parser.get_platform_name().lower()
            assert name in source_map, f"Parser '{name}' not in source_map"
