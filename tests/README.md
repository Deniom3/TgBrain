# Тесты проекта

## Структура

```
tests/
├── conftest.py              # Общие фикстуры и pytest hooks
├── conftest_*.py            # Модульные фикстуры (db, api, repositories, fixtures)
├── unit/                    # Unit-тесты (запускаются по умолчанию)
├── integration/             # Integration-тесты (требуют --integration)
└── e2e/                     # End-to-end тесты (требуют --e2e)
```

## Запуск тестов

**Все unit-тесты (по умолчанию):**
```bash
pytest tests/unit/ -v
```

**Integration-тесты (требуют Docker с PostgreSQL + Ollama):**
```bash
pytest tests/integration/ -v --integration
```

**E2E-тесты (требуют полный стек):**
```bash
pytest tests/e2e/ -v --e2e
```

**Все тесты включая integration:**
```bash
pytest tests/ -v --integration
```

**Отдельный тест:**
```bash
pytest tests/unit/test_config.py -v
pytest tests/unit/test_config.py::TestSettingsLoading::test_load_from_env -v
```

**Пропустить медленные тесты:**
```bash
pytest tests/ -v -m "not slow"
```

## Reindex API тесты

Тесты переиндексации находятся в `tests/integration/test_reindex_api.py`.

**Требования:**
- Запущенное приложение: `uvicorn main:app --host 0.0.0.0 --port 8000`
- Флаг `--integration`

**Запуск:**
```bash
pytest tests/integration/test_reindex_api.py -v --integration
```

**Отдельные группы тестов:**
```bash
# Smart Trigger
pytest tests/integration/test_reindex_api.py::TestSmartTrigger -v --integration

# Миграция размерности
pytest tests/integration/test_reindex_api.py::TestDimensionMigration -v --integration

# RAG поиск
pytest tests/integration/test_reindex_api.py::TestRagAfterMigration -v --integration
```
