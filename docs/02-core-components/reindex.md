# Reindex
Languages: [English](reindex.md) | [Русский](reindex_ru.md)

## Overview

The reindex service regenerates vector embeddings for all messages when the embedding model or provider changes. It runs as a background service with a priority queue and supports pause, resume, and cancel operations.

## When Reindex is Needed

Reindex is required when:
- The embedding model changes (e.g., `nomic-embed-text` to `mxbai-embed-large`)
- The embedding provider changes (e.g., Ollama to Gemini)
- The vector dimension changes

The system automatically detects when a reindex is needed via the check endpoint.

## Reindex API

### Check if Reindex is Needed

```bash
curl http://localhost:8000/api/v1/settings/reindex/check
```

### Get Reindex Status

```bash
curl http://localhost:8000/api/v1/settings/reindex/status
```

Response:

```json
{
  "running": false,
  "current_task": null,
  "queue_size": 0
}
```

### Get Reindex Stats

```bash
curl http://localhost:8000/api/v1/settings/reindex/stats
```

Response:

```json
{
  "models": {
    "nomic-embed-text": {
      "dimension": 768,
      "message_count": 50000,
      "summary_count": 200
    }
  }
}
```

### Start Reindex

```bash
curl -X POST http://localhost:8000/api/v1/settings/reindex/start \
  -H "Content-Type: application/json" \
  -d '{
    "priority": "normal",
    "model_name": "nomic-embed-text"
  }'
```

### Control Reindex

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

### Reindex History

```bash
curl http://localhost:8000/api/v1/settings/reindex/history
```

## Speed Modes

Reindex supports different speed modes to balance between completion time and system load:

| Mode | Description |
|------|-------------|
| low | Minimal impact on system, slowest |
| medium | Balanced speed and load |
| aggressive | Fastest, highest system load |

### Get Current Speed

```bash
curl http://localhost:8000/api/v1/settings/reindex/speed
```

### Change Speed

```bash
curl -X PATCH http://localhost:8000/api/v1/settings/reindex/speed \
  -H "Content-Type: application/json" \
  -d '{"mode": "aggressive"}'
```

## Architecture

```
ReindexService
  |-- TaskQueue           -- Priority queue for reindex tasks
  |-- BatchProcessor      -- Process messages in batches
  |-- TaskExecutor        -- Execute individual reindex tasks
  |-- TaskManagement      -- Create, pause, resume, cancel tasks
  |-- Repository          -- Database operations for reindex state
  |-- DirectReindex       -- Direct reindex for specific models
```

## Priority Levels

| Priority | Description |
|----------|-------------|
| high | Process before normal and low |
| normal | Default priority |
| low | Process when queue is empty of higher priorities |
