# TgBrain Documentation

Version: 1.0.1
Date: April 2026

Languages: [English](README.md) | [Русский](README_ru.md)

## Overview

TgBrain is a Telegram message summarization and knowledge base system. It monitors Telegram chats, ingests messages, generates AI-powered summaries, and provides semantic search across all stored conversations.

## Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and configure your settings
3. Run `docker compose up -d` to start PostgreSQL and the application
4. Authenticate with Telegram via QR code
5. Access the API at `http://localhost:8000/docs`

## Documentation Structure

### Getting Started

| Document | Description |
|----------|-------------|
| [Installation](01-getting-started/installation.md) | System requirements and installation methods |
| [Configuration](01-getting-started/configuration.md) | Environment variables and settings reference |
| [Docker Setup](01-getting-started/docker-setup.md) | Docker deployment and compose configuration |
| [QR Authentication](01-getting-started/qr-auth.md) | Telegram authentication via QR code |

### Core Components

| Document | Description |
|----------|-------------|
| [Telegram Ingestion](02-core-components/telegram-ingestion.md) | Message ingestion from Telegram |
| [Summarization](02-core-components/summarization.md) | AI-powered chat summarization |
| [RAG Search](02-core-components/rag-search.md) | Semantic search with RAG |
| [Rate Limiter](02-core-components/rate-limiter.md) | Adaptive Telegram API rate limiting |
| [LLM Providers](02-core-components/llm-providers.md) | Multi-provider LLM abstraction |
| [Embeddings](02-core-components/embeddings.md) | Vector embedding generation |
| [Batch Import](02-core-components/batch-import.md) | Bulk message import from Telegram export |
| [External Ingestion](02-core-components/external-ingestion.md) | Message ingestion from external sources |
| [Webhook](02-core-components/webhook.md) | Webhook delivery for summaries |
| [Reindex](02-core-components/reindex.md) | Vector reindexing service |
| [Schedule](02-core-components/schedule.md) | Scheduled summary generation |
| [Pending Cleanup](02-core-components/pending-cleanup.md) | Pending message cleanup |

### API Reference

| Document | Description |
|----------|-------------|
| [Overview](03-api-reference/overview.md) | API introduction and conventions |
| [Settings API](03-api-reference/settings-api.md) | All settings endpoints |
| [Chat Management API](03-api-reference/chat-management-api.md) | Chat monitoring endpoints |
| [Summary API](03-api-reference/summary-api.md) | Summary generation and retrieval |
| [Message API](03-api-reference/message-api.md) | Message ingestion and import |
| [Reindex API](03-api-reference/reindex-api.md) | Reindex management |
| [System API](03-api-reference/system-api.md) | System monitoring and stats |
| [QR Auth API](03-api-reference/qr-auth-api.md) | QR authentication endpoints |
| [Error Codes](03-api-reference/error-codes.md) | API error codes reference |

### Architecture

| Document | Description |
|----------|-------------|
| [System Overview](04-architecture/system-overview.md) | High-level architecture |
| [C4 Model](04-architecture/c4-model.md) | C4 architecture diagrams |
| [Database Schema](04-architecture/database-schema.md) | PostgreSQL schema reference |
| [Settings Architecture](04-architecture/settings-architecture.md) | Settings storage and loading |

### Integrations

| Document | Description |
|----------|-------------|
| [LLM Providers](05-integrations/llm-providers.md) | Gemini, OpenRouter, Ollama, LM Studio |
| [Embedding Providers](05-integrations/embedding-providers.md) | Ollama, Gemini, OpenRouter, LM Studio |

### Frontend

| Document | Description |
|----------|-------------|
| [Integration Guide](06-frontend/integration-guide.md) | Frontend integration patterns |

### Testing

| Document | Description |
|----------|-------------|
| [Testing Guide](07-testing/testing-guide.md) | Running and writing tests |

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12+ |
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| Database | PostgreSQL 16 + pgvector |
| Telegram Client | Telethon |
| Vector Search | HNSW (pgvector) |
| Templates | Jinja2 |
| Encryption | cryptography |
| Testing | pytest, pytest-asyncio |
| Containerization | Docker, Docker Compose |

## Architecture

The application follows a layered architecture with Domain-Driven Design principles:

```
src/
  api/              -- HTTP API layer (FastAPI routers)
  settings_api/     -- Settings HTTP API layer
  application/      -- Application services
  domain/           -- Domain models and value objects
  infrastructure/   -- Database, external services
  ingestion/        -- Telegram message ingestion
  embeddings/       -- Embedding provider implementations
  providers/        -- LLM provider implementations
  rag/              -- RAG search and summarization
  reindex/          -- Vector reindexing service
  rate_limiter/     -- Adaptive rate limiting
  schedule/         -- Cron-like scheduler
  settings/         -- Settings repositories
  webhook/          -- Webhook delivery system
  batch_import/     -- Batch import processing
  auth/             -- QR authentication
  config/           -- Configuration management
```

## License

MIT License
