# Руководство по тестированию
Языки: [English](testing-guide.md) | [Русский](testing-guide_ru.md)

## Запуск тестов

### Активация виртуального окружения

```bash
venv\Scripts\activate
```

### Запуск всех тестов

```bash
pytest tests/ -v
```

### Запуск конкретного файла тестов

```bash
pytest tests/test_reindex_api.py -v
```

### Запуск конкретного класса тестов

```bash
pytest tests/test_reindex_api.py::TestSmartTrigger -v
```

### Запуск конкретного метода теста

```bash
pytest tests/test_reindex_api.py::TestSmartTrigger::test_model_change_triggers_reindex -v
```

### Пропуск медленных тестов

```bash
pytest tests/ -v -m "not slow"
```

### Запуск всех тестов (скрипт пре-коммита)

```bash
scripts\test_all.bat
```

## Структура тестов

```
tests/
  conftest.py              -- Основные тестовые фикстуры
  conftest_db.py           -- Фикстуры базы данных
  conftest_api.py          -- Фикстуры API
  conftest_fixtures.py     -- Общие фикстуры
  conftest_repositories.py -- Фикстуры репозиториев
  unit/                    -- Модульные тесты
  integration/             -- Интеграционные тесты
  e2e/                     -- Сквозные тесты
```

## Конфигурация тестов

- **pytest.ini** -- Конфигурация тестов
- **mypy.ini** -- Конфигурация проверки типов
- **Цикл событий Windows** -- conftest использует `WindowsProactorEventLoopPolicy`

## Фикстуры

Общие фикстуры предоставляются через файлы conftest:

| Фикстура | Источник | Описание |
|----------|----------|----------|
| `db_pool` | conftest_db.py | Асинхронный пул соединений с базой данных |
| `http_client` | conftest_api.py | Асинхронный HTTP тестовый клиент |
| `settings` | conftest.py | Тестовый экземпляр настроек |

## Кэш настроек

Кэш настроек следует очищать перед тестами, которые изменяют конфигурацию:

```python
from src.config import get_settings
get_settings.cache_clear()
```

## Мокирование HTTP

Тесты используют `respx` для мокирования HTTP-запросов к внешним сервисам (LLM провайдеры, сервисы эмбеддингов):

```python
import respx

@respx.mock
async def test_llm_call():
    respx.post("https://api.example.com/...").mock(
        return_value=httpx.Response(200, json={"text": "response"})
    )
    # Test code here
```

## Категории тестов

### Модульные тесты

Тестирование отдельных функций и классов изолированно. Быстрое выполнение, без базы данных.

### Интеграционные тесты

Тестирование взаимодействия между компонентами. Могут использовать тестовую базу данных.

### Сквозные тесты

Тестирование полных рабочих процессов через API. Требуют доступности всех сервисов.

## Покрытие

Генерация отчётов о покрытии:

```bash
pytest tests/ --cov=src --cov-report=html
```

Просмотр отчёта в `htmlcov/index.html`.

## Тестирование в Docker

Отдельный файл Docker Compose доступен для запуска тестов в изолированном окружении:

```bash
docker compose -f docker-compose.test.yml up
```
