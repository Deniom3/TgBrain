# Документация TgBrain

Версия: 1.0.1
Дата: Апрель 2026

Языки: [English](README.md) | [Русский](README_ru.md)

## Обзор

TgBrain — это система суммаризации сообщений Telegram и база знаний. Она отслеживает чаты Telegram, принимает сообщения, генерирует суммаризации с помощью AI и предоставляет семантический поиск по всем сохранённым conversations (беседам).

## Быстрый старт

1. Клонируйте репозиторий
2. Скопируйте `.env.example` в `.env` и настройте параметры
3. Запустите `docker compose up -d` для запуска PostgreSQL и приложения
4. Аутентифицируйтесь в Telegram через QR-код
5. Откройте API по адресу `http://localhost:8000/docs`

## Структура документации

### Начало работы

| Документ | Описание |
|----------|----------|
| [Установка](01-getting-started/installation_ru.md) | Системные требования и способы установки |
| [Конфигурация](01-getting-started/configuration_ru.md) | Переменные окружения и справочник настроек |
| [Docker Setup](01-getting-started/docker-setup_ru.md) | Развёртывание Docker и конфигурация compose |
| [QR-аутентификация](01-getting-started/qr-auth_ru.md) | Аутентификация в Telegram через QR-код |

### Основные компоненты

| Документ | Описание |
|----------|----------|
| [Telegram Ingestion](02-core-components/telegram-ingestion_ru.md) | Приём сообщений из Telegram |
| [Суммаризация](02-core-components/summarization_ru.md) | AI-суммаризация чатов |
| [RAG Search](02-core-components/rag-search_ru.md) | Семантический поиск с RAG |
| [Rate Limiter](02-core-components/rate-limiter_ru.md) | Адаптивное ограничение частоты запросов к Telegram API |
| [LLM Providers](02-core-components/llm-providers_ru.md) | Абстракция мультипровайдерных LLM |
| [Embeddings](02-core-components/embeddings_ru.md) | Генерация векторных embeddings |
| [Batch Import](02-core-components/batch-import_ru.md) | Массовый импорт сообщений из экспорта Telegram |
| [External Ingestion](02-core-components/external-ingestion_ru.md) | Приём сообщений из внешних источников |
| [Webhook](02-core-components/webhook_ru.md) | Доставка webhook для суммаризаций |
| [Reindex](02-core-components/reindex_ru.md) | Сервис векторного реиндексирования |
| [Schedule](02-core-components/schedule_ru.md) | Плановая генерация суммаризаций |
| [Pending Cleanup](02-core-components/pending-cleanup_ru.md) | Очистка ожидающих сообщений |

### API Reference

| Документ | Описание |
|----------|----------|
| [Обзор](03-api-reference/overview_ru.md) | Введение и соглашения API |
| [Settings API](03-api-reference/settings-api_ru.md) | Все эндпоинты настроек |
| [Chat Management API](03-api-reference/chat-management-api_ru.md) | Эндпоинты управления чатами |
| [Summary API](03-api-reference/summary-api_ru.md) | Генерация и получение суммаризаций |
| [Message API](03-api-reference/message-api_ru.md) | Приём и импорт сообщений |
| [Reindex API](03-api-reference/reindex-api_ru.md) | Управление реиндексированием |
| [System API](03-api-reference/system-api_ru.md) | Системный мониторинг и статистика |
| [QR Auth API](03-api-reference/qr-auth-api_ru.md) | Эндпоинты QR-аутентификации |
| [Коды ошибок](03-api-reference/error-codes_ru.md) | Справочник кодов ошибок API |

### Архитектура

| Документ | Описание |
|----------|----------|
| [System Overview](04-architecture/system-overview_ru.md) | Высокоуровневая архитектура |
| [C4 Model](04-architecture/c4-model_ru.md) | Диаграммы архитектуры C4 |
| [Database Schema](04-architecture/database-schema_ru.md) | Справочник схемы PostgreSQL |
| [Settings Architecture](04-architecture/settings-architecture_ru.md) | Хранение и загрузка настроек |

### Интеграции

| Документ | Описание |
|----------|----------|
| [LLM Providers](05-integrations/llm-providers_ru.md) | Gemini, OpenRouter, Ollama, LM Studio |
| [Embedding Providers](05-integrations/embedding-providers_ru.md) | Ollama, Gemini, OpenRouter, LM Studio |

### Фронтенд

| Документ | Описание |
|----------|----------|
| [Integration Guide](06-frontend/integration-guide_ru.md) | Паттерны интеграции фронтенда |

### Тестирование

| Документ | Описание |
|----------|----------|
| [Testing Guide](07-testing/testing-guide_ru.md) | Запуск и написание тестов |

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Язык | Python 3.12+ |
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Database | PostgreSQL 16 + pgvector |
| Telegram Client | Telethon |
| Vector Search | HNSW (pgvector) |
| Шаблоны | Jinja2 |
| Шифрование | cryptography |
| Тестирование | pytest, pytest-asyncio |
| Контейнеризация | Docker, Docker Compose |

## Архитектура

Приложение следует слоистой архитектуре с принципами Domain-Driven Design:

```
src/
  api/              -- HTTP API layer (FastAPI routers)
  settings_api/     -- Settings HTTP API layer
  application/      -- Application services
  domain/           -- Domain models and value objects
  infrastructure/   -- Database, external services
  ingestion/        -- Telegram message ingestion
  embeddings/       -- Embedding provider implementations
  providers/        -- LLM provider implementations
  rag/              -- RAG search and summarization
  reindex/          -- Vector reindexing service
  rate_limiter/     -- Adaptive rate limiting
  schedule/         -- Cron-like scheduler
  settings/         -- Settings repositories
  webhook/          -- Webhook delivery system
  batch_import/     -- Batch import processing
  auth/             -- QR authentication
  config/           -- Configuration management
```

## Лицензия

MIT License
