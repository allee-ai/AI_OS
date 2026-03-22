"""
Pure-function tests — deterministic, no DB, no LLM.

These test functions that transform inputs → outputs with no side effects.
They survive refactors because they test *contracts*, not *implementations*.
"""

import pytest
from datetime import datetime


# ===================================================================
# Cron Matcher
# ===================================================================

class TestCronMatcher:
    """agent.threads.reflex.schedule.cron_matches_now — 5-field cron parser."""

    def _match(self, expr, dt=None):
        from agent.threads.reflex.schedule import cron_matches_now
        return cron_matches_now(expr, dt)

    def test_wildcard_always_matches(self):
        assert self._match("* * * * *") is True

    def test_exact_minute_match(self):
        dt = datetime(2025, 6, 15, 8, 30)
        assert self._match("30 8 * * *", dt) is True

    def test_exact_minute_mismatch(self):
        dt = datetime(2025, 6, 15, 8, 31)
        assert self._match("30 8 * * *", dt) is False

    def test_step_expression(self):
        dt = datetime(2025, 6, 15, 8, 0)
        assert self._match("*/15 * * * *", dt) is True
        dt2 = datetime(2025, 6, 15, 8, 7)
        assert self._match("*/15 * * * *", dt2) is False

    def test_range_expression(self):
        # Mon=1 in cron mapping
        dt_mon = datetime(2025, 6, 16, 8, 30)  # Monday
        assert self._match("30 8 * * 1-5", dt_mon) is True

    def test_comma_list(self):
        dt = datetime(2025, 6, 15, 8, 15)
        assert self._match("0,15,30,45 * * * *", dt) is True
        dt2 = datetime(2025, 6, 15, 8, 10)
        assert self._match("0,15,30,45 * * * *", dt2) is False

    def test_invalid_expression(self):
        assert self._match("") is False
        assert self._match("not a cron") is False
        assert self._match("* * *") is False  # only 3 fields

    def test_impossible_minute(self):
        assert self._match("99 * * * *") is False


# ===================================================================
# Condition Checker
# ===================================================================

class TestConditionChecker:
    """agent.threads.reflex.executor.check_condition — all operators."""

    def _check(self, condition, payload):
        from agent.threads.reflex.executor import check_condition
        return check_condition(condition, payload)

    def test_no_condition_always_matches(self):
        assert self._check(None, {"foo": "bar"}) is True
        assert self._check({}, {"foo": "bar"}) is True

    def test_eq(self):
        assert self._check(
            {"field": "name", "operator": "eq", "value": "alice"},
            {"name": "alice"},
        ) is True

    def test_neq(self):
        assert self._check(
            {"field": "name", "operator": "neq", "value": "bob"},
            {"name": "alice"},
        ) is True

    def test_contains(self):
        assert self._check(
            {"field": "subject", "operator": "contains", "value": "urgent"},
            {"subject": "This is urgent: please review"},
        ) is True

    def test_not_contains(self):
        assert self._check(
            {"field": "subject", "operator": "not_contains", "value": "spam"},
            {"subject": "Important meeting"},
        ) is True

    def test_starts_with(self):
        assert self._check(
            {"field": "path", "operator": "starts_with", "value": "/api"},
            {"path": "/api/v2/users"},
        ) is True

    def test_gt_lt(self):
        assert self._check(
            {"field": "score", "operator": "gt", "value": 5},
            {"score": 10},
        ) is True
        assert self._check(
            {"field": "score", "operator": "lt", "value": 5},
            {"score": 3},
        ) is True

    def test_exists(self):
        assert self._check(
            {"field": "data", "operator": "exists"},
            {"data": "something"},
        ) is True
        assert self._check(
            {"field": "missing", "operator": "exists"},
            {"data": "something"},
        ) is False

    def test_regex(self):
        assert self._check(
            {"field": "email", "operator": "regex", "value": r"@example\.com$"},
            {"email": "user@example.com"},
        ) is True

    def test_in_operator(self):
        assert self._check(
            {"field": "status", "operator": "in", "value": ["active", "pending"]},
            {"status": "active"},
        ) is True

    def test_nested_field(self):
        assert self._check(
            {"field": "payload.sender.name", "operator": "eq", "value": "Alice"},
            {"payload": {"sender": {"name": "Alice"}}},
        ) is True

    def test_composite_all(self):
        cond = {
            "all": [
                {"field": "type", "operator": "eq", "value": "email"},
                {"field": "priority", "operator": "gt", "value": 3},
            ]
        }
        assert self._check(cond, {"type": "email", "priority": 5}) is True
        assert self._check(cond, {"type": "email", "priority": 1}) is False

    def test_composite_any(self):
        cond = {
            "any": [
                {"field": "source", "operator": "eq", "value": "email"},
                {"field": "source", "operator": "eq", "value": "slack"},
            ]
        }
        assert self._check(cond, {"source": "slack"}) is True
        assert self._check(cond, {"source": "discord"}) is False

    def test_composite_not(self):
        cond = {"not": {"field": "type", "operator": "eq", "value": "spam"}}
        assert self._check(cond, {"type": "legit"}) is True
        assert self._check(cond, {"type": "spam"}) is False


# ===================================================================
# LLM Output Parser
# ===================================================================

class TestParsePythonList:
    """MemoryLoop._parse_python_list — parsing LLM output."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from agent.subconscious.loops import MemoryLoop
        self.ml = MemoryLoop.__new__(MemoryLoop)

    def test_clean_json(self):
        raw = '[{"key": "user.name", "text": "User is Alice"}]'
        result = self.ml._parse_python_list(raw)
        assert result is not None
        assert len(result) == 1
        assert result[0]["key"] == "user.name"

    def test_markdown_wrapped(self):
        raw = '```python\n[{"key": "user.likes.coffee", "text": "User likes coffee"}]\n```'
        result = self.ml._parse_python_list(raw)
        assert result is not None
        assert len(result) == 1

    def test_trailing_text(self):
        raw = 'Here are the facts:\n[{"key": "a", "text": "b"}]\nDone!'
        result = self.ml._parse_python_list(raw)
        assert result is not None
        assert len(result) == 1

    def test_empty_list(self):
        result = self.ml._parse_python_list("[]")
        assert result == []

    def test_unparseable(self):
        result = self.ml._parse_python_list("this is not a list at all")
        assert result is None

    def test_single_quotes(self):
        raw = "[{'key': 'user.name', 'text': 'Alice'}]"
        result = self.ml._parse_python_list(raw)
        assert result is not None
        assert len(result) == 1


# ===================================================================
# Path Normalizer
# ===================================================================

class TestNormalizePath:
    """workspace.schema.normalize_path — pure string transforms."""

    def _norm(self, path):
        from workspace.schema import normalize_path
        return normalize_path(path)

    def test_adds_leading_slash(self):
        assert self._norm("foo/bar") == "/foo/bar"

    def test_strips_trailing_slash(self):
        assert self._norm("/foo/bar/") == "/foo/bar"

    def test_root_preserved(self):
        assert self._norm("/") == "/"

    def test_collapses_double_slashes(self):
        assert self._norm("//foo//bar") == "/foo/bar"

    def test_already_normalized(self):
        assert self._norm("/a/b/c") == "/a/b/c"


# ===================================================================
# Concept Extraction (pure text → list)
# ===================================================================

class TestConceptExtraction:
    """linking_core.schema.extract_concepts_from_text — tokenizer."""

    def _extract(self, text):
        from agent.threads.linking_core.schema import extract_concepts_from_text
        return extract_concepts_from_text(text)

    def test_basic_extraction(self):
        result = self._extract("python programming and machine learning")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_empty_string(self):
        result = self._extract("")
        assert result == [] or result is not None

    def test_stopwords_filtered(self):
        result = self._extract("the and or but")
        # Should return empty or very short — stopwords aren't concepts
        assert len(result) <= 1


# ===================================================================
# Feed Intelligence — pure helpers
# ===================================================================

class TestFeedIntelligenceFormatThread:
    """Feeds.intelligence._format_thread — no LLM, just text formatting."""

    def _fmt(self, messages):
        from Feeds.intelligence import _format_thread
        return _format_thread(messages)

    def test_empty_list(self):
        assert self._fmt([]) == ""

    def test_single_message(self):
        result = self._fmt([
            {"from": "alice@x.com", "date": "2025-01-01", "subject": "Hi", "snippet": "Hello!"}
        ])
        assert "alice@x.com" in result
        assert "Hi" in result
        assert "Hello!" in result

    def test_multi_message_separator(self):
        msgs = [
            {"from": "a@x.com", "date": "d1", "subject": "s1", "snippet": "body1"},
            {"from": "b@x.com", "date": "d2", "subject": "s2", "snippet": "body2"},
        ]
        result = self._fmt(msgs)
        assert "---" in result
        assert "a@x.com" in result
        assert "b@x.com" in result

    def test_missing_fields_graceful(self):
        result = self._fmt([{}])
        assert "?" in result  # fallback shows '?'


class TestFeedIntelligenceParseJson:
    """Feeds.intelligence._parse_json — best-effort JSON extraction."""

    def _parse(self, raw, fallback=None):
        from Feeds.intelligence import _parse_json
        return _parse_json(raw, fallback)

    def test_valid_json(self):
        assert self._parse('[1,2,3]') == [1, 2, 3]

    def test_json_in_markdown_fences(self):
        raw = '```json\n[{"task": "do it"}]\n```'
        result = self._parse(raw, [])
        assert isinstance(result, list)
        assert result[0]["task"] == "do it"

    def test_none_input(self):
        assert self._parse(None, "default") == "default"

    def test_invalid_json(self):
        assert self._parse("not json at all", []) == []

    def test_empty_string(self):
        assert self._parse("", "fb") == "fb"


class TestFeedIntelligenceNullSafety:
    """Intelligence public functions handle empty / None inputs gracefully."""

    def test_summarize_thread_empty(self):
        from Feeds.intelligence import summarize_thread
        assert summarize_thread([]) is None

    def test_extract_action_items_empty(self):
        from Feeds.intelligence import extract_action_items
        assert extract_action_items([]) == []

    def test_triage_empty(self):
        from Feeds.intelligence import triage_emails
        assert triage_emails([]) == []

    def test_daily_digest_empty(self):
        from Feeds.intelligence import daily_digest
        assert daily_digest([]) is None
