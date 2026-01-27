"""
Tests for Thread Adapters.

Each thread adapter provides:
- introspect(level) → IntrospectionResult with facts list at that HEA level
- get_context_string(level) or format for STATE → string context for STATE

The Subconscious uses these to build STATE.
"""

import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestIdentityThread:
    """Test identity thread adapter."""
    
    def test_adapter_instantiates(self):
        """IdentityThreadAdapter should instantiate."""
        from agent.threads.identity.adapter import IdentityThreadAdapter
        
        adapter = IdentityThreadAdapter()
        assert adapter is not None
        assert adapter._name == "identity"
    
    def test_introspect_returns_result(self):
        """introspect() should return IntrospectionResult with facts."""
        from agent.threads.identity.adapter import IdentityThreadAdapter
        
        adapter = IdentityThreadAdapter()
        result = adapter.introspect(context_level=2)
        
        # IntrospectionResult has .facts list
        assert hasattr(result, 'facts')
        assert isinstance(result.facts, list)
    
    def test_get_context_string_returns_string(self):
        """get_context_string() should return string for STATE."""
        from agent.threads.identity.adapter import IdentityThreadAdapter
        
        adapter = IdentityThreadAdapter()
        context = adapter.get_context_string(level=2)
        
        assert isinstance(context, str)


class TestLogThread:
    """Test log thread adapter."""
    
    def test_adapter_instantiates(self):
        """LogThreadAdapter should instantiate."""
        from agent.threads.log.adapter import LogThreadAdapter
        
        adapter = LogThreadAdapter()
        assert adapter is not None
        assert adapter._name == "log"
    
    def test_introspect_returns_result(self):
        """introspect() should return IntrospectionResult with facts."""
        from agent.threads.log.adapter import LogThreadAdapter
        
        adapter = LogThreadAdapter()
        result = adapter.introspect(context_level=2)
        
        assert hasattr(result, 'facts')
        assert isinstance(result.facts, list)


class TestFormThread:
    """Test form thread adapter."""
    
    def test_adapter_instantiates(self):
        """FormThreadAdapter should instantiate."""
        from agent.threads.form.adapter import FormThreadAdapter
        
        adapter = FormThreadAdapter()
        assert adapter is not None
        assert adapter._name == "form"
    
    def test_introspect_returns_result(self):
        """introspect() should return IntrospectionResult with facts."""
        from agent.threads.form.adapter import FormThreadAdapter
        
        adapter = FormThreadAdapter()
        result = adapter.introspect(context_level=2)
        
        assert hasattr(result, 'facts')
        assert isinstance(result.facts, list)


class TestPhilosophyThread:
    """Test philosophy thread adapter."""
    
    def test_adapter_instantiates(self):
        """PhilosophyThreadAdapter should instantiate."""
        from agent.threads.philosophy.adapter import PhilosophyThreadAdapter
        
        adapter = PhilosophyThreadAdapter()
        assert adapter is not None
        assert adapter._name == "philosophy"
    
    def test_introspect_returns_result(self):
        """introspect() should return IntrospectionResult with facts."""
        from agent.threads.philosophy.adapter import PhilosophyThreadAdapter
        
        adapter = PhilosophyThreadAdapter()
        result = adapter.introspect(context_level=2)
        
        assert hasattr(result, 'facts')
        assert isinstance(result.facts, list)


class TestReflexThread:
    """Test reflex thread adapter."""
    
    def test_adapter_instantiates(self):
        """ReflexThreadAdapter should instantiate."""
        from agent.threads.reflex.adapter import ReflexThreadAdapter
        
        adapter = ReflexThreadAdapter()
        assert adapter is not None
        assert adapter._name == "reflex"
    
    def test_introspect_returns_result(self):
        """introspect() should return IntrospectionResult with facts."""
        from agent.threads.reflex.adapter import ReflexThreadAdapter
        
        adapter = ReflexThreadAdapter()
        result = adapter.introspect(context_level=2)
        
        assert hasattr(result, 'facts')
        assert isinstance(result.facts, list)


class TestLinkingCoreThread:
    """Test linking_core thread adapter."""
    
    def test_adapter_instantiates(self):
        """LinkingCoreThreadAdapter should instantiate."""
        from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
        
        adapter = LinkingCoreThreadAdapter()
        assert adapter is not None
        assert adapter._name == "linking_core"
    
    def test_introspect_returns_result(self):
        """introspect() should return IntrospectionResult with summary facts."""
        from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
        
        adapter = LinkingCoreThreadAdapter()
        result = adapter.introspect(context_level=2)
        
        assert hasattr(result, 'facts')
        assert isinstance(result.facts, list)
    
    def test_score_threads_returns_dict(self):
        """score_threads() should return dict of scores."""
        from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
        
        adapter = LinkingCoreThreadAdapter()
        scores = adapter.score_threads("what is my dad's name")
        
        assert isinstance(scores, dict)
        assert len(scores) > 0
    
    def test_get_context_returns_list(self):
        """get_context() should return list of facts."""
        from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
        
        adapter = LinkingCoreThreadAdapter()
        context = adapter.get_context(query="dad", level=2)
        
        assert isinstance(context, list)
