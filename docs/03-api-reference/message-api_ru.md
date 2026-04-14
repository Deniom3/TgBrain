# Message API
Языки: [English](message-api.md) | [Русский](message-api_ru.md)

## Внешний ingest сообщений

### POST /api/v1/messages/ingest

Ingest сообщения из внешнего источника (бот, вебхук, кастомное приложение).

```bash
curl -X POST http://localhost:8000/api/v1/messages/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": -1001234567890,
    "text": "Message content",
    "date": "2026-04-01T10:00:00Z",
    "sender_id": 123456,
    "sender_name": "Bot Name",
    "is_bot": true,
    "is_action": false
  }'
```

Полные детали смотрите в [External Ingestion](../02-core-components/external-ingestion_ru.md).

## Пакетный импорт

### POST /api/v1/messages/import

Загрузить JSON-файл экспорта Telegram Desktop для пакетного импорта.

```bash
curl -X POST http://localhost:8000/api/v1/messages/import \
  -F "file=@result.json" \
  -F "chat_id=-1001234567890"
```

### GET /api/v1/messages/import/{task_id}/progress

Проверить прогресс задачи импорта.

```bash
curl http://localhost:8000/api/v1/messages/import/{task_id}/progress
```

### DELETE /api/v1/messages/import/{task_id}/cancel

Отменить задачу импорта.

```bash
curl -X DELETE http://localhost:8000/api/v1/messages/import/{task_id}/cancel
```

Полные детали смотрите в [Batch Import](../02-core-components/batch-import_ru.md).
