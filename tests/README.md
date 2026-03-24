# Tests

Automated test suite for AI OS.

---

## For Users

You don't need to run tests for normal use. These are for developers to verify AI OS works correctly.

---

## For Developers

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_workspace_tools.py -v

# With coverage
pytest tests/ --cov=agent --cov-report=html

# Live LLM tests (requires Ollama running)
AIOS_TEST_LIVE=1 pytest tests/ -v --live
```

### Test Files

| File | What It Tests |
|------|---------------|
| `test_workspace_tools.py` | Workspace read/write/move/delete, registry, DB sync, settings, CLI, LLM sorting |
| `test_flows.py` | End-to-end conversation flows and agent pipeline |
| `test_pure.py` | Pure function unit tests (no DB or network) |
| `test_weights.py` | Thread scoring and weight calculations |
| `test_task_planner.py` | Task planning loop and goal decomposition |
| `live_kimi_test.py` | Live Kimi K2 workspace sorting integration test |
| `conftest.py` | Shared fixtures (demo mode, DB isolation) |
| `reset_demo.sh` | Reset demo database to clean state |
| `runtests.sh` | Convenience wrapper for running test suite |

### Test Modes

| Mode | Flag | Description |
|------|------|-------------|
| Demo (default) | `AIOS_MODE=demo` | Uses `state_demo.db`, isolated from live data |
| Live LLM | `--live` or `AIOS_TEST_LIVE=1` | Runs tests that call real LLM (Kimi K2 / Ollama) |

### Writing New Tests

```python
# tests/test_my_feature.py
import pytest

def test_my_feature():
    """Test description."""
    result = my_function()
    assert result == expected
```

### CI Integration

Tests run automatically on:
- Every push to main
- Every pull request

See `.github/workflows/ci.yml` for configuration.
