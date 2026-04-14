# TgBrain

Приложение для автоматического сбора, обработки и суммаризации сообщений из Telegram-чатов с использованием LLM и векторным поиском (RAG).

## 📚 Документация

Полная документация доступна в папке [docs/](docs/):

| Раздел | Описание |
|--------|----------|
| [Быстрый старт](docs/01-getting-started/) | Установка, настройка и запуск |
| [Основные компоненты](docs/02-core-components/) | Telegram, эмбеддинги, LLM, RAG |
| **[REST API Reference](docs/03-api-reference/overview.md)** | Полный справочник всех endpoints |
| [API Reference](docs/03-api-reference/) | REST API документация |
| [Архитектура](docs/04-architecture/) | Архитектурный обзор системы |
| [Интеграции](docs/05-integrations/) | Gemini, OpenRouter, Ollama |
| [Frontend](docs/06-frontend/) | Интеграция веб-интерфейса |

## 📊 Текущее состояние

**Версия:** 1.6.0
**Последнее обновление:** 30 марта 2026 г.

### Реализованный функционал

| Компонент | Статус | Описание |
|-----------|--------|----------|
| Telegram Ingestion | ✅ | Сбор сообщений с адаптивным rate limiting |
| QR авторизация | ✅ | Вход через QR код с веб-интерфейсом |
| Эмбеддинги | ✅ | Ollama, Gemini, OpenRouter, LM Studio |
| RAG-поиск | ✅ | Семантический поиск с источниками |
| Summary (асинхронный) | ✅ | Генерация дайджестов с кэшированием |
| Summary CRUD API | ✅ | Полный CRUD для summary |
| Chat Management | ✅ | Динамическое управление мониторингом |
| Reindex Service | ✅ | Автоматическая переиндексация |
| Auto Cleanup | ✅ | Автоочистка summary задач |
| FloodWait Protection | ✅ | Адаптивный контроллер нагрузки |
| External Messages API | ✅ | Приём сообщений от ботов и вебхуков |
| Batch Import API | ✅ | Пакетный импорт из Telegram Desktop |
| Summary Webhook | ✅ | Отправка summary на webhook URL |
| REST API Reference | ✅ | Полная документация 80+ endpoints |

### Известные ограничения

| Проблема | Статус | Описание |
|----------|--------|----------|
| BackgroundTasks | | Ненадёжная очередь (требует Celery/RQ для production) |

## Legacy функционал

| Компонент | Статус | Описание |
|-----------|--------|----------|
| `/summary` endpoint | | Удалён — заменён на `/api/v1/chats/summary/generate` |
| `src/rag/summary_cache.py` | | Удалён — кэширование в `summary_task_service.py` |
| `src/api/endpoints/chat_summary.py` | | Удалён — разделён на generate/retrieval |
| Синхронная генерация summary | | Удалена — только асинхронная генерация |
| Фиксированный TTL кэша (30 мин) | | Удалён — плавающий TTL (2ч/24ч/∞) |

## Быстрый старт

### 1. Активация виртуального окружения

```bash
# Windows (cmd или PowerShell)
cd D:\Work\TgBrain
venv\Scripts\activate
```

После активации увидите `(venv)` в начале строки.

### 2. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 3. Настройка конфигурации

```bash
# Скопировать шаблон
copy .env.example .env

# Отредактировать .env с вашими данными
```

### 4. Запуск приложения

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

После запуска:
- **Swagger UI:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health
- **API:** http://localhost:8000/

## Запуск в Docker

### Требования
- Docker Desktop для Windows
- Docker Compose (входит в Docker Desktop)

### Быстрый старт

#### 1. Настроить .env
```bash
copy .env.example .env
```

Отредактировать `.env`:
- `TG_API_ID`, `TG_API_HASH` (из https://my.telegram.org)
- `DB_PASSWORD` (придумать пароль)
- `OLLAMA_EMBEDDING_URL=http://host.docker.internal:11434` (для доступа к локальному Ollama)
- `LLM_ACTIVE_PROVIDER=gemini` (или другой провайдер)
- `GEMINI_API_KEY=...` (API ключ)

#### 2. Запустить сервисы
```bash
docker-compose up -d
```

#### 3. Проверить статус
```bash
docker-compose ps
docker-compose logs -f app
```

#### 4. Проверить API
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"question\": \"О чём этот чат?\"}"
```

#### 5. Остановка
```bash
docker-compose down
```

### Важные замечания

1. **Ollama Embeddings:** Для доступа к локальному Ollama из контейнера:
   - Windows: `OLLAMA_EMBEDDING_URL=http://host.docker.internal:11434`
   - Убедитесь, что Ollama запущен на хосте

2. **Telegram сессия:** При первом запуске потребуется ввести телефон и код подтверждения
   - Сессия сохранится в `./sessions/`

3. **Персистентность:**
   - **База данных:** Сохраняется в `./data/postgres/`
   - Сессии Telegram в `./sessions/`

4. **Полный сброс:**
   ```bash
   docker-compose down -v
   ```

## REST API

### Основные endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/` | GET | Информация об API |
| `/health` | GET | Проверка здоровья компонентов |
| `/api/v1/ask` | POST | Семантический поиск с источниками |
| `/docs` | GET | Swagger UI (интерактивная документация) |

### Управление настройками

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/v1/settings/overview` | GET | Общий обзор настроек |
| `/api/v1/settings/telegram` | GET/PUT | Настройки Telegram |
| `/api/v1/settings/telegram/qr-code` | POST | Создать сессию QR авторизации |
| `/api/v1/settings/telegram/qr-status/{session_id}` | GET | Статус QR авторизации |
| `/api/v1/settings/llm` | GET | Все LLM провайдеры |
| `/api/v1/settings/llm/{name}/activate` | POST | Активировать LLM провайдер |
| `/api/v1/settings/embedding` | GET | Все провайдеры эмбеддингов |
| `/api/v1/settings/embedding/{name}/activate` | POST | Активировать провайдер эмбеддингов |
| `/api/v1/settings/app/{key}` | GET/PUT | Настройки приложения |
| `/api/v1/settings/chats` | GET | Все настройки чатов |
| `/api/v1/settings/chats/monitored` | GET | Только monitored чаты |
| `/api/v1/settings/chats/{chat_id}/enable` | POST | Включить мониторинг чата |
| `/api/v1/settings/chats/{chat_id}/disable` | POST | Отключить мониторинг чата |
| `/api/v1/settings/chats/{chat_id}/toggle` | POST | Переключить мониторинг |
| `/api/v1/settings/chats/bulk-update` | POST | Массовое обновление |
| `/api/v1/settings/chats/sync` | POST | Синхронизация с Telegram |
| `/api/v1/settings/chats/user/add` | POST | Добавить пользователя |
| `/api/v1/settings/chats/user/remove` | POST | Отключить пользователя |

### Управление Summary (настройки)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/v1/settings/chats/{chat_id}/summary/enable` | POST | Включить генерацию summary |
| `/api/v1/settings/chats/{chat_id}/summary/disable` | POST | Отключить генерацию summary |
| `/api/v1/settings/chats/{chat_id}/summary/toggle` | POST | Переключить статус summary |
| `/api/v1/settings/chats/{chat_id}/summary/period` | PUT/GET | Установить/получить период сбора |
| `/api/v1/settings/chats/{chat_id}/summary/schedule` | PUT/GET/DELETE | Управление расписанием |
| `/api/v1/settings/chats/{chat_id}/summary/custom-prompt` | PUT/GET/DELETE | Кастомный промпт |
| `/api/v1/settings/chats/{chat_id}/summary/settings` | GET | Все настройки summary |

### Генерация Summary (CRUD)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/v1/chats/{chat_id}/summary/generate` | POST | Генерация summary для одного чата (асинхронно) |
| `/api/v1/chats/summary/generate` | POST | Генерация summary для всех чатов (асинхронно) |
| `/api/v1/chats/{chat_id}/summary` | GET | Список summary (с пагинацией) |
| `/api/v1/chats/{chat_id}/summary/latest` | GET | Последнее summary |
| `/api/v1/chats/{chat_id}/summary/{id}` | GET | Конкретное summary по ID |
| `/api/v1/chats/{chat_id}/summary/{id}` | DELETE | Удалить summary |
| `/api/v1/chats/{chat_id}/summary/cleanup` | POST | Очистка старых summary |
| `/api/v1/chats/summary/stats` | GET | Статистика по всем чатам |

### Управление переиндексацией

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/v1/settings/reindex/check` | GET | Проверить необходимость переиндексации |
| `/api/v1/settings/reindex/status` | GET | Статус переиндексации |
| `/api/v1/settings/reindex/stats` | GET | Статистика по моделям |
| `/api/v1/settings/reindex/start` | POST | Запустить переиндексацию |
| `/api/v1/settings/reindex/cancel` | POST | Отменить переиндексацию |

### Системные endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/v1/system/stats` | GET | Статистика системы |
| `/api/v1/system/rate-limiter/stats` | GET | Статистика rate limiter |
| `/api/v1/system/rate-limiter/incidents` | GET | История FloodWait инцидентов |

### Примеры запросов

**Проверка здоровья:**
```bash
curl http://localhost:8000/health
```

**Поиск по базе знаний:**
```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"О чём этот чат?\"}"
```

**Генерация summary (асинхронно):**
```bash
# Для одного чата
curl -X POST http://localhost:8000/api/v1/chats/-1009999999001/summary/generate \
  -H "Content-Type: application/json" \
  -d "{\"period_minutes\": 1440}"

# Ответ:
# {
#   "task_id": 84,
#   "status": "pending",
#   "from_cache": false
# }

# Для всех чатов
curl -X POST http://localhost:8000/api/v1/chats/summary/generate \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Получение summary:**
```bash
# Последнее summary чата
curl http://localhost:8000/api/v1/chats/-1009999999001/summary/latest

# Список summary (с пагинацией)
curl "http://localhost:8000/api/v1/chats/-1009999999001/summary?limit=10&offset=0"

# Конкретное summary по ID
curl http://localhost:8000/api/v1/chats/-1009999999001/summary/84
```

**Проверка настроек:**
```bash
curl http://localhost:8000/api/v1/settings/overview
```

**Управление Summary (настройки):**
```bash
# Включить summary для чата
curl -X POST http://localhost:8000/api/v1/settings/chats/-1009999999001/summary/enable

# Установить период сбора (12 часов)
curl -X PUT http://localhost:8000/api/v1/settings/chats/-1009999999001/summary/period \
  -H "Content-Type: application/json" \
  -d '{"period_minutes": 720}'

# Установить расписание (ежедневно в 9:00)
curl -X PUT http://localhost:8000/api/v1/settings/chats/-1009999999001/summary/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "09:00"}'

# Получить все настройки summary
curl http://localhost:8000/api/v1/settings/chats/-1009999999001/summary/settings
```

## Проверка работоспособности

```bash
# Тест API
python tests\test_api.py

# Тест конфигурации
python tests\test_config.py

# Тест БД
python tests\test_database.py
```

## Структура проекта

```
TgBrain/
├── venv/                   # Виртуальное окружение
├── src/
│   ├── config/             # Конфигурация (settings, providers, loader)
│   ├── models/             # Модели данных и SQL запросы
│   ├── embeddings/         # Эмбеддинги (клиент + провайдеры)
│   ├── ingestion/          # Сбор сообщений (ingester, фильтры, saver)
│   ├── rag/                # RAG-поиск и суммаризация
│   ├── providers/          # LLM провайдеры (Gemini, OpenRouter, Ollama)
│   ├── settings/           # Репозитории настроек
│   ├── settings_api/       # API для управления настройками
│   ├── database.py         # PostgreSQL подключения
│   ├── llm_client.py       # LLM клиент
│   ├── reindex.py          # Переиндексация эмбеддингов
│   └── settings_initializer.py
├── tests/                  # Тесты
├── scripts/
│   ├── utility/            # Утилиты проверки
│   └── maintenance/        # Скрипты обслуживания
├── docs/                   # Документация
├── main.py                 # FastAPI приложение
├── requirements.txt
├── .env.example
└── docker-compose.yml
```

## Требования

- **Python 3.10+**
- **PostgreSQL 14+** с расширением pgvector
- **Ollama сервер** (локально) — опционально
- **Telegram API credentials** (api_id, api_hash, phone)
- **Docker Desktop** (опционально, для контейнеризации)

## Разработка

### Запуск тестов

```bash
pytest tests/ -v
```

### Утилиты

```bash
# Проверка конфигурации
python scripts/utility/check_config.py

# Проверка БД
python scripts/utility/check_db_messages.py

# Запуск ingestion
python scripts/maintenance/run_ingester.py
```

## Лицензия

MIT
