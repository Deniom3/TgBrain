# Summary API
Языки: [English](summary-api.md) | [Русский](summary-api_ru.md)

## Генерация сводок

### Генерация для одного чата

```bash
POST /api/v1/chats/{chat_id}/summary/generate
```

Тело запроса:

```json
{
  "period_minutes": 1440,
  "period_start": "2026-04-01T00:00:00Z",
  "period_end": "2026-04-02T00:00:00Z",
  "custom_prompt": "Optional custom prompt",
  "max_messages": 100,
  "use_cache": true
}
```

Ответ:

```json
{
  "task_id": "uuid",
  "status": "pending",
  "from_cache": false
}
```

### Генерация для всех чатов

```bash
POST /api/v1/chats/summary/generate
```

## Получение сводок

### Список сводок

```bash
GET /api/v1/chats/{chat_id}/summary?limit=10&offset=0
```

Параметры запроса:
- `limit` -- Количество сводок для возврата (по умолчанию: 10)
- `offset` -- Количество сводок для пропуска (по умолчанию: 0)

### Получить последнюю сводку

```bash
GET /api/v1/chats/{chat_id}/summary/latest
```

### Получить сводку по ID или статус задачи

```bash
GET /api/v1/chats/{chat_id}/summary/{summary_id}
```

Этот эндпоинт возвращает либо завершённую сводку, либо статус задачи:

Ответ для ожидающей/обрабатываемой задачи:

```json
{
  "id": "task-uuid",
  "chat_id": -1001234567890,
  "period_start": "2026-04-01T00:00:00Z",
  "period_end": "2026-04-02T00:00:00Z",
  "status": "pending",
  "text": null,
  "created_at": "2026-04-02T09:00:00Z",
  "updated_at": "2026-04-02T09:00:00Z"
}
```

Ответ для завершённой сводки:

```json
{
  "id": 123,
  "chat_id": -1001234567890,
  "period_start": "2026-04-01T00:00:00Z",
  "period_end": "2026-04-02T00:00:00Z",
  "status": "completed",
  "text": "Summary content...",
  "generated_at": "2026-04-02T09:01:00Z",
  "message_count": 150,
  "created_at": "2026-04-02T09:00:00Z",
  "updated_at": "2026-04-02T09:01:00Z"
}
```

## Управление сводками

### Удалить сводку

```bash
DELETE /api/v1/chats/{chat_id}/summary/{summary_id}
```

### Очистка старых сводок

```bash
POST /api/v1/chats/{chat_id}/summary/cleanup
```

### Статистика сводок

```bash
GET /api/v1/chats/summary/stats
```

## Отправка сводки в вебхук

```bash
POST /api/v1/chats/{chat_id}/summary/send-webhook
```

Генерирует сводку и отправляет её на настроенный URL вебхука для чата.
