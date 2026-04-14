# System Overview
Languages: [English](system-overview.md) | [Русский](system-overview_ru.md)

## High-Level Architecture

TgBrain follows a layered architecture with clear separation of concerns:

```
+-------------------+
|    API Layer      |  FastAPI routers, request/response models
+-------------------+
|  Application      |  Business services, orchestration
+-------------------+
|    Domain         |  Value objects, domain exceptions
+-------------------+
|  Infrastructure   |  Database, external services, persistence
+-------------------+
```

## Component Diagram

```
                    +------------------+
                    |   FastAPI App    |
                    +--------+---------+
                             |
            +----------------+----------------+
            |                |                |
     +------+------+  +-----+------+  +------+------+
     |  API Layer  |  | Settings   |  |  Callbacks  |
     |  (routers)  |  | API        |  |  (QR auth)  |
     +------+------+  +-----+------+  +-------------+
            |                |
            +----------------+
                             |
                    +--------+---------+
                    |  Application     |
                    |  Services        |
                    +--------+---------+
                             |
        +--------------------+--------------------+
        |                    |                    |
 +------+------+     +------+------+      +------+------+
 |  Ingestion  |     |    RAG      |      |  Reindex    |
 |  Service    |     |  Service    |      |  Service    |
 +-------------+     +-------------+      +-------------+
        |                    |                    |
        +--------------------+--------------------+
                             |
                    +--------+---------+
                    |  Infrastructure  |
                    |  (PostgreSQL)    |
                    +------------------+
```

## Background Services

The application runs several long-running background services as asyncio tasks:

| Service | Description |
|---------|-------------|
| TelegramIngester | Polls Telegram for new messages |
| ReindexService | Regenerates embeddings when model changes |
| SummaryTaskService | Manages async summary generation |
| SummaryEmbeddingsService | Generates embeddings for summaries |
| SummaryCleanupService | Cleans up old summary tasks |
| ScheduleService | Triggers scheduled summary generation |
| PendingCleanupService | Cleans up stale pending messages |
| WebhookService | Delivers summaries to webhooks |

## Startup Sequence

1. Load settings from database (override .env)
2. Initialize database connection pool
3. Create embedding and LLM clients
4. Initialize repositories
5. Start background services
6. Check Telegram session and start ingestion if authenticated

## Shutdown Sequence

1. Stop ScheduleService
2. Close WebhookService
3. Stop TelegramIngester
4. Close database connection pool

## Data Flow

### Message Ingestion

```
Telegram --> Ingester --> Filter --> Embedder --> Database
```

### RAG Search

```
User Query --> Embedder --> Vector Search --> Context Expand --> LLM --> Answer
```

### Summary Generation

```
API/Schedule --> Message Fetch --> LLM --> Summary Store --> Embedder --> Webhook
```

## SummaryEmbeddingsService

The `SummaryEmbeddingsService` (`src/rag/summary_embeddings_service.py`) handles vector embedding generation for chat summaries. It works analogously to the `MessageIngester` but operates on `chat_summaries` instead of `messages`.

### Responsibilities

- **Generate embeddings** -- Creates vector embeddings from summary `result_text` using the active `EmbeddingsClient`
- **Store embeddings** -- Saves embeddings to `chat_summaries.embedding` column along with `embedding_model` name
- **Batch processing** -- Supports batch embedding generation for multiple summaries
- **Reindexing support** -- Can regenerate embeddings with a new model when the embedding model changes

### Key Methods

| Method | Description |
|--------|-------------|
| `generate_and_save_embedding(summary_id, summary_text)` | Generate and store embedding for a single summary |
| `generate_batch_embeddings(summary_ids, summary_texts)` | Generate embeddings for a batch of summaries |
| `reindex_summary_embedding(summary_id, new_model)` | Regenerate embedding with a different model |

### Integration

The service is called after summary generation completes and during reindex operations. It uses the same `EmbeddingsClient` as message ingestion, ensuring consistent vector dimensions across messages and summaries.
