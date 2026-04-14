# Batch Import
Languages: [English](batch-import.md) | [Русский](batch-import_ru.md)

## Overview

The batch import system allows importing historical messages from Telegram Desktop export files. This enables building a knowledge base from existing chat history.

## How It Works

1. **Upload** -- Submit a Telegram Desktop export JSON file
2. **Parse** -- The file is parsed using streaming JSON (ijson) for memory efficiency
3. **Process** -- Messages are filtered, embedded, and stored in batches
4. **Track** -- Progress is tracked and available via the API

## Importing Messages

### Start Import

```bash
curl -X POST http://localhost:8000/api/v1/messages/import \
  -F "file=@result.json" \
  -F "chat_id=-1001234567890"
```

Response:

```json
{
  "task_id": "uuid-here",
  "status": "pending",
  "chat_id": -1001234567890,
  "file_name": "result.json"
}
```

### Check Progress

```bash
curl http://localhost:8000/api/v1/messages/import/{task_id}/progress
```

Response:

```json
{
  "task_id": "uuid-here",
  "status": "processing",
  "total_messages": 50000,
  "processed_messages": 12500,
  "imported_messages": 11800,
  "skipped_messages": 700,
  "progress_percent": 25.0
}
```

### Cancel Import

```bash
curl -X DELETE http://localhost:8000/api/v1/messages/import/{task_id}/cancel
```

## Telegram Desktop Export Format

The system expects JSON files in the Telegram Desktop export format:

```json
{
  "name": "Chat Name",
  "type": "private_channel",
  "id": 1234567890,
  "messages": [
    {
      "id": 1,
      "type": "message",
      "date": "2026-01-01T10:00:00",
      "from": "User Name",
      "from_id": "user123",
      "text": "Message content",
      "text_entities": [...]
    }
  ]
}
```

## Processing

Import tasks run as background asyncio tasks. Large files are processed in batches to manage memory usage. The streaming JSON parser (ijson) allows processing files larger than available RAM.

## Duplicate Handling

Messages with the same `message_id` and `chat_id` are skipped during import. This allows re-running imports without creating duplicates.

## File Management

Uploaded files are stored temporarily during processing and cleaned up after the import completes or is cancelled.
