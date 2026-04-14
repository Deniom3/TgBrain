# Database Schema

Languages: [English](database-schema.md) | [Русский](database-schema_ru.md)

## Overview

TgBrain uses PostgreSQL with the pgvector extension for storing messages, settings, and vector embeddings.

## Tables

### telegram_auth

Stores encrypted Telegram session data. Single-row table (id = 1).

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key (always 1) |
| `api_id` | integer | Telegram API ID |
| `api_hash` | text | Telegram API Hash |
| `phone_number` | text | Phone number (optional) |
| `session_name` | text | Session name (default: 'qr_auth_session') |
| `session_data` | bytea | Encrypted session data |
| `updated_at` | timestamptz | Last update timestamp |

### chat_settings

Configuration for monitored Telegram chats.

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial | Primary key |
| `chat_id` | bigint | Telegram chat ID (UNIQUE) |
| `title` | text | Chat title |
| `type` | text | Chat type (default: 'private') |
| `last_message_id` | bigint | Last processed message ID |
| `is_monitored` | boolean | Whether chat is monitored |
| `summary_enabled` | boolean | Whether summary generation is enabled |
| `summary_period_minutes` | integer | Summary period in minutes (default: 1440) |
| `summary_schedule` | varchar(50) | Schedule expression (HH:MM or cron, stored as UTC) |
| `custom_prompt` | text | Custom summary prompt |
| `webhook_config` | jsonb | Webhook configuration |
| `webhook_enabled` | boolean | Whether webhook is enabled |
| `next_schedule_run` | timestamptz | Next scheduled run time |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

### messages

Stored Telegram messages with vector embeddings.

| Column | Type | Description |
|--------|------|-------------|
| `id` | bigint | Primary key (Telegram message ID) |
| `chat_id` | bigint | Chat ID (FK to chat_settings) |
| `sender_id` | bigint | Sender user ID |
| `sender_name` | text | Display name |
| `message_text` | text | Message content |
| `message_date` | timestamptz | Message timestamp |
| `message_link` | text | Link to the message |
| `embedding` | vector(1024) | Vector embedding |
| `embedding_model` | text | Name of the embedding model used |
| `is_processed` | boolean | Whether message has been processed |
| `created_at` | timestamptz | Storage timestamp |

### pending_messages

Messages awaiting embedding or processing.

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial | Primary key |
| `message_data` | jsonb | Full message data as JSON |
| `retry_count` | integer | Number of retry attempts |
| `last_error` | text | Last error message |
| `created_at` | timestamptz | Creation timestamp |

### chat_summaries

Generated chat summaries and task records.

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial | Primary key |
| `chat_id` | bigint | Chat ID (FK to chat_settings) |
| `status` | text | Task status: pending, processing, completed, failed |
| `params_hash` | text | Hash of generation parameters (for caching) |
| `result_text` | text | Summary text or error message |
| `period_start` | timestamptz | Summary period start |
| `period_end` | timestamptz | Summary period end |
| `messages_count` | integer | Number of messages summarized |
| `embedding` | vector(1024) | Summary vector embedding |
| `embedding_model` | text | Name of the embedding model used |
| `generated_by` | text | Generator type (default: 'llm') |
| `metadata` | jsonb | Generation metadata (llm_model, tokens_used, etc.) |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

### llm_providers

LLM provider configurations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial | Primary key |
| `name` | text | Provider name (UNIQUE) |
| `is_active` | boolean | Whether this is the active provider |
| `api_key` | text | API key |
| `base_url` | text | Base URL |
| `model` | text | Model name |
| `is_enabled` | boolean | Whether provider is enabled |
| `priority` | integer | Fallback priority |
| `description` | text | Provider description |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

### embedding_providers

Embedding provider configurations.

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial | Primary key |
| `name` | text | Provider name (UNIQUE) |
| `is_active` | boolean | Whether this is the active provider |
| `api_key` | text | API key |
| `base_url` | text | Base URL |
| `model` | text | Model name |
| `is_enabled` | boolean | Whether provider is enabled |
| `priority` | integer | Fallback priority |
| `description` | text | Provider description |
| `embedding_dim` | integer | Vector dimension (default: 768) |
| `max_retries` | integer | Max retry attempts (default: 3) |
| `timeout` | integer | Request timeout in seconds (default: 30) |
| `normalize` | boolean | Normalize output vectors (default: false) |
| `created_at` | timestamptz | Creation timestamp |
| `updated_at` | timestamptz | Last update timestamp |

### app_settings

Application-level key-value settings.

| Column | Type | Description |
|--------|------|-------------|
| `id` | serial | Primary key |
| `key` | text | Setting key (UNIQUE) |
| `value` | text | Setting value |
| `value_type` | text | Value type: string, int, bool, float |
| `description` | text | Setting description |
| `is_sensitive` | boolean | Whether value is sensitive |
| `updated_at` | timestamptz | Last update timestamp |

### reindex_settings

Reindex service configuration. Single-row table (id = 1).

| Column | Type | Description |
|--------|------|-------------|
| `id` | integer | Primary key (always 1) |
| `batch_size` | integer | Messages per batch (default: 50) |
| `delay_between_batches` | float | Delay between batches in seconds |
| `auto_reindex_on_model_change` | boolean | Auto-reindex when model changes |
| `auto_reindex_new_messages` | boolean | Auto-reindex new messages |
| `reindex_new_messages_delay` | integer | Delay before reindexing new messages |
| `max_concurrent_tasks` | integer | Max concurrent reindex tasks |
| `max_retries` | integer | Max retry attempts |
| `speed_mode` | text | Speed mode: slow, medium, fast, aggressive |
| `current_batch_size` | integer | Current adaptive batch size |
| `last_reindex_model` | text | Last reindexed model name |
| `low_priority_delay` | float | Delay for low priority tasks |
| `normal_priority_delay` | float | Delay for normal priority tasks |
| `high_priority_delay` | float | Delay for high priority tasks |
| `updated_at` | timestamptz | Last update timestamp |

### reindex_tasks

Reindex task history.

| Column | Type | Description |
|--------|------|-------------|
| `id` | text | Primary key (task UUID) |
| `status` | text | Task status |
| `priority` | integer | Priority level (0=low, 1=normal, 2=high) |
| `target_model` | text | Target embedding model |
| `total_messages` | integer | Total messages to process |
| `processed_count` | integer | Messages processed |
| `failed_count` | integer | Messages failed |
| `batch_size` | integer | Batch size used |
| `delay_between_batches` | float | Delay between batches |
| `created_at` | timestamptz | Creation timestamp |
| `started_at` | timestamptz | Start timestamp |
| `completed_at` | timestamptz | Completion timestamp |
| `error` | text | Error message (if failed) |
| `progress_percent` | float | Progress percentage |

## Indexes

### HNSW Vector Index

Messages are indexed using pgvector's HNSW index for fast approximate nearest neighbor search:

```sql
CREATE INDEX idx_embedding ON messages USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
```

Chat summaries also have an HNSW index for semantic search:

```sql
CREATE INDEX idx_chat_summary_embedding ON chat_summaries USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
```

### Standard Indexes

- `messages(chat_id)` -- Chat filtering
- `messages(message_date DESC)` -- Date-range queries
- `chat_summaries(chat_id)` -- Chat filtering
- `chat_summaries(created_at DESC)` -- Recent summary lookup
- `chat_summaries(chat_id, period_start, period_end)` -- Period-based lookup
- `chat_summaries(params_hash)` -- Cache lookup
- `chat_summaries(status)` -- Task status filtering
- `chat_summaries(status, created_at)` -- Task cleanup queries
