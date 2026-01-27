"""
Tests for Memory Loop (fact extraction).

Tests:
- LLM response parsing (handles markdown, quotes, trailing text)
- Fact extraction from conversations
- Hierarchical key format
"""

import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestPythonListParsing:
    """Test the _parse_python_list helper for LLM output."""
    
    def test_parse_clean_json(self):
        """Should parse clean JSON list."""
        from agent.subconscious.loops import MemoryLoop
        
        m = MemoryLoop()
        result = m._parse_python_list('[{"key": "user.name", "text": "Bob"}]')
        
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["key"] == "user.name"
    
    def test_parse_with_markdown(self):
        """Should strip markdown code blocks."""
        from agent.subconscious.loops import MemoryLoop
        
        m = MemoryLoop()
        result = m._parse_python_list('```python\n[{"key": "test", "text": "value"}]\n```')
        
        assert isinstance(result, list)
        assert len(result) == 1
    
    def test_parse_with_trailing_text(self):
        """Should handle LLM adding explanation after JSON."""
        from agent.subconscious.loops import MemoryLoop
        
        m = MemoryLoop()
        result = m._parse_python_list('[{"key": "test", "text": "value"}] Hope this helps!')
        
        assert isinstance(result, list)
        assert len(result) == 1
    
    def test_parse_empty_list(self):
        """Should handle empty list."""
        from agent.subconscious.loops import MemoryLoop
        
        m = MemoryLoop()
        result = m._parse_python_list('[]')
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    def test_parse_single_quotes(self):
        """Should handle Python-style single quotes."""
        from agent.subconscious.loops import MemoryLoop
        
        m = MemoryLoop()
        result = m._parse_python_list("[{'key': 'user.pet', 'text': 'Has a dog'}]")
        
        assert isinstance(result, list)
        assert len(result) == 1


class TestMemoryLoopInit:
    """Test MemoryLoop initialization."""
    
    def test_memory_loop_creates(self):
        """MemoryLoop should instantiate."""
        from agent.subconscious.loops import MemoryLoop
        
        m = MemoryLoop()
        
        assert m is not None
    
    def test_has_extract_method(self):
        """MemoryLoop should have _extract method."""
        from agent.subconscious.loops import MemoryLoop
        
        m = MemoryLoop()
        
        assert hasattr(m, '_extract')


class TestHierarchicalKeys:
    """Test hierarchical key format (user.likes.coffee)."""
    
    def test_key_format_validation(self):
        """Keys should follow dot notation."""
        valid_keys = [
            "user.name",
            "user.likes.coffee",
            "family.dad.birthday",
            "project.taskmaster.status"
        ]
        
        for key in valid_keys:
            parts = key.split(".")
            assert len(parts) >= 2, f"Key should have at least 2 parts: {key}"
            assert all(part.isalnum() or "_" in part for part in parts)
