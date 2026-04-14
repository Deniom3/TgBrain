# Embeddings
Languages: [English](embeddings.md) | [Русский](embeddings_ru.md)

## Overview

The embedding system converts text into vector representations for semantic search. Multiple embedding providers are supported through a unified abstraction layer.

## Supported Providers

| Provider | Description |
|----------|-------------|
| Ollama | Local embedding models via Ollama server |
| Gemini | Google's embedding models via API |
| OpenRouter | Embedding models through OpenRouter |
| LM Studio | Local models via LM Studio server |

## Vector Dimension

The vector dimension is auto-detected from the embedding model on first use and stored in the database. This ensures consistency across restarts and enables migration tracking.

## Managing Embedding Providers via API

### List All Providers

```bash
curl http://localhost:8000/api/v1/settings/embedding
```

### Get Specific Provider

```bash
curl http://localhost:8000/api/v1/settings/embedding/ollama
```

### Update Provider Settings

```bash
curl -X PUT http://localhost:8000/api/v1/settings/embedding/ollama \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://localhost:11434",
    "model": "nomic-embed-text"
  }'
```

### Activate Provider

```bash
curl -X POST http://localhost:8000/api/v1/settings/embedding/ollama/activate
```

### Check Provider Health

```bash
curl -X POST http://localhost:8000/api/v1/settings/embedding/ollama/check
```

### Refresh Dimension (Ollama)

```bash
curl -X POST http://localhost:8000/api/v1/settings/embedding/ollama/refresh-dimension
```

## Embedding During Ingestion

Every message ingested from Telegram is automatically embedded before storage. If embedding fails, the message is placed in the `pending_messages` table for later processing.

## Embedding During Search

When a user submits a RAG query, the query text is embedded and used to find similar messages via the pgvector HNSW index.

## Reindexing

When the embedding model or provider changes, all existing message embeddings must be regenerated. Use the Reindex API to trigger this process. See [Reindex](reindex.md) for details.
