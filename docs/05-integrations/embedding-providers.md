# Embedding Providers
Languages: [English](embedding-providers.md) | [Русский](embedding-providers_ru.md)

## Overview

TgBrain supports four embedding providers for converting text into vector representations.

## Ollama

Local embedding models via Ollama server.

**Configuration:**
- `OLLAMA_EMBEDDING_URL` -- Ollama server URL (default: http://localhost:11434)
- `OLLAMA_EMBEDDING_MODEL` -- Model name (default: nomic-embed-text)
- `OLLAMA_EMBEDDING_DIM` -- Vector dimension (auto-detected on first use)
- `OLLAMA_EMBEDDING_MAX_RETRIES` -- Max retry attempts (default: 3)
- `OLLAMA_EMBEDDING_TIMEOUT` -- Request timeout in seconds (default: 30)
- `OLLAMA_EMBEDDING_NORMALIZE` -- Normalize output vectors (default: true)

**Use case:** Default provider, local inference, no API costs.

**Docker note:** Use `http://host.docker.internal:11434` instead of `localhost` when running in Docker.

## Gemini

Google's embedding models via API.

**Configuration:**
- `GEMINI_EMBEDDING_URL` -- API base URL
- `GEMINI_EMBEDDING_MODEL` -- Model name (default: text-embedding-004)
- `GEMINI_EMBEDDING_DIM` -- Vector dimension (default: 768)

**Use case:** High-quality embeddings, cloud-based.

## OpenRouter

Embedding models through OpenRouter.

**Configuration:**
- `OPENROUTER_EMBEDDING_URL` -- API base URL
- `OPENROUTER_EMBEDDING_MODEL` -- Model name (default: openai/text-embedding-3-small)
- `OPENROUTER_EMBEDDING_DIM` -- Vector dimension (default: 1536)
- `OPENROUTER_EMBEDDING_BATCH_SIZE` -- Batch size (default: 20)

**Use case:** Access to OpenAI embedding models via OpenRouter.

## LM Studio

Local models via LM Studio server.

**Configuration:**
- `LM_STUDIO_EMBEDDING_URL` -- Server URL
- `LM_STUDIO_EMBEDDING_MODEL` -- Model name
- `LM_STUDIO_EMBEDDING_DIM` -- Vector dimension
- `LM_STUDIO_EMBEDDING_API_KEY` -- API key (if required)

**Use case:** Local inference with OpenAI-compatible API.

## Vector Dimension

The vector dimension is critical for pgvector indexing. It is:

1. Auto-detected on first embedding generation
2. Stored in the `embedding_providers` table
3. Used to validate all subsequent embeddings

If the dimension changes (model change), a full reindex is required. See [Reindex](../02-core-components/reindex.md).
