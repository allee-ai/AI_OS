"""
Shared fixtures for AI OS tests.

Mock / Live mode
----------------
By default every test that touches the LLM uses a mock ``ollama.chat``.
Pass ``--live`` (or set ``AIOS_TEST_LIVE=1``) to hit a real Ollama instance.

    pytest tests/                   # mocked — no Ollama needed
    pytest tests/ --live            # real Ollama calls
    AIOS_TEST_LIVE=1 pytest tests/  # same thing via env

All tests run against the demo DB (AIOS_MODE=demo).
"""

import os
import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Demo mode for all tests
os.environ.setdefault("AIOS_MODE", "demo")


# ---------------------------------------------------------------------------
# --live flag
# ---------------------------------------------------------------------------

def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run tests against real Ollama instead of mocks",
    )


@pytest.fixture(scope="session")
def live_mode(request):
    """True when tests should use real Ollama."""
    return request.config.getoption("--live") or os.environ.get("AIOS_TEST_LIVE") == "1"


# ---------------------------------------------------------------------------
# Mock Ollama responses
# ---------------------------------------------------------------------------

_MOCK_CHAT_RESPONSE = {
    "message": {
        "role": "assistant",
        "content": "Hello! I'm your AI assistant. How can I help you today?",
    }
}

_MOCK_EXTRACT_RESPONSE = {
    "message": {
        "role": "assistant",
        "content": '[{"key": "user.preference.coffee", "text": "User enjoys coffee while coding"}]',
    }
}


def _mock_ollama_chat(model=None, messages=None, **kwargs):
    """Route mock responses based on the prompt content."""
    if not messages:
        return _MOCK_CHAT_RESPONSE

    last_content = messages[-1].get("content", "")

    # Fact extraction prompt
    if "Extract facts" in last_content or "Python list" in last_content:
        return _MOCK_EXTRACT_RESPONSE

    # Classification prompt (for consolidation)
    if "classify" in last_content.lower() or "identity" in last_content.lower():
        return {"message": {"role": "assistant", "content": "identity"}}

    return _MOCK_CHAT_RESPONSE


@pytest.fixture(autouse=True)
def maybe_mock_ollama(live_mode):
    """Patch ``ollama.chat`` unless --live is set."""
    if live_mode:
        yield
    else:
        with patch("ollama.chat", side_effect=_mock_ollama_chat):
            yield


# ---------------------------------------------------------------------------
# Demo DB schema sync (once per session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def ensure_schemas():
    """Run migrations on the demo DB once before any test."""
    try:
        from agent.core.migrations import ensure_all_schemas
        ensure_all_schemas()
    except Exception:
        pass
    yield


# ---------------------------------------------------------------------------
# Reusable fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_conversation():
    """3-turn conversation for pipeline tests."""
    return [
        {"role": "user", "content": "Hi, I'm working on a project called TaskMaster"},
        {"role": "assistant", "content": "Nice! Tell me more about TaskMaster."},
        {"role": "user", "content": "It's a todo app. I love coffee while coding."},
    ]


@pytest.fixture
def agent_service():
    """Create an AgentService hooked to the demo DB."""
    from agent.services.agent_service import AgentService
    svc = AgentService()
    yield svc
    svc.message_history.clear()
