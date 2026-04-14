# Summarization
Languages: [English](summarization.md) | [Русский](summarization_ru.md)

## Overview

The summarization system generates AI-powered digest summaries of chat activity over configurable time periods. Summaries are generated asynchronously and can be scheduled for automatic generation.

## How It Works

1. A summary generation request is received (via API or schedule)
2. Messages from the specified time period are retrieved
3. Messages are formatted and sent to the configured LLM provider
4. The generated summary is stored in the `chat_summaries` table
5. Embeddings are automatically generated for the summary
6. If a webhook is configured, the summary is delivered

## Summary Generation API

### Generate for a Single Chat

```bash
curl -X POST http://localhost:8000/api/v1/chats/{chat_id}/summary/generate \
  -H "Content-Type: application/json" \
  -d '{
    "period_minutes": 1440,
    "use_cache": true
  }'
```

Response:

```json
{
  "task_id": "uuid-here",
  "status": "pending",
  "from_cache": false
}
```

### Generate for All Chats

```bash
curl -X POST http://localhost:8000/api/v1/chats/summary/generate
```

### Check Task Status

```bash
curl http://localhost:8000/api/v1/chats/{chat_id}/summary/{task_id}
```

### Retrieve Summaries

```bash
# List summaries with pagination
curl http://localhost:8000/api/v1/chats/{chat_id}/summary?page=1&limit=10

# Get latest summary
curl http://localhost:8000/api/v1/chats/{chat_id}/summary/latest

# Get specific summary
curl http://localhost:8000/api/v1/chats/{chat_id}/summary/{summary_id}
```

## Caching

Summary results are cached based on a hash of the generation parameters. Cache TTL depends on the age of the requested period:

| Period Age | Cache TTL |
|------------|-----------|
| Less than 24 hours | 2 hours |
| 24-72 hours | 24 hours |
| More than 72 hours | No expiration |

Use `use_cache: false` to bypass the cache and force regeneration.

## Scheduling

Each chat can have an independent summary schedule. Schedules support both simple time format and cron expressions.

### Set Schedule

```bash
curl -X PUT http://localhost:8000/api/v1/settings/chats/{chat_id}/summary/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "09:00", "timezone": "Europe/Moscow"}'
```

### Cron Format

```bash
curl -X PUT http://localhost:8000/api/v1/settings/chats/{chat_id}/summary/schedule \
  -H "Content-Type: application/json" \
  -d '{"schedule": "cron:0 9 * * 1-5", "timezone": "Europe/Moscow"}'
```

The schedule service runs in the background and triggers summary generation at the specified times.

## Custom Prompts

Each chat can have a custom prompt for summary generation:

```bash
curl -X PUT http://localhost:8000/api/v1/settings/chats/{chat_id}/summary/prompt \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize the key technical decisions made in this chat..."}'
```

## Summary Settings

| Setting | Endpoint | Description |
|---------|----------|-------------|
| Enable/Disable | `POST /api/v1/settings/chats/{chat_id}/summary/enable` | Toggle summary generation |
| Period | `PUT /api/v1/settings/chats/{chat_id}/summary/period` | Set summary period in minutes |
| Schedule | `PUT/GET/DELETE /api/v1/settings/chats/{chat_id}/summary/schedule` | Manage schedule |
| Custom Prompt | `PUT/GET/DELETE /api/v1/settings/chats/{chat_id}/summary/prompt` | Manage custom prompt |

## Summary Statistics

```bash
curl http://localhost:8000/api/v1/chats/summary/stats
```

Returns summary counts, generation times, and cache hit rates.

## Auto-Cleanup

Old summary tasks are automatically cleaned up based on configurable retention settings:

| Setting | Default | Description |
|---------|---------|-------------|
| `pending_timeout_minutes` | 60 | Remove pending tasks after this time |
| `processing_timeout_minutes` | 5 | Mark processing tasks as failed after this time |
| `failed_retention_minutes` | 120 | Remove failed tasks after this time |
| `completed_retention_minutes` | None | Completed tasks are kept indefinitely |

## Webhook Delivery

When a summary is generated and a webhook is configured for the chat, the summary is automatically delivered. See [Webhook](webhook.md) for configuration details.
