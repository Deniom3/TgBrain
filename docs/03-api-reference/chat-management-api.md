# Chat Management API
Languages: [English](chat-management-api.md) | [Русский](chat-management-api_ru.md)

## Overview

Chat management is handled through the Settings API endpoints under `/api/v1/settings/chats`. These endpoints control which Telegram chats are monitored for message ingestion.

## Endpoints

### List All Chats

```bash
GET /api/v1/settings/chats
```

Returns all registered chats settings.

### List Chats with Metadata

```bash
GET /api/v1/settings/chats/list
```

Returns chats with additional metadata such as title, member count, and last activity.

### List Monitored Chats

```bash
GET /api/v1/settings/chats/monitored
```

Returns only chats with monitoring enabled.

### Get Chat Settings

```bash
GET /api/v1/settings/chats/{chat_id}
```

Returns settings for a specific chat.

### Update Chat Settings

```bash
PUT /api/v1/settings/chats/{chat_id}
```

Update chat configuration.

### Delete Chat

```bash
DELETE /api/v1/settings/chats/{chat_id}
```

Remove a chat from the system.

### Enable Monitoring

```bash
POST /api/v1/settings/chats/{chat_id}/enable
```

Enable message ingestion for a chat.

### Disable Monitoring

```bash
POST /api/v1/settings/chats/{chat_id}/disable
```

Disable message ingestion for a chat.

### Toggle Monitoring

```bash
POST /api/v1/settings/chats/{chat_id}/toggle
```

Toggle monitoring state (enable if disabled, disable if enabled).

### Bulk Update

```bash
POST /api/v1/settings/chats/bulk-update
```

Update multiple chats in a single request.

```json
{
  "chats": [
    {"chat_id": -1001234567890, "enabled": true},
    {"chat_id": -1009876543210, "enabled": false}
  ]
}
```

### Sync with Telegram

```bash
POST /api/v1/settings/chats/sync
```

Synchronize the chat list with Telegram. Discovers new chats and updates metadata.

### Add User for Monitoring

```bash
POST /api/v1/settings/chats/user/add
```

Add a user's private chat to monitoring.

### Remove User from Monitoring

```bash
POST /api/v1/settings/chats/user/remove
```

Remove a user's private chat from monitoring.
