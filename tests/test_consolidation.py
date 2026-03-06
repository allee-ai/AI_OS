"""
Tests for Consolidation Loop
============================
Tests for fact scoring, classification, and promotion to long-term memory.

These tests verify behavior through LinkingCore's scoring pipeline
rather than testing internal keyword lists.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestFactClassification:
    """Test fact classification into identity vs philosophy via LinkingCore."""
    
    def _get_loop(self):
        from agent.subconscious.loops import ConsolidationLoop
        return ConsolidationLoop()
    
    def _get_loop_with_mock_scores(self, identity_score, philosophy_score):
        """Create a loop with a mocked linking core returning given scores."""
        loop = self._get_loop()
        mock_lc = MagicMock()
        mock_lc.score_threads.return_value = {
            'identity': identity_score,
            'philosophy': philosophy_score,
            'log': 3.0, 'form': 3.0, 'reflex': 3.0,
        }
        loop._linking_core = mock_lc
        return loop
    
    def test_classify_identity_when_identity_scores_higher(self):
        """When identity scores higher, route to identity."""
        loop = self._get_loop_with_mock_scores(identity_score=8.0, philosophy_score=4.0)
        assert loop._classify_fact_destination("My name is Sarah") == "identity"
    
    def test_classify_philosophy_when_philosophy_scores_higher(self):
        """When philosophy scores clearly higher, route to philosophy."""
        loop = self._get_loop_with_mock_scores(identity_score=4.0, philosophy_score=8.0)
        assert loop._classify_fact_destination("I believe honesty is the most important virtue") == "philosophy"
    
    def test_classify_identity_when_scores_close(self):
        """When scores are close (within 1.0), default to identity."""
        loop = self._get_loop_with_mock_scores(identity_score=6.0, philosophy_score=6.5)
        assert loop._classify_fact_destination("something ambiguous") == "identity"
    
    def test_classify_philosophy_needs_clear_margin(self):
        """Philosophy needs >1.0 margin over identity to win."""
        loop = self._get_loop_with_mock_scores(identity_score=5.0, philosophy_score=6.0)
        assert loop._classify_fact_destination("sort of philosophical") == "identity"
        
        loop2 = self._get_loop_with_mock_scores(identity_score=5.0, philosophy_score=6.5)
        assert loop2._classify_fact_destination("sort of philosophical") == "philosophy"
    
    def test_classify_defaults_to_identity_without_linking_core(self):
        """If linking core is unavailable, default to identity."""
        loop = self._get_loop()
        loop._linking_core = None  # Force no linking core
        # Patch _get_linking_core to return None
        with patch.object(loop, '_get_linking_core', return_value=None):
            assert loop._classify_fact_destination("anything at all") == "identity"
    
    def test_classify_returns_valid_destination(self):
        """Classification should only return 'identity' or 'philosophy'."""
        loop = self._get_loop()
        for text in ["random text", "hello world", "12345", "I believe in truth", "I live in NYC"]:
            result = loop._classify_fact_destination(text)
            assert result in ("identity", "philosophy"), f"Got '{result}' for '{text}'"
    
    def test_classify_uses_score_threads(self):
        """Verify classification actually calls score_threads on the linking core."""
        loop = self._get_loop()
        mock_lc = MagicMock()
        mock_lc.score_threads.return_value = {'identity': 7.0, 'philosophy': 3.0}
        loop._linking_core = mock_lc
        
        loop._classify_fact_destination("test input")
        mock_lc.score_threads.assert_called_once_with("test input")


class TestKeyGeneration:
    """Test hierarchical key generation."""
    
    def _get_loop(self):
        from agent.subconscious.loops import ConsolidationLoop
        return ConsolidationLoop()
    
    def test_generate_key_has_correct_prefix(self):
        """Keys should start with 'user.' for identity and 'philosophy.' for philosophy."""
        loop = self._get_loop()
        
        id_key = loop._generate_key("My name is Sarah", "identity")
        assert id_key.startswith("user."), f"Identity key should start with 'user.': {id_key}"
        
        phil_key = loop._generate_key("I believe in honesty", "philosophy")
        assert phil_key.startswith("philosophy."), f"Philosophy key should start with 'philosophy.': {phil_key}"
    
    def test_generate_key_has_three_parts(self):
        """Keys should have prefix.category.detail structure."""
        loop = self._get_loop()
        
        key = loop._generate_key("I work as a developer", "identity")
        parts = key.split(".", 2)
        assert len(parts) == 3, f"Key should have 3 dot-separated parts: {key}"
    
    def test_generate_key_extracts_meaningful_detail(self):
        """Detail portion should contain content words, not stop words."""
        loop = self._get_loop()
        
        key = loop._generate_key("Sarah works at Blue Bottle Coffee", "identity")
        detail = key.split(".", 2)[2]
        
        # Should contain some meaningful words from the input
        assert detail  # Not empty
        assert "_the_" not in detail
        assert "_is_" not in detail
    
    def test_generate_key_handles_empty_text(self):
        """Key generation should handle edge cases gracefully."""
        loop = self._get_loop()
        
        # Should not crash, should produce a valid key
        key = loop._generate_key("a", "identity")
        assert key.startswith("user.")
    
    def test_generate_key_identity_categories(self):
        """Identity keys should use reasonable categories."""
        loop = self._get_loop()
        
        key = loop._generate_key("I work as a developer", "identity")
        category = key.split(".")[1]
        valid_categories = {"identity", "preferences", "professional", "hobbies", "location", "general"}
        assert category in valid_categories, f"Unknown category '{category}' in key: {key}"
    
    def test_generate_key_philosophy_categories(self):
        """Philosophy keys should use reasonable categories."""
        loop = self._get_loop()
        
        key = loop._generate_key("I believe in honesty", "philosophy")
        category = key.split(".")[1]
        valid_categories = {"beliefs", "values", "principles", "ethics", "worldview", "stance"}
        assert category in valid_categories, f"Unknown category '{category}' in key: {key}"


class TestConfidenceScoring:
    """Test confidence score calculation."""
    
    def _get_loop(self):
        from agent.subconscious.loops import ConsolidationLoop
        return ConsolidationLoop()
    
    def test_confidence_base_score(self):
        """Facts start with base confidence."""
        loop = self._get_loop()
        
        # No linking core → uses text quality heuristics only
        confidence = loop._calculate_confidence(
            "Short fact",
            [],  # No existing facts
            None  # No linking core
        )
        
        assert 0.0 <= confidence <= 1.0
    
    def test_confidence_longer_facts_score_higher(self):
        """Longer, more detailed facts should score higher."""
        loop = self._get_loop()
        
        short_confidence = loop._calculate_confidence(
            "Likes blue",
            [],
            None
        )
        
        long_confidence = loop._calculate_confidence(
            "User prefers the color blue for their workspace theme and UI elements",
            [],
            None
        )
        
        assert long_confidence >= short_confidence
    
    def test_confidence_specific_facts_score_higher(self):
        """Facts with proper nouns/specifics should score higher."""
        loop = self._get_loop()
        
        generic_confidence = loop._calculate_confidence(
            "likes programming languages",
            [],
            None
        )
        
        specific_confidence = loop._calculate_confidence(
            "Sarah prefers Python over JavaScript",
            [],
            None
        )
        
        assert specific_confidence > generic_confidence
    
    def test_confidence_empty_fact_returns_zero(self):
        """Empty facts should return 0 confidence."""
        loop = self._get_loop()
        
        assert loop._calculate_confidence("", [], None) == 0.0
        assert loop._calculate_confidence("  ", [], None) == 0.0
    
    def test_confidence_with_mock_linking_core_dedup(self):
        """When linking core detects a duplicate, confidence should be -1.0."""
        loop = self._get_loop()
        
        # Mock a linking core that returns high similarity
        mock_lc = MagicMock()
        mock_lc.score_relevance.return_value = [("existing fact text", 0.95)]
        
        confidence = loop._calculate_confidence(
            "existing fact text",
            ["existing fact text"],
            mock_lc
        )
        
        assert confidence == -1.0
    
    def test_confidence_with_mock_linking_core_no_dup(self):
        """When linking core sees low similarity, fact should pass through."""
        loop = self._get_loop()
        
        mock_lc = MagicMock()
        # First call for dedup returns low similarity
        # Second call for relevance boost returns moderate
        mock_lc.score_relevance.side_effect = [
            [("some other fact", 0.3)],  # dedup check
            [("some other fact", 0.4)],  # relevance boost
        ]
        
        confidence = loop._calculate_confidence(
            "A new and different fact about Python",
            ["some other fact"],
            mock_lc
        )
        
        assert 0.0 < confidence <= 1.0


class TestTempMemoryStatus:
    """Test temp memory status functions."""
    
    def test_fact_dataclass_has_status(self):
        """Fact dataclass should have status field."""
        from agent.subconscious.temp_memory import Fact
        
        fact = Fact(
            id=1,
            text="Test fact",
            timestamp="2026-01-27",
            source="test",
            session_id="test-session",
            status="pending"
        )
        
        assert fact.status == "pending"
    
    def test_fact_dataclass_has_confidence_score(self):
        """Fact dataclass should have confidence_score field."""
        from agent.subconscious.temp_memory import Fact
        
        fact = Fact(
            id=1,
            text="Test fact",
            timestamp="2026-01-27",
            source="test",
            session_id="test-session",
            confidence_score=0.85
        )
        
        assert fact.confidence_score == 0.85
    
    def test_update_fact_status_validates_status(self):
        """update_fact_status should reject invalid statuses."""
        from agent.subconscious.temp_memory import update_fact_status
        
        with pytest.raises(ValueError) as exc_info:
            update_fact_status(1, "invalid_status")
        
        assert "Invalid status" in str(exc_info.value)
    
    def test_valid_statuses(self):
        """All valid statuses should be accepted."""
        from agent.subconscious.temp_memory.store import _ensure_table, update_fact_status
        
        # Ensure table exists first
        _ensure_table()
        
        valid_statuses = ['pending', 'approved', 'pending_review', 'consolidated', 'rejected']
        
        for status in valid_statuses:
            # Should not raise ValueError - we don't care if fact doesn't exist
            try:
                update_fact_status(99999, status)  # Non-existent ID
            except ValueError:
                pytest.fail(f"Status '{status}' should be valid")


class TestConsolidationThresholds:
    """Test auto-approval thresholds."""
    
    def test_auto_approve_threshold_exists(self):
        """ConsolidationLoop should have AUTO_APPROVE_THRESHOLD."""
        from agent.subconscious.loops import ConsolidationLoop
        
        assert hasattr(ConsolidationLoop, 'AUTO_APPROVE_THRESHOLD')
        assert 0.0 <= ConsolidationLoop.AUTO_APPROVE_THRESHOLD <= 1.0
    
    def test_duplicate_threshold_exists(self):
        """ConsolidationLoop should have DUPLICATE_THRESHOLD."""
        from agent.subconscious.loops import ConsolidationLoop
        
        assert hasattr(ConsolidationLoop, 'DUPLICATE_THRESHOLD')
        assert 0.0 <= ConsolidationLoop.DUPLICATE_THRESHOLD <= 1.0
    
    def test_thresholds_are_reasonable(self):
        """Thresholds should be in sensible ranges."""
        from agent.subconscious.loops import ConsolidationLoop
        
        # Auto-approve should require decent confidence
        assert ConsolidationLoop.AUTO_APPROVE_THRESHOLD >= 0.5
        
        # Duplicate detection should be strict
        assert ConsolidationLoop.DUPLICATE_THRESHOLD >= 0.8


class TestExports:
    """Test that new functions are properly exported."""
    
    def test_temp_memory_exports(self):
        """All new temp_memory functions should be exported."""
        from agent.subconscious import temp_memory
        
        assert hasattr(temp_memory, 'get_pending_review')
        assert hasattr(temp_memory, 'update_fact_status')
        assert hasattr(temp_memory, 'approve_fact')
        assert hasattr(temp_memory, 'reject_fact')
        assert hasattr(temp_memory, 'get_approved_pending')
    
    def test_get_stats_includes_status_counts(self):
        """get_stats should include pending_review and approved counts."""
        from agent.subconscious.temp_memory import get_stats
        
        stats = get_stats()
        
        assert 'pending_review' in stats
        assert 'approved' in stats


class TestAddFact:
    """Test add_fact function and its log_event integration."""
    
    def test_add_fact_logs_event_with_correct_signature(self):
        """add_fact should call log_event with correct parameters (regression test)."""
        with patch('agent.threads.log.log_event') as mock_log:
            from agent.subconscious.temp_memory import add_fact
            
            fact = add_fact(
                session_id="test-session",
                text="User likes coffee",
                source="conversation",
                metadata={"category": "preference"}
            )
            
            # Verify log_event was called with named parameters, not positional
            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            
            # These are the expected parameters for log_event
            assert 'event_type' in call_kwargs
            assert 'data' in call_kwargs
            assert 'metadata' in call_kwargs
            assert 'source' in call_kwargs
            assert 'session_id' in call_kwargs
            
            # fact_id should be in metadata, NOT as a direct kwarg
            assert 'fact_id' not in call_kwargs
            assert 'fact_id' in call_kwargs['metadata']
    
    def test_add_fact_returns_fact_object(self):
        """add_fact should return a valid Fact object."""
        from agent.subconscious.temp_memory import add_fact, Fact
        
        fact = add_fact(
            session_id="test-session-2",
            text="Test fact",
            source="test"
        )
        
        assert isinstance(fact, Fact)
        assert fact.text == "Test fact"
        assert fact.session_id == "test-session-2"
        assert fact.source == "test"
