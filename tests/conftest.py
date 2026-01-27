"""
Pytest configuration and shared fixtures.

Run tests with: pytest tests/ -v
Run specific file: pytest tests/test_subconscious.py -v
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment once per session."""
    import os
    
    # Use demo mode for tests (don't touch personal data)
    os.environ["AIOS_MODE"] = "demo"
    
    yield
    
    # Cleanup if needed


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database for isolated tests."""
    db_path = tmp_path / "test_state.db"
    yield db_path


@pytest.fixture
def sample_conversation():
    """Sample conversation for testing extraction."""
    return [
        {"role": "user", "content": "Hi, I'm working on a project called TaskMaster"},
        {"role": "assistant", "content": "Nice! Tell me more about TaskMaster."},
        {"role": "user", "content": "It's a todo app. I love coffee while coding."},
    ]
