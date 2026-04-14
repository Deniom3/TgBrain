# Pending Cleanup
Languages: [English](pending-cleanup.md) | [Русский](pending-cleanup_ru.md)

## Overview

The pending cleanup service manages messages that could not be immediately processed during ingestion. Messages are placed in the `pending_messages` table when embedding fails or other transient errors occur.

## How It Works

1. Messages that fail embedding during ingestion are stored in `pending_messages`
2. The PendingCleanupService periodically scans for stale pending messages
3. Messages exceeding the TTL are removed
4. Settings are stored in `app_settings` table with `pending.*` keys

## Configuration

| Setting Key | Default | Description |
|-------------|---------|-------------|
| `pending.ttl_minutes` | 240 | Time-to-live for pending messages (4 hours) |
| `pending.cleanup_interval_minutes` | 60 | How often to run cleanup (1 hour) |

Settings can be modified via the App Settings API:

```bash
# Update TTL
curl -X PUT http://localhost:8000/api/v1/settings/app/pending.ttl_minutes \
  -H "Content-Type: application/json" \
  -d '{"value": 480}'

# Update interval
curl -X PUT http://localhost:8000/api/v1/settings/app/pending.cleanup_interval_minutes \
  -H "Content-Type: application/json" \
  -d '{"value": 30}'
```

## Pending Message Sources

Pending messages come from two sources:

1. **Telegram ingestion** -- Messages from monitored chats that fail embedding
2. **External ingestion** -- Messages from the API that fail embedding (stored with pending status)

## Cleanup Behavior

The cleanup service:
- Runs on the configured interval
- Removes messages older than the TTL
- Logs the number of cleaned messages
- Does not attempt re-processing (messages are removed if they exceed TTL)

## Monitoring

Pending message counts can be observed through the system stats endpoint. A growing count of pending messages may indicate embedding service issues.
