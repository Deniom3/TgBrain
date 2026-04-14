# System API
Languages: [English](system-api.md) | [Русский](system-api_ru.md)

## Health Check

### GET /health

Returns the health status of all subsystems.

```bash
curl http://localhost:8000/health
```

Response:

```json
{
  "status": "ok",
  "components": {
    "database": "ok",
    "ollama_embeddings": "ok",
    "llm": "ok",
    "telegram": "not_configured"
  },
  "timestamp": "2026-04-10T12:00:00Z"
}
```

Component status values: `ok`, `error`, `degraded`, `not_configured`.
Overall status values: `ok`, `degraded`, `error`.

### GET /

Returns basic application information.

## System Statistics

### GET /api/v1/system/stats

Returns overall system statistics including message counts, chat counts, and service status.

```bash
curl http://localhost:8000/api/v1/system/stats
```

### GET /api/v1/system/throughput

Returns current system throughput metrics.

```bash
curl http://localhost:8000/api/v1/system/throughput
```

### GET /api/v1/system/flood-history

Returns history of FloodWait incidents from the Telegram rate limiter.

```bash
curl http://localhost:8000/api/v1/system/flood-history
```

### GET /api/v1/system/request-history

Returns recent request history.

```bash
curl http://localhost:8000/api/v1/system/request-history
```
