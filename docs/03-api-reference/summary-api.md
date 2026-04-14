# Summary API
Languages: [English](summary-api.md) | [Русский](summary-api_ru.md)

## Summary Generation

### Generate for Single Chat

```bash
POST /api/v1/chats/{chat_id}/summary/generate
```

Request body:

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

Response:

```json
{
  "task_id": "uuid",
  "status": "pending",
  "from_cache": false
}
```

### Generate for All Chats

```bash
POST /api/v1/chats/summary/generate
```

## Summary Retrieval

### List Summaries

```bash
GET /api/v1/chats/{chat_id}/summary?limit=10&offset=0
```

Query parameters:
- `limit` -- Number of summaries to return (default: 10)
- `offset` -- Number of summaries to skip (default: 0)

### Get Latest Summary

```bash
GET /api/v1/chats/{chat_id}/summary/latest
```

### Get Summary by ID or Task Status

```bash
GET /api/v1/chats/{chat_id}/summary/{summary_id}
```

This endpoint returns either a completed summary or task status:

Response for pending/processing task:

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

Response for completed summary:

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

## Summary Management

### Delete Summary

```bash
DELETE /api/v1/chats/{chat_id}/summary/{summary_id}
```

### Cleanup Old Summaries

```bash
POST /api/v1/chats/{chat_id}/summary/cleanup
```

### Summary Statistics

```bash
GET /api/v1/chats/summary/stats
```

## Send Summary to Webhook

```bash
POST /api/v1/chats/{chat_id}/summary/send-webhook
```

Generates a summary and sends it to the configured webhook URL for the chat.
