# Webhook
Languages: [English](webhook.md) | [Русский](webhook_ru.md)

## Overview

The webhook system delivers generated summaries to external URLs. Each chat can have its own webhook configuration with customizable templates and retry logic.

## Configuration

### Webhook Config Structure

The webhook configuration is stored as a structured object with the following fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | string | Yes | Target URL (must start with http:// or https://) |
| `method` | string | No | HTTP method: `POST`, `GET`, `PUT`, `PATCH`, `DELETE` (default: `POST`) |
| `headers` | object | No | Custom HTTP headers as key-value pairs |
| `body_template` | object | Yes | JSON template for the request body (must contain `{{summary}}` variable) |

### Set Webhook

```bash
curl -X PUT http://localhost:8000/api/v1/settings/chats/{chat_id}/webhook/config \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/webhook",
    "method": "POST",
    "headers": {
      "Authorization": "Bearer your-secret-token"
    },
    "body_template": {
      "chat_id": "{{chat_id}}",
      "text": "{{summary}}",
      "parse_mode": "HTML"
    }
  }'
```

### Get Webhook Config

```bash
curl http://localhost:8000/api/v1/settings/chats/{chat_id}/webhook/config
```

### Test Webhook

```bash
curl -X POST http://localhost:8000/api/v1/settings/chats/{chat_id}/webhook/test
```

### Disable Webhook

```bash
curl -X DELETE http://localhost:8000/api/v1/settings/chats/{chat_id}/webhook/config
```

## Webhook Payload

The default payload structure:

```json
{
  "chat_id": -1001234567890,
  "chat_title": "My Chat",
  "period_start": "2026-04-01T00:00:00Z",
  "period_end": "2026-04-02T00:00:00Z",
  "summary": "Summary text content...",
  "generated_at": "2026-04-02T09:00:00Z",
  "message_count": 150
}
```

## Templates

Webhook body templates use simple string substitution with `{{summary}}` and `{{chat_id}}` variables. The `body_template` must contain at least one `{{summary}}` placeholder, which will be replaced with the generated summary text.

## Delivery

Webhooks are delivered with:

- **Retry logic** -- Failed deliveries are retried with exponential backoff
- **Rate limiting** -- aiolimiter prevents overwhelming the target endpoint
- **Timeout** -- Requests have a configurable timeout

## Automatic Delivery

When a summary is generated (via API or schedule) and a webhook is configured for that chat, the summary is automatically delivered. Manual delivery can be triggered via:

```bash
curl -X POST http://localhost:8000/api/v1/chats/{chat_id}/summary/send-webhook
```
