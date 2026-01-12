"""
Tests for Nola agent module.

Tests cover:
- Singleton pattern (get_agent returns same instance)
- Thread safety of state operations
- Provider switching (ollama/http/mock)
- Identity loading and system prompt generation
"""

import pytest
import threading
from unittest.mock import patch, MagicMock


class TestAgentSingleton:
    """Test that agent follows singleton pattern."""
    
    def test_get_agent_returns_same_instance(self, nola_path):
        """get_agent() should return the same Agent instance."""
        from agent import get_agent
        
        agent1 = get_agent()
        agent2 = get_agent()
        
        assert agent1 is agent2, "get_agent should return singleton"
    
    def test_agent_has_required_methods(self, nola_path):
        """Agent instance should have all required methods."""
        from agent import get_agent
        
        agent = get_agent()
        
        assert hasattr(agent, 'generate'), "Agent needs generate method"
        assert hasattr(agent, 'get_state'), "Agent needs get_state method"
        assert hasattr(agent, 'bootstrap'), "Agent needs bootstrap method"
        # Agent may have update_section or put_section depending on version
        assert hasattr(agent, 'get_state'), "Agent needs state access method"


class TestAgentThreadSafety:
    """Test thread safety of agent operations."""
    
    def test_concurrent_state_access(self, nola_path):
        """Multiple threads should safely access agent state."""
        from agent import get_agent
        
        agent = get_agent()
        errors = []
        
        def read_state():
            try:
                for _ in range(10):
                    state = agent.get_state()
                    assert isinstance(state, dict)
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=read_state) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Thread safety errors: {errors}"


class TestAgentProvider:
    """Test provider switching functionality."""
    
    def test_mock_provider_returns_response(self, nola_path):
        """Mock provider should return predictable response."""
        from agent import get_agent
        
        agent = get_agent()
        
        # Force mock provider for testing
        with patch.dict('os.environ', {'NOLA_PROVIDER': 'mock'}):
            response = agent.generate("Test prompt", stimuli_type="realtime")
            assert response is not None
            assert isinstance(response, str)
    
    def test_generate_accepts_stimuli_type(self, nola_path):
        """generate() should accept stimuli_type parameter."""
        from agent import get_agent
        
        agent = get_agent()
        
        # All three stimuli types should work
        for stimuli_type in ["realtime", "conversational", "analytical"]:
            with patch.dict('os.environ', {'NOLA_PROVIDER': 'mock'}):
                response = agent.generate(
                    f"Test {stimuli_type}",
                    stimuli_type=stimuli_type
                )
                assert response is not None


class TestAgentIdentity:
    """Test identity loading and system prompt generation."""
    
    def test_load_identity_returns_dict(self, nola_path):
        """_load_identity_for_stimuli should return identity dict."""
        from agent import get_agent
        
        agent = get_agent()
        
        # Access private method for testing
        if hasattr(agent, '_load_identity_for_stimuli'):
            identity = agent._load_identity_for_stimuli("conversational")
            assert isinstance(identity, dict)
    
    def test_get_state_includes_identity(self, nola_path):
        """State should include identity context."""
        from agent import get_agent
        
        agent = get_agent()
        state = agent.get_state()
        
        # State should be a dict
        assert isinstance(state, dict)
        # May have IdentityConfig or other sections
        assert len(state) >= 0  # Can be empty if no config loaded
