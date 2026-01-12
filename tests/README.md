# Tests

Automated test suite for Nola.

---

## For Users

You don't need to run tests for normal use. These are for developers to verify Nola works correctly.

---

## For Developers

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_agent.py -v

# With coverage
pytest tests/ --cov=Nola --cov-report=html
```

### Test Files

| File | What It Tests |
|------|---------------|
| `test_agent.py` | Singleton pattern, thread safety, provider toggle |
| `test_idv2.py` | Database operations, level filtering, migration |
| `test_hea.py` | Stimuli classification, context levels, token budgets |
| `conftest.py` | Shared fixtures |

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
