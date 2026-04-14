# QR Auth API
Languages: [English](qr-auth-api.md) | [Русский](qr-auth-api_ru.md)

## Authentication Status

### GET /api/v1/settings/telegram/auth-status

Check if a Telegram session is active.

```bash
curl http://localhost:8000/api/v1/settings/telegram/auth-status
```

## Logout

### POST /api/v1/settings/telegram/logout

Destroy the current Telegram session.

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/logout
```

## QR Code Session

### POST /api/v1/settings/telegram/qr-code

Create a new QR code authentication session.

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/qr-code
```

Response:

```json
{
  "session_id": "abc123",
  "session_name": "session_abc123",
  "qr_code_data": "tg://resolve?domain=...",
  "expires_in": 300
}
```

## QR Session Status

### GET /api/v1/settings/telegram/qr-status/{session_id}

Check the status of a QR authentication session.

```bash
curl http://localhost:8000/api/v1/settings/telegram/qr-status/abc123
```

Response:

```json
{
  "exists": true,
  "is_completed": false,
  "is_expired": false,
  "user_id": null,
  "user_username": null,
  "error": null,
  "saved_to_db": false,
  "reconnect_attempted": false
}
```

Response fields:
- `exists` -- Session exists
- `is_completed` -- Authentication completed successfully
- `is_expired` -- Session has expired
- `user_id` -- Telegram user ID (if authenticated)
- `user_username` -- Telegram username (if authenticated)
- `error` -- Error message (if any)
- `saved_to_db` -- Session data saved to database
- `reconnect_attempted` -- Reconnection to Telegram attempted

## Cancel QR Session

### POST /api/v1/settings/telegram/qr-cancel/{session_id}

Cancel a QR authentication session.

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/qr-cancel/abc123
```

## Web Interface

The QR authentication web interface is available at:

```
GET /qr-auth
GET /qr-auth?session={session_id}
```

This serves an HTML page displaying the QR code for the specified session.
