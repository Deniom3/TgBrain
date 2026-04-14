# QR Authentication
Languages: [English](qr-auth.md) | [Русский](qr-auth_ru.md)

## Overview

TgBrain uses QR code authentication to connect to Telegram. This method does not require entering a phone number or receiving SMS codes -- simply scan the QR code with your Telegram mobile app.

## How It Works

1. The application generates a QR code linked to a temporary Telegram session
2. You scan the QR code with Telegram on your phone
3. Telegram confirms the login on your phone
4. The application receives the session data and stores it encrypted in the database
5. Future starts use the stored session automatically

## Authenticating

### Via Web Interface

1. Start the application
2. Open http://localhost:8000/qr-auth in your browser
3. A QR code will be displayed
4. Open Telegram on your phone
5. Go to Settings > Devices > Link Desktop Device
6. Scan the QR code
7. Confirm the login on your phone

### Via API

Create a QR authentication session:

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/qr-code
```

Response:

```json
{
  "session_id": "abc123",
  "qr_url": "http://localhost:8000/qr-auth?session=abc123"
}
```

Open the `qr_url` in your browser to see the QR code.

Check authentication status:

```bash
curl http://localhost:8000/api/v1/settings/telegram/qr-status/abc123
```

Response while waiting:

```json
{
  "status": "waiting",
  "session_id": "abc123"
}
```

Response after successful auth:

```json
{
  "status": "authenticated",
  "session_id": "abc123"
}
```

Cancel a session:

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/qr-cancel/abc123
```

## Session Management

### Check Auth Status

```bash
curl http://localhost:8000/api/v1/settings/telegram/auth-status
```

Response:

```json
{
  "authenticated": true,
  "user_id": 123456789,
  "username": "your_username",
  "phone": "+1234567890"
}
```

### Check Session Health

```bash
curl http://localhost:8000/api/v1/settings/telegram/check
```

Response:

```json
{
  "status": "healthy",
  "user_id": 123456789
}
```

### Logout

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/logout
```

This destroys the current Telegram session and removes stored session data.

## Session Storage

Session data is encrypted using the `cryptography` library and stored in the `telegram_auth` database table. Temporary session files are created during authentication and cleaned up afterward.

## Automatic Reconnection

On startup, the application checks for stored session data. If a valid session exists, it automatically connects to Telegram and begins message ingestion. No manual authentication is needed after the initial setup.

## Troubleshooting

### QR Code Expires

QR codes have a limited lifetime. If the code expires, create a new session via the API or refresh the web page.

### Authentication Fails

Ensure:
- Your Telegram app is up to date
- You are scanning with the correct Telegram account
- Your internet connection is stable

### Session Invalidated

If Telegram invalidates your session (e.g., password change, security settings), you will need to re-authenticate. Check the auth status endpoint and re-authenticate if needed.
