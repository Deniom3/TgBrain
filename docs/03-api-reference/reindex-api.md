# Reindex API
Languages: [English](reindex-api.md) | [Русский](reindex-api_ru.md)

All endpoints are under `/api/v1/settings/reindex`.

## Check Reindex Need

### GET /api/v1/settings/reindex/check

Returns whether a reindex is needed based on embedding model changes. Checks both messages and summaries.

```bash
curl http://localhost:8000/api/v1/settings/reindex/check
```

Response:

```json
{
  "needs_reindex": true,
  "messages_to_reindex": 150,
  "summaries_to_reindex": 12,
  "current_model": "nomic-embed-text",
  "recommendation": "Переиндексация желательна: значительная часть сообщений использует другие модели | Включая 50 сообщений без эмбеддинга",
  "messages_without_embedding": 50,
  "summaries_without_embedding": 3
}
```

## Embedding Model Stats

### GET /api/v1/settings/reindex/stats

Returns distribution of messages and summaries across embedding models.

```bash
curl http://localhost:8000/api/v1/settings/reindex/stats
```

Response:

```json
{
  "models": [
    {
      "model_name": "nomic-embed-text",
      "message_count": 5000,
      "summary_count": 120,
      "first_message": "2026-01-01T00:00:00Z",
      "last_message": "2026-04-01T12:00:00Z"
    }
  ],
  "total_messages": 5000,
  "total_summaries": 120,
  "models_count": 1
}
```

## Reindex Status

### GET /api/v1/settings/reindex/status

Returns the current status of the reindex service including progress for both messages and summaries.

```bash
curl http://localhost:8000/api/v1/settings/reindex/status
```

Response:

```json
{
  "background_running": true,
  "paused": false,
  "is_running": true,
  "current_task": {
    "id": "task-123",
    "target_model": "nomic-embed-text"
  },
  "queued_tasks": 2,
  "stats": {},
  "progress": {
    "messages_progress_percent": 45.2,
    "summaries_progress_percent": 0.0,
    "total_progress_percent": 40.5
  }
}
```

## Start Reindex

### POST /api/v1/settings/reindex/start

Start a reindex operation.

```bash
curl -X POST http://localhost:8000/api/v1/settings/reindex/start \
  -H "Content-Type: application/json" \
  -d '{
    "batch_size": 50,
    "delay_between_batches": 1.0,
    "async_mode": true,
    "priority": "normal",
    "include_summaries": true
  }'
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `batch_size` | int | from settings | Messages per batch (10-1000) |
| `delay_between_batches` | float | from settings | Delay between batches in seconds (0-10) |
| `async_mode` | bool | false | Background mode with queue |
| `priority` | string | "normal" | Priority: low, normal, high (only with async_mode) |
| `include_summaries` | bool | true | Include summary reindexing |

Response (async):

```json
{
  "status": "scheduled",
  "task_id": "task-123",
  "message": "Переиндексация запланирована (ID: task-123, приоритет: NORMAL)"
}
```

Response (sync):

```json
{
  "status": "started",
  "message": "Переиндексация запущена (batch_size=50, delay=1.0)"
}
```

## Control Reindex

### POST /api/v1/settings/reindex/control

Pause, resume, or cancel a running reindex.

```bash
# Pause
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'

# Resume
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'

# Cancel
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "cancel"}'
```

## Reindex History

### GET /api/v1/settings/reindex/history

Returns history of reindex tasks.

```bash
curl http://localhost:8000/api/v1/settings/reindex/history?limit=10
```

Response:

```json
{
  "tasks": [
    {
      "id": "task-123",
      "status": "completed",
      "priority": 1,
      "target_model": "nomic-embed-text",
      "total_messages": 5000,
      "total_summaries": 120,
      "processed_count": 5000,
      "summaries_processed_count": 120,
      "failed_count": 0,
      "summaries_failed_count": 0,
      "progress_percent": 100.0,
      "summaries_progress_percent": 100.0,
      "total_progress_percent": 100.0,
      "created_at": "2026-04-01T10:00:00Z",
      "completed_at": "2026-04-01T11:30:00Z",
      "error": null,
      "includes_summaries": true
    }
  ],
  "total": 1
}
```

## Speed Control

### GET /api/v1/settings/reindex/speed

Get the current reindex speed mode.

```bash
curl http://localhost:8000/api/v1/settings/reindex/speed
```

Response:

```json
{
  "speed_mode": "medium",
  "batch_size": 50,
  "delay_between_batches": 1.0,
  "description": "Средняя скорость: 50 сообщений, задержка 1 сек (баланс)"
}
```

### PATCH /api/v1/settings/reindex/speed

Update the reindex speed mode.

```bash
curl -X PATCH http://localhost:8000/api/v1/settings/reindex/speed \
  -H "Content-Type: application/json" \
  -d '{"speed_mode": "aggressive"}'
```

| Mode | Batch Size | Delay | Description |
|------|------------|-------|-------------|
| `low` | 20 | 3.0s | Low speed: safe mode |
| `medium` | 50 | 1.0s | Medium speed: balanced |
| `aggressive` | 100 | 0.5s | Aggressive: maximum speed |
