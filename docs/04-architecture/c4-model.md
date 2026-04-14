# C4 Model

Languages: [English](c4-model.md) | [Русский](c4-model_ru.md)

## Level 1: System Context

```
+------------------+     Messages      +------------------+
|    Telegram      | ----------------> |  Telegram Message  |
|    Platform      | <---------------  |                  |
+------------------+   API Requests    +------------------+
                                             |
                      +----------------------+----------------------+
                      |                                             |
              +-------+-------+                             +-------+-------+
              |   LLM Provider|                             |   PostgreSQL  |
              |   (Gemini,    |                             |   + pgvector  |
              |   OpenRouter) |                             |               |
              +---------------+                             +---------------+
```

## Level 2: Container

```
+----------------------------------------------------------+
|                    Docker Compose                         |
|                                                          |
|  +----------------+         +--------------------------+  |
|  |   PostgreSQL   | <-----> |   TgBrain App    |  |
|  |   + pgvector   |         |   (FastAPI + Uvicorn)    |  |
|  +----------------+         +--------------------------+  |
+----------------------------------------------------------+
```

## Level 3: Component

```
+--------------------------------------------------------------+
|                     TgBrain App               |
|                                                              |
|  +-----------+  +-----------+  +---------+  +-------------+  |
|  | API Layer |  | Ingestion |  |   RAG   |  |  Settings   |  |
|  | (FastAPI) |  | Service   |  | Service |  |    API      |  |
|  +-----------+  +-----------+  +---------+  +-------------+  |
|                                                              |
|  +-----------+  +-----------+  +---------+  +-------------+  |
|  |  Reindex  |  | Schedule  |  | Webhook |  | Rate Limiter|  |
|  |  Service  |  |  Service  |  | Service |  |             |  |
|  +-----------+  +-----------+  +---------+  +-------------+  |
|                                                              |
|  +--------------------------------------------------------+  |
|  |              Database Layer (asyncpg)                  |  |
|  +--------------------------------------------------------+  |
+--------------------------------------------------------------+
```

## Level 4: Code

The codebase follows a layered structure:

```
src/
  api/              -- HTTP API routers and models
  settings_api/     -- Settings-specific API routers
  application/      -- Application services
  domain/           -- Domain models and value objects
  infrastructure/   -- Database and external service adapters
  ingestion/        -- Telegram message ingestion
  embeddings/       -- Embedding provider implementations
  providers/        -- LLM provider implementations
  rag/              -- RAG search and summarization
  reindex/          -- Vector reindexing
  rate_limiter/     -- Adaptive rate limiting
  schedule/         -- Cron-like scheduling
  settings/         -- Settings repositories
  webhook/          -- Webhook delivery
  batch_import/     -- Batch import processing
  auth/             -- QR authentication
  config/           -- Configuration management
```

Import dependencies are enforced via import-linter to maintain architectural boundaries.
