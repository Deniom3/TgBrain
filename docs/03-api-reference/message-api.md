# Message API
Languages: [English](message-api.md) | [Русский](message-api_ru.md)

## External Message Ingestion

### POST /api/v1/messages/ingest

Ingest a message from an external source (bot, webhook, custom application).

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

See [External Ingestion](../02-core-components/external-ingestion.md) for full details.

## Batch Import

### POST /api/v1/messages/import

Upload a Telegram Desktop export JSON file for batch import, or pass JSON data directly.

**File upload:**

```bash
curl -X POST http://localhost:8000/api/v1/messages/import \
  -F "file=@result.json" \
  -F "chat_id=-1001234567890"
```

**Direct JSON (up to 1000 messages):**

```bash
curl -X POST http://localhost:8000/api/v1/messages/import \
  -F "json_data={\"messages\":[{\"id\":1,\"text\":\"Hello\",\"date\":\"2026-04-01T10:00:00\"}]}" \
  -F "chat_id=-1001234567890"
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | No | JSON export file (up to 500MB) |
| `json_data` | string | No | JSON data directly (up to 1000 messages) |
| `chat_id` | integer | No | Override chat ID (takes priority over file) |

Either `file` or `json_data` must be provided, but not both.

Response:

```json
{
  "task_id": "abc-123-def",
  "status": "accepted",
  "messages_count": 150,
  "chat_id": -1001234567890
}
```

### GET /api/v1/messages/import/{task_id}/progress

Check import task progress.

```bash
curl http://localhost:8000/api/v1/messages/import/{task_id}/progress
```

### DELETE /api/v1/messages/import/{task_id}/cancel

Cancel an import task.

```bash
curl -X DELETE http://localhost:8000/api/v1/messages/import/{task_id}/cancel
```

See [Batch Import](../02-core-components/batch-import.md) for full details.
