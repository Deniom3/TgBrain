# Testing Guide
Languages: [English](testing-guide.md) | [Русский](testing-guide_ru.md)

## Running Tests

### Activate Virtual Environment

```bash
venv\Scripts\activate
```

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_reindex_api.py -v
```

### Run Specific Test Class

```bash
pytest tests/test_reindex_api.py::TestSmartTrigger -v
```

### Run Specific Test Method

```bash
pytest tests/test_reindex_api.py::TestSmartTrigger::test_model_change_triggers_reindex -v
```

### Skip Slow Tests

```bash
pytest tests/ -v -m "not slow"
```

### Run All Tests (Pre-commit Script)

```bash
scripts\test_all.bat
```

## Test Structure

```
tests/
  conftest.py              -- Main test fixtures
  conftest_db.py           -- Database fixtures
  conftest_api.py          -- API fixtures
  conftest_fixtures.py     -- General fixtures
  conftest_repositories.py -- Repository fixtures
  unit/                    -- Unit tests
  integration/             -- Integration tests
  e2e/                     -- End-to-end tests
```

## Test Configuration

- **pytest.ini** -- Test configuration
- **mypy.ini** -- Type checking configuration
- **Windows event loop** -- conftest uses `WindowsProactorEventLoopPolicy`

## Fixtures

Common fixtures are provided through conftest files:

| Fixture | Source | Description |
|---------|--------|-------------|
| `db_pool` | conftest_db.py | Async database connection pool |
| `http_client` | conftest_api.py | Async HTTP test client |
| `settings` | conftest.py | Test settings instance |

## Settings Cache

The settings cache should be cleared before tests that modify configuration:

```python
from src.config import get_settings
get_settings.cache_clear()
```

## HTTP Mocking

Tests use `respx` for mocking HTTP requests to external services (LLM providers, embedding services):

```python
import respx

@respx.mock
async def test_llm_call():
    respx.post("https://api.example.com/...").mock(
        return_value=httpx.Response(200, json={"text": "response"})
    )
    # Test code here
```

## Test Categories

### Unit Tests

Test individual functions and classes in isolation. Fast execution, no database.

### Integration Tests

Test interactions between components. May use a test database.

### End-to-End Tests

Test complete workflows through the API. Require all services to be available.

## Coverage

Generate coverage reports:

```bash
pytest tests/ --cov=src --cov-report=html
```

View the report in `htmlcov/index.html`.

## Docker Testing

A separate Docker Compose file is available for running tests in an isolated environment:

```bash
docker compose -f docker-compose.test.yml up
```
