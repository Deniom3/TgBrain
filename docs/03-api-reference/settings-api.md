# Settings API
Languages: [English](settings-api.md) | [Русский](settings-api_ru.md)

All settings endpoints use the prefix `/api/v1/settings`.

## Settings Overview

### GET /api/v1/settings/overview

Returns a summary of all configured settings.

```bash
curl http://localhost:8000/api/v1/settings/overview
```

## Telegram Settings

### GET /api/v1/settings/telegram

Get Telegram authentication settings.

### PUT /api/v1/settings/telegram

Update Telegram authentication settings.

```bash
curl -X PUT http://localhost:8000/api/v1/settings/telegram \
  -H "Content-Type: application/json" \
  -d '{
    "api_id": 123456,
    "api_hash": "your-api-hash"
  }'
```

### GET /api/v1/settings/telegram/check

Check Telegram session health.

## LLM Provider Settings

### GET /api/v1/settings/llm

List all configured LLM providers.

### GET /api/v1/settings/llm/{provider_name}

Get a specific LLM provider configuration.

### PUT /api/v1/settings/llm/{provider_name}

Update LLM provider settings.

### POST /api/v1/settings/llm/{provider_name}/activate

Set a provider as the active LLM provider.

### POST /api/v1/settings/llm/{provider_name}/check

Check provider connectivity.

## Embedding Provider Settings

### GET /api/v1/settings/embedding

List all configured embedding providers.

### GET /api/v1/settings/embedding/{provider_name}

Get a specific embedding provider configuration.

### PUT /api/v1/settings/embedding/{provider_name}

Update embedding provider settings.

### PUT /api/v1/settings/embedding/{provider_name}/model

Update the embedding model for a provider.

### POST /api/v1/settings/embedding/{provider_name}/activate

Set a provider as the active embedding provider.

### POST /api/v1/settings/embedding/{provider_name}/check

Check provider connectivity.

### POST /api/v1/settings/embedding/{provider_name}/refresh-dimension

Refresh the embedding dimension (Ollama only).

## App Settings

### GET /api/v1/settings/app

List all application settings.

### GET /api/v1/settings/app/{setting_key}

Get a specific application setting.

### PUT /api/v1/settings/app/{setting_key}

Update an application setting.

```bash
curl -X PUT http://localhost:8000/api/v1/settings/app/pending.ttl_minutes \
  -H "Content-Type: application/json" \
  -d '{"value": 480}'
```

### PUT /api/v1/settings/app/timezone

Set the application timezone.

## Chat Settings

### GET /api/v1/settings/chats

List all chat settings.

### GET /api/v1/settings/chats/list

List chats with metadata.

### GET /api/v1/settings/chats/monitored

List only monitored chats.

### GET /api/v1/settings/chats/{chat_id}

Get a specific chat configuration.

### PUT /api/v1/settings/chats/{chat_id}

Update chat settings.

### DELETE /api/v1/settings/chats/{chat_id}

Remove a chat from settings.

### POST /api/v1/settings/chats/{chat_id}/toggle

Toggle monitoring for a chat.

### POST /api/v1/settings/chats/{chat_id}/enable

Enable monitoring for a chat.

### POST /api/v1/settings/chats/{chat_id}/disable

Disable monitoring for a chat.

### POST /api/v1/settings/chats/bulk-update

Update multiple chats at once.

### POST /api/v1/settings/chats/sync

Sync chat list with Telegram.

### POST /api/v1/settings/chats/user/add

Add a user for monitoring.

### POST /api/v1/settings/chats/user/remove

Remove a user from monitoring.

## Chat Summary Settings

### POST /api/v1/settings/chats/{chat_id}/summary/enable

Enable summary generation for a chat.

### POST /api/v1/settings/chats/{chat_id}/summary/disable

Disable summary generation for a chat.

### POST /api/v1/settings/chats/{chat_id}/summary/toggle

Toggle summary generation.

### PUT /api/v1/settings/chats/{chat_id}/summary/period

Set the summary period in minutes.

### PUT /api/v1/settings/chats/{chat_id}/summary/schedule

Set the summary schedule (HH:MM or cron format).

### GET /api/v1/settings/chats/{chat_id}/summary/schedule

Get the current summary schedule.

### DELETE /api/v1/settings/chats/{chat_id}/summary/schedule

Clear the summary schedule.

### PUT /api/v1/settings/chats/{chat_id}/summary/prompt

Set a custom summary prompt.

### GET /api/v1/settings/chats/{chat_id}/summary/prompt

Get the custom summary prompt.

### DELETE /api/v1/settings/chats/{chat_id}/summary/prompt

Clear the custom summary prompt.

## Chat Webhook Settings

### PUT /api/v1/settings/chats/{chat_id}/webhook/config

Set webhook configuration.

### GET /api/v1/settings/chats/{chat_id}/webhook/config

Get webhook configuration.

### DELETE /api/v1/settings/chats/{chat_id}/webhook/config

Disable webhook for a chat.

### POST /api/v1/settings/chats/{chat_id}/webhook/test

Test webhook delivery.

## QR Auth Settings

### GET /api/v1/settings/telegram/auth-status

Check Telegram authentication status.

### POST /api/v1/settings/telegram/logout

Logout from Telegram session.

### POST /api/v1/settings/telegram/qr-code

Create a new QR code authentication session.

### GET /api/v1/settings/telegram/qr-status/{session_id}

Check QR authentication session status.

### POST /api/v1/settings/telegram/qr-cancel/{session_id}

Cancel a QR authentication session.

## Reindex Settings

See [Reindex API](reindex-api.md) for full documentation.
