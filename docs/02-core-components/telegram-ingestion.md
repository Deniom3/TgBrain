# Telegram Ingestion
Languages: [English](telegram-ingestion.md) | [Русский](telegram-ingestion_ru.md)

## Overview

The Telegram Ingester is the core message collection component. It connects to Telegram via Telethon, polls monitored chats for new messages, filters unwanted content, generates embeddings, and stores messages in the database.

## Architecture

```
TelegramIngester
  |-- SessionManager          -- Telegram session lifecycle
  |-- TelegramConnection      -- Connection management
  |-- MessageProcessing       -- Message processing pipeline
  |-- Filters                 -- Message filtering (bots, ads, actions)
  |-- Saver                   -- Database persistence
  |-- PendingCleanupService   -- Stale pending message cleanup
  |-- ChatSyncService         -- Chat metadata synchronization
```

## Message Processing Pipeline

1. **Poll** -- Fetch new messages from monitored chats via Telethon
2. **Filter** -- Remove bot messages, ads, system actions, and other unwanted content
3. **Embed** -- Generate vector embeddings for the message text
4. **Store** -- Save message and embedding to the database
5. **Acknowledge** -- Update the last processed message offset

## Chat Monitoring

Chats are monitored based on settings in the `chat_settings` table. Only chats with `is_monitored = true` are processed.

### Managing Monitored Chats

Use the Settings API to manage which chats are monitored:

```bash
# List all chats
curl http://localhost:8000/api/v1/settings/chats

# Enable monitoring for a chat
curl -X POST http://localhost:8000/api/v1/settings/chats/{chat_id}/enable

# Disable monitoring for a chat
curl -X POST http://localhost:8000/api/v1/settings/chats/{chat_id}/disable

# Sync chats with Telegram
curl -X POST http://localhost:8000/api/v1/settings/chats/sync
```

### Startup Configuration

On startup, chats can be enabled or disabled via environment variables:

```env
TG_CHAT_ENABLE=-1001234567890,-1009876543210
TG_CHAT_DISABLE=-1001111111111
```

These settings are applied once on startup. Subsequent changes should be made via the API.

## Message Filtering

The ingestion pipeline applies several filters:

| Filter | Description |
|--------|-------------|
| Bot messages | Messages from bot accounts |
| Ad messages | Promoted/channel posts in groups |
| System actions | Join/leave/pin messages |
| Service messages | Chat photo changes, title changes |
| Empty messages | Messages with no text content |

Filters can be configured per-chat through the chat settings.

## Message Storage

Messages are stored in the `messages` table with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | bigint | Telegram message ID |
| `chat_id` | bigint | Chat ID |
| `sender_id` | bigint | Sender user ID |
| `sender_name` | text | Display name of sender |
| `text` | text | Message text content |
| `date` | timestamptz | Message timestamp |
| `embedding` | vector | Vector embedding |
| `is_bot` | boolean | Whether sender is a bot |
| `is_action` | boolean | Whether message is a system action |

## Pending Messages

Messages that pass initial validation but cannot be immediately embedded or stored are placed in the `pending_messages` table. A background cleanup service removes stale pending messages based on configurable TTL settings.

See [Pending Cleanup](pending-cleanup.md) for details.

## Ingestion Lifecycle

The Ingester runs as a background asyncio task during the application lifespan:

1. **Startup** -- Load session, connect to Telegram, start polling loop
2. **Polling** -- Periodically fetch new messages from all monitored chats
3. **Processing** -- Filter, embed, and store each message
4. **Error handling** -- Retry on transient failures, log permanent failures
5. **Shutdown** -- Gracefully close Telegram connection, save state

## Rate Limiting

The Ingester uses an adaptive rate limiter to avoid Telegram API FloodWait errors. See [Rate Limiter](rate-limiter.md) for details.

## External Message Sources

Messages can also be ingested from external sources (bots, webhooks) via the `POST /api/v1/messages/ingest` endpoint. See [External Ingestion](external-ingestion.md) for details.

## Batch Import

Historical messages can be imported from Telegram Desktop export files. See [Batch Import](batch-import.md) for details.
