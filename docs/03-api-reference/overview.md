# API Overview
Languages: [English](overview.md) | [Русский](overview_ru.md)

## Base URL

```
http://localhost:8000
```

## Interactive Documentation

Swagger UI is available at http://localhost:8000/docs for interactive API exploration.

## Authentication

Most settings and management endpoints require authentication. QR Auth endpoints are used to establish a Telegram session, which serves as the authentication mechanism.

## Request Format

All request bodies use JSON format with `Content-Type: application/json` header.

## Response Format

All responses use JSON format. Error responses include an error code and message.

### Success Response

```json
{
  "status": "ok",
  "data": { ... }
}
```

### Error Response

```json
{
  "status": "error",
  "code": "EXT-001",
  "message": "Invalid request data: chat_id is required"
}
```

## API Groups

| Group | Prefix | Description |
|-------|--------|-------------|
| Health | `/health` | System health checks |
| RAG Search | `/api/v1/ask` | Semantic search |
| Chat Summary | `/api/v1/chats/{chat_id}/summary` | Summary generation and retrieval |
| Message Ingestion | `/api/v1/messages` | External ingestion and batch import |
| Settings | `/api/v1/settings` | All configuration endpoints |
| System | `/api/v1/system` | Monitoring and statistics |

## Pagination

List endpoints support pagination via query parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | 1 | Page number |
| `limit` | 20 | Items per page |

## Rate Limiting

API endpoints may be rate-limited. Check response headers for rate limit information.
