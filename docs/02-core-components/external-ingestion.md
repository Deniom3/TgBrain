# External Ingestion
Languages: [English](external-ingestion.md) | [Русский](external-ingestion_ru.md)

## Overview

The external ingestion API allows messages to be submitted from external sources such as custom bots, webhooks, or other applications. Messages are processed through the same pipeline as Telegram-ingested messages.

## Ingestion Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/messages/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": -1001234567890,
    "text": "Message content",
    "date": "2026-04-01T10:00:00Z",
    "sender_id": 123456,
    "sender_name": "Bot Name",
    "message_link": "https://t.me/c/1234567890/100",
    "is_bot": true,
    "is_action": false
  }'
```

## Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chat_id` | integer | Yes | Telegram chat ID |
| `text` | string | Yes | Message text content |
| `date` | string | Yes | Message timestamp (ISO 8601) |
| `sender_id` | integer | Yes | Sender user or bot ID |
| `sender_name` | string | Yes | Display name of sender |
| `message_link` | string | No | Link to the message |
| `is_bot` | boolean | No | Whether sender is a bot |
| `is_action` | boolean | No | Whether message is a system action |

## Response

```json
{
  "success": true,
  "status": "processed",
  "message_id": 100,
  "chat_id": -1001234567890,
  "filtered": false,
  "pending": false,
  "duplicate": false,
  "updated": false
}
```

Status values: `processed`, `pending`, `filtered`, `duplicate`, `updated`.

## Error Codes

### Ingestion Errors (EXT-001..EXT-007)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| EXT-001 | 400 | Invalid request data |
| EXT-002 | 400 | Chat not monitored |
| EXT-003 | 200 | Embedding error (message stored as pending) |
| EXT-004 | 200/500 | Database error |
| EXT-005 | 200 | Filtered message |
| EXT-006 | 200 | Duplicate message |
| EXT-007 | 200 | Embedding service unavailable (message stored as pending) |

### Batch Import Errors (EXT-008..EXT-015)

| Code | HTTP Status | Description |
|------|-------------|-------------|
| EXT-008 | 413 | File too large |
| EXT-009 | 400 | Invalid chat type |
| EXT-010 | 415 | Invalid content type |
| EXT-013 | 404 | Task not found |
| EXT-014 | 403 | User has no access to chat |
| EXT-015 | 400 | Too many messages |

## Processing Flow

1. Validate request data
2. Check if chat is monitored (EXT-002 if not)
3. Check for duplicate messages (skip embedding for exact duplicates)
4. Apply message filters
5. Generate embedding
6. Store message in database
7. Return response

## Pending Messages

If embedding fails but the message is valid, it is stored in the `pending_messages` table. The pending cleanup service will attempt to process it later.

## Chat Monitoring Requirement

The target chat must be registered and monitored in the system. Use the Chat Management API to enable monitoring before ingesting messages.
