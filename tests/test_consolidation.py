"""
Tests for Consolidation Loop
============================
Tests for fact scoring, classification, and promotion to long-term memory.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestFactClassification:
    """Test fact classification into identity vs philosophy."""
    
    def test_classify_identity_name(self):
        """Name facts should route to identity."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        assert loop._classify_fact_destination("My name is Sarah") == "identity"
        assert loop._classify_fact_destination("I'm called Jordan") == "identity"
        assert loop._classify_fact_destination("I am a software engineer") == "identity"
    
    def test_classify_identity_preferences(self):
        """Preference facts should route to identity."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        assert loop._classify_fact_destination("I like Python") == "identity"
        assert loop._classify_fact_destination("My favorite color is blue") == "identity"
        assert loop._classify_fact_destination("I prefer dark mode") == "identity"
        assert loop._classify_fact_destination("I enjoy hiking on weekends") == "identity"
    
    def test_classify_identity_location(self):
        """Location facts should route to identity."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        assert loop._classify_fact_destination("I live in Austin") == "identity"
        assert loop._classify_fact_destination("I work at a tech startup") == "identity"
        assert loop._classify_fact_destination("My job is data science") == "identity"
    
    def test_classify_philosophy_beliefs(self):
        """Belief statements should route to philosophy."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        assert loop._classify_fact_destination("I believe honesty is important") == "philosophy"
        assert loop._classify_fact_destination("I think that kindness matters most") == "philosophy"
        assert loop._classify_fact_destination("My belief is that everyone deserves respect") == "philosophy"
    
    def test_classify_philosophy_values(self):
        """Value statements should route to philosophy."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        assert loop._classify_fact_destination("I value integrity above all") == "philosophy"
        assert loop._classify_fact_destination("Family is important to me") == "philosophy"
        assert loop._classify_fact_destination("What matters is being authentic") == "philosophy"
    
    def test_classify_philosophy_principles(self):
        """Principle statements should route to philosophy."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        assert loop._classify_fact_destination("I always try to be fair") == "philosophy"
        assert loop._classify_fact_destination("I never want to compromise on ethics") == "philosophy"
        assert loop._classify_fact_destination("My principle is to treat others well") == "philosophy"
    
    def test_classify_philosophy_ethics(self):
        """Ethical statements should route to philosophy."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        assert loop._classify_fact_destination("Lying is wrong") == "philosophy"
        assert loop._classify_fact_destination("We should help others") == "philosophy"
        assert loop._classify_fact_destination("It's right to stand up for justice") == "philosophy"
    
    def test_classify_ambiguous_defaults_to_identity(self):
        """Ambiguous facts should default to identity."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        # Neutral facts default to identity
        assert loop._classify_fact_destination("Has two cats") == "identity"
        assert loop._classify_fact_destination("Uses VS Code") == "identity"


class TestKeyGeneration:
    """Test hierarchical key generation."""
    
    def test_generate_key_identity_name(self):
        """Name facts get identity.name category."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        key = loop._generate_key("My name is Sarah", "identity")
        assert key.startswith("user.identity.")
        assert "sarah" in key.lower()
    
    def test_generate_key_identity_preferences(self):
        """Preference facts get preferences category."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        key = loop._generate_key("I love hiking", "identity")
        assert key.startswith("user.preferences.")
    
    def test_generate_key_identity_professional(self):
        """Work facts get professional category."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        key = loop._generate_key("I work as a developer", "identity")
        assert key.startswith("user.professional.")
    
    def test_generate_key_philosophy_beliefs(self):
        """Philosophy beliefs get beliefs category."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        key = loop._generate_key("I believe in being honest", "philosophy")
        assert key.startswith("philosophy.beliefs.")
    
    def test_generate_key_philosophy_values(self):
        """Philosophy values get values category."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        key = loop._generate_key("Family is important to me", "philosophy")
        assert key.startswith("philosophy.values.")
    
    def test_generate_key_philosophy_ethics(self):
        """Ethical statements get ethics category."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        # "should" and "wrong" trigger ethics
        key = loop._generate_key("Lying is wrong and we should avoid it", "philosophy")
        assert key.startswith("philosophy.ethics.")
    
    def test_generate_key_removes_stop_words(self):
        """Keys should not include common stop words."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        key = loop._generate_key("I really like the color blue", "identity")
        # "I", "really", "the" should be stripped
        assert "_i_" not in key
        assert "_the_" not in key
        assert "_really_" not in key


class TestConfidenceScoring:
    """Test confidence score calculation."""
    
    def test_confidence_base_score(self):
        """Facts start with base confidence."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        # Mock embedding function to return None (fallback mode)
        def mock_get_embedding(text):
            return None
        
        confidence = loop._calculate_confidence(
            "Short fact",
            [],  # No existing facts
            mock_get_embedding,
            lambda a, b: 0.0,
            lambda q, t: 0.0
        )
        
        assert 0.0 <= confidence <= 1.0
    
    def test_confidence_longer_facts_score_higher(self):
        """Longer, more detailed facts should score higher."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        def mock_get_embedding(text):
            return None
        
        short_confidence = loop._calculate_confidence(
            "Likes blue",
            [],
            mock_get_embedding,
            lambda a, b: 0.0,
            lambda q, t: 0.0
        )
        
        long_confidence = loop._calculate_confidence(
            "User prefers the color blue for their workspace theme and UI elements",
            [],
            mock_get_embedding,
            lambda a, b: 0.0,
            lambda q, t: 0.0
        )
        
        assert long_confidence >= short_confidence
    
    def test_confidence_specific_facts_score_higher(self):
        """Facts with proper nouns/specifics should score higher."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        def mock_get_embedding(text):
            return None
        
        generic_confidence = loop._calculate_confidence(
            "likes programming languages",
            [],
            mock_get_embedding,
            lambda a, b: 0.0,
            lambda q, t: 0.0
        )
        
        specific_confidence = loop._calculate_confidence(
            "Sarah prefers Python over JavaScript",
            [],
            mock_get_embedding,
            lambda a, b: 0.0,
            lambda q, t: 0.0
        )
        
        assert specific_confidence > generic_confidence
    
    def test_confidence_empty_fact_returns_zero(self):
        """Empty facts should return 0 confidence."""
        from agent.subconscious.loops import ConsolidationLoop
        loop = ConsolidationLoop()
        
        confidence = loop._calculate_confidence(
            "",
            [],
            lambda t: None,
            lambda a, b: 0.0,
            lambda q, t: 0.0
        )
        
        assert confidence == 0.0


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
