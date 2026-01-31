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
pytest tests/test_api.py -v

# With coverage
pytest tests/ --cov=agent --cov-report=html
```

### Test Files

| File | What It Tests |
|------|---------------|
| `test_api.py` | API endpoints (health, chat, identity, philosophy, subconscious) |
| `test_database.py` | SQLite connections, WAL mode, closing context managers |
| `test_threads.py` | Thread adapters (identity, log, form, philosophy, reflex, linking) |
| `test_subconscious.py` | Thread scoring, state building, context injection |
| `test_memory_loop.py` | Memory consolidation and recall |
| `test_consolidation.py` | Memory consolidation logic |
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
