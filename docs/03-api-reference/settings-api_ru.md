# Settings API
Языки: [English](settings-api.md) | [Русский](settings-api_ru.md)

Все эндпоинты настроек используют префикс `/api/v1/settings`.

## Обзор настроек

### GET /api/v1/settings/overview

Возвращает сводку всех настроенных параметров.

```bash
curl http://localhost:8000/api/v1/settings/overview
```

## Настройки Telegram

### GET /api/v1/settings/telegram

Получить настройки аутентификации Telegram.

### PUT /api/v1/settings/telegram

Обновить настройки аутентификации Telegram.

```bash
curl -X PUT http://localhost:8000/api/v1/settings/telegram \
  -H "Content-Type: application/json" \
  -d '{
    "api_id": 123456,
    "api_hash": "your-api-hash"
  }'
```

### GET /api/v1/settings/telegram/check

Проверить работоспособность Telegram-сессии.

## Настройки LLM Provider

### GET /api/v1/settings/llm

Список всех настроенных LLM провайдеров.

### GET /api/v1/settings/llm/{provider_name}

Получить конфигурацию конкретного LLM провайдера.

### PUT /api/v1/settings/llm/{provider_name}

Обновить настройки LLM провайдера.

### POST /api/v1/settings/llm/{provider_name}/activate

Установить провайдер как активный LLM провайдер.

### POST /api/v1/settings/llm/{provider_name}/check

Проверить подключение провайдера.

## Настройки Embedding Provider

### GET /api/v1/settings/embedding

Список всех настроенных embedding провайдеров.

### GET /api/v1/settings/embedding/{provider_name}

Получить конфигурацию конкретного embedding провайдера.

### PUT /api/v1/settings/embedding/{provider_name}

Обновить настройки embedding провайдера.

### PUT /api/v1/settings/embedding/{provider_name}/model

Обновить embedding модель для провайдера.

### POST /api/v1/settings/embedding/{provider_name}/activate

Установить провайдер как активный embedding провайдер.

### POST /api/v1/settings/embedding/{provider_name}/check

Проверить подключение провайдера.

### POST /api/v1/settings/embedding/{provider_name}/refresh-dimension

Обновить размерность embedding (только Ollama).

## Настройки приложения

### GET /api/v1/settings/app

Список всех настроек приложения.

### GET /api/v1/settings/app/{setting_key}

Получить конкретный параметр приложения.

### PUT /api/v1/settings/app/{setting_key}

Обновить параметр приложения.

```bash
curl -X PUT http://localhost:8000/api/v1/settings/app/pending.ttl_minutes \
  -H "Content-Type: application/json" \
  -d '{"value": 480}'
```

### PUT /api/v1/settings/app/timezone

Установить часовой пояс приложения.

## Настройки чатов

### GET /api/v1/settings/chats

Список всех настроек чатов.

### GET /api/v1/settings/chats/list

Список чатов с метаданными.

### GET /api/v1/settings/chats/monitored

Список только отслеживаемых чатов.

### GET /api/v1/settings/chats/{chat_id}

Получить конфигурацию конкретного чата.

### PUT /api/v1/settings/chats/{chat_id}

Обновить настройки чата.

### DELETE /api/v1/settings/chats/{chat_id}

Удалить чат из настроек.

### POST /api/v1/settings/chats/{chat_id}/toggle

Переключить мониторинг для чата.

### POST /api/v1/settings/chats/{chat_id}/enable

Включить мониторинг для чата.

### POST /api/v1/settings/chats/{chat_id}/disable

Отключить мониторинг для чата.

### POST /api/v1/settings/chats/bulk-update

Обновить несколько чатов одновременно.

### POST /api/v1/settings/chats/sync

Синхронизировать список чатов с Telegram.

### POST /api/v1/settings/chats/user/add

Добавить пользователя для мониторинга.

### POST /api/v1/settings/chats/user/remove

Удалить пользователя из мониторинга.

## Настройки сводок чатов

### POST /api/v1/settings/chats/{chat_id}/summary/enable

Включить генерацию сводок для чата.

### POST /api/v1/settings/chats/{chat_id}/summary/disable

Отключить генерацию сводок для чата.

### POST /api/v1/settings/chats/{chat_id}/summary/toggle

Переключить генерацию сводок.

### PUT /api/v1/settings/chats/{chat_id}/summary/period

Установить период сводки в минутах.

### PUT /api/v1/settings/chats/{chat_id}/summary/schedule

Установить расписание сводок (формат HH:MM или cron).

### GET /api/v1/settings/chats/{chat_id}/summary/schedule

Получить текущее расписание сводок.

### DELETE /api/v1/settings/chats/{chat_id}/summary/schedule

Очистить расписание сводок.

### PUT /api/v1/settings/chats/{chat_id}/summary/prompt

Установить кастомный промпт для сводки.

### GET /api/v1/settings/chats/{chat_id}/summary/prompt

Получить кастомный промпт для сводки.

### DELETE /api/v1/settings/chats/{chat_id}/summary/prompt

Очистить кастомный промпт для сводки.

## Настройки вебхуков чатов

### PUT /api/v1/settings/chats/{chat_id}/webhook/config

Установить конфигурацию вебхука.

### GET /api/v1/settings/chats/{chat_id}/webhook/config

Получить конфигурацию вебхука.

### DELETE /api/v1/settings/chats/{chat_id}/webhook/config

Отключить вебхук для чата.

### POST /api/v1/settings/chats/{chat_id}/webhook/test

Протестировать доставку вебхука.

## Настройки QR Auth

### GET /api/v1/settings/telegram/auth-status

Проверить статус аутентификации Telegram.

### POST /api/v1/settings/telegram/logout

Выйти из Telegram-сессии.

### POST /api/v1/settings/telegram/qr-code

Создать новую сессию аутентификации через QR-код.

### GET /api/v1/settings/telegram/qr-status/{session_id}

Проверить статус сессии аутентификации через QR-код.

### POST /api/v1/settings/telegram/qr-cancel/{session_id}

Отменить сессию аутентификации через QR-код.

## Настройки Reindex

Полную документацию смотрите в [Reindex API](reindex-api_ru.md).
