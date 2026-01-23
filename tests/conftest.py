"""
Pytest configuration and shared fixtures for AI_OS test suite.

Fixtures provide isolated test environments:
- temp_db: Fresh SQLite database per test
- mock_agent: Agent with mock provider (no Ollama needed)
- sample_identity: Pre-seeded identity data
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "Agent"))


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary SQLite database for testing."""
    db_path = tmp_path / "test_state.db"
    yield db_path
    # Cleanup happens automatically with tmp_path


@pytest.fixture
def sample_identity():
    """Sample identity data for testing HEA levels."""
    return {
        "machineID": {
            "metadata": {"level": "level_1", "source": "test"},
            "data": {
                "level_1": {
                    "hostname": "test-machine",
                    "os": "TestOS"
                },
                "level_2": {
                    "hostname": "test-machine",
                    "os": "TestOS",
                    "cpu_cores": 8,
                    "memory_gb": 16
                },
                "level_3": {
                    "hostname": "test-machine",
                    "os": "TestOS",
                    "cpu_cores": 8,
                    "memory_gb": 16,
                    "gpu": "Test GPU",
                    "disk_gb": 512,
                    "network_interfaces": ["eth0", "wlan0"]
                }
            }
        },
        "userID": {
            "metadata": {"level": "level_2", "source": "test"},
            "data": {
                "level_1": {
                    "name": "Test User"
                },
                "level_2": {
                    "name": "Test User",
                    "preferences": {"theme": "dark"}
                },
                "level_3": {
                    "name": "Test User",
                    "preferences": {"theme": "dark", "language": "en"},
                    "history": ["session_1", "session_2"]
                }
            }
        }
    }


@pytest.fixture
def mock_agent_config():
    """Configuration for mock agent (no Ollama dependency)."""
    return {
        "provider": "mock",
        "model": "test-model",
        "response": "This is a mock response for testing."
    }


@pytest.fixture
def aios_path():
    """Path to agent module."""
    return PROJECT_ROOT / "Agent"


@pytest.fixture
def identity_thread_path(aios_path):
    """Path to identity_thread directory."""
    return aios_path / "identity_thread"
