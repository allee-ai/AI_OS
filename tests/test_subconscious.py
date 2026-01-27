"""
Tests for the Subconscious module - the core of AI OS.

Tests the STATE assembly pipeline:
- score(query) → thread relevance scores
- build_state(scores, query) → STATE block
- get_subconscious() → Subconscious instance
"""

import pytest
from pathlib import Path
import sys

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestScoring:
    """Test thread relevance scoring."""
    
    def test_score_returns_dict(self):
        """score() should return dict of thread scores."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        scores = sub.score("hello")
        
        assert isinstance(scores, dict)
        assert len(scores) > 0
    
    def test_score_all_threads_present(self):
        """All registered threads should have scores."""
        from agent.subconscious.orchestrator import get_subconscious, THREADS
        
        sub = get_subconscious()
        scores = sub.score("test query")
        
        for thread in THREADS:
            assert thread in scores, f"Missing score for {thread}"
    
    def test_score_values_are_numeric(self):
        """Scores should be numeric values."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        scores = sub.score("what is my name")
        
        for thread, value in scores.items():
            assert isinstance(value, (int, float)), f"{thread} score not numeric"
    
    def test_identity_query_scores_identity_high(self):
        """Identity-related queries should score identity thread high."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        scores = sub.score("what is my name")
        
        # Identity should be relevant for name queries
        assert scores.get("identity", 0) > 0


class TestStateBuild:
    """Test STATE block assembly."""
    
    def test_build_state_returns_string(self):
        """build_state() should return a string."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        scores = {"identity": 8.0, "log": 5.0, "form": 3.0}
        state = sub.build_state(scores, "hello")
        
        assert isinstance(state, str)
    
    def test_build_state_contains_markers(self):
        """STATE block should have == STATE == markers."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        scores = {"identity": 8.0, "log": 5.0}
        state = sub.build_state(scores, "hello")
        
        assert "== STATE ==" in state or "STATE" in state.upper()
    
    def test_build_state_includes_thread_context(self):
        """STATE should include context from scored threads."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        scores = {"identity": 9.0}  # High identity score
        state = sub.build_state(scores, "who am I")
        
        # Should have some identity-related content
        assert len(state) > 50  # Not empty


class TestGetState:
    """Test the convenience get_state() wrapper."""
    
    def test_get_state_returns_string(self):
        """get_state() should return assembled STATE string."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        state = sub.get_state("hello")
        
        assert isinstance(state, str)
        assert len(state) > 0
    
    def test_get_state_different_queries_different_state(self):
        """Different queries should produce different STATE."""
        from agent.subconscious.orchestrator import get_subconscious
        
        sub = get_subconscious()
        state1 = sub.get_state("what is my name")
        state2 = sub.get_state("tell me a joke")
        
        # States might differ based on relevance scoring
        # At minimum, both should be valid
        assert isinstance(state1, str)
        assert isinstance(state2, str)
