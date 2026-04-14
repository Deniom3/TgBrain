# TgBrain

Telegram message summarization and knowledge base system. Monitors Telegram chats, ingests messages, generates AI-powered summaries, and provides semantic search (RAG) across all stored conversations.

Language: [English](README.md) | [Русский](docs/README_ru.md)

## Features

| Component | Description |
|-----------|-------------|
| Telegram Ingestion | Real-time message collection with adaptive rate limiting and FloodWait protection |
| QR Authentication | Telegram login via QR code with web interface |
| Multi-provider Embeddings | Ollama, Gemini, OpenRouter, LM Studio |
| RAG Search | Semantic search with source citations |
| Async Summary Generation | AI-powered chat digests with caching and floating TTL |
| Chat Management | Dynamic monitoring control with bulk operations and Telegram sync |
| Reindex Service | Automatic reindexing when embedding model changes |
| External Messages API | Accept messages from bots and webhooks |
| Batch Import | Import messages from Telegram Desktop export files |
| Summary Webhook | Deliver summaries to external endpoints |
| Settings API | Hot-reload configuration without restart |
| Reindex Speed Control | Adjustable reindex performance parameters |

## Quick Start

### Requirements

- Python 3.12+
- PostgreSQL 14+ with pgvector extension
- Telegram API credentials (api_id, api_hash from https://my.telegram.org)
- LLM provider API key (Gemini, OpenRouter) or local Ollama

### Run with Docker

1. Copy and configure environment:
   ```bash
   cp .env.example .env
   ```

2. Start services:
   ```bash
   docker-compose up -d
   ```

3. Authenticate via QR code at `http://localhost:8000/settings`

4. Access the API:
   - Swagger UI: http://localhost:8000/docs
   - Health check: http://localhost:8000/health

### Run Locally

1. Activate virtual environment:
   ```bash
   # Linux/macOS
   source venv/bin/activate
   # Windows
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure `.env` and start:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Component health check |
| `/api/v1/ask` | POST | Semantic search with sources |
| `/api/v1/chats/{chat_id}/summary/generate` | POST | Generate summary for a chat |
| `/api/v1/chats/{chat_id}/summary` | GET | List summaries |
| `/api/v1/settings/overview` | GET | Settings overview |
| `/docs` | GET | Interactive Swagger UI |

Full API reference: [docs/03-api-reference/overview.md](docs/03-api-reference/overview.md)

## Project Structure

```
TgBrain/
src/
  api/              HTTP API endpoints (FastAPI routers)
  settings_api/     Settings management API
  application/      Application use cases and services
  domain/           Domain models and value objects
  infrastructure/   Database, external services, adapters
  ingestion/        Telegram message ingestion pipeline
  embeddings/       Embedding provider implementations
  providers/        LLM provider implementations
  rag/              RAG search and summarization
  reindex/          Vector reindexing service
  rate_limiter/     Adaptive Telegram rate limiting
  schedule/         Cron-like scheduler
  settings/         Settings repositories
  webhook/          Webhook delivery system
  batch_import/     Batch import from Telegram export
  auth/             QR authentication
  config/           Configuration management
  importers/        External message importers
  models/           Data models and SQL queries
  protocols/        Interface definitions
  services/         Shared services
  utils/            Utility functions
  stubs/            Type stubs
  app.py            Application factory
  database.py       PostgreSQL connection pool
  llm_client.py     LLM client abstraction
  settings_initializer.py  Settings initialization
tests/              Test suite (pytest)
docs/               Documentation
scripts/            Utility and maintenance scripts
main.py             FastAPI application entry point
```

## Development

Run tests:
```bash
pytest tests/ -v
```

Lint and type check:
```bash
ruff check .
mypy src/
import-lint src/
```

Run with Docker (dev):
```bash
docker-compose up -d
docker-compose logs -f app
```

## Architecture

The application follows a layered architecture with Domain-Driven Design principles. The dependency flow is unidirectional: domain -> application -> infrastructure -> API. Import order is enforced by `import-lint`.

## License

MIT
