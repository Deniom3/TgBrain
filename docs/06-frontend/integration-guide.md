# Frontend Integration Guide
Languages: [English](integration-guide.md) | [Русский](integration-guide_ru.md)

## Overview

TgBrain provides a REST API that can be consumed by any frontend framework. This guide covers common integration patterns.

## Base URL

```
http://localhost:8000
```

## Authentication

Most endpoints require an active Telegram session. Check authentication status before making management requests:

```javascript
const status = await fetch('/api/v1/settings/telegram/auth-status');
const data = await status.json();

if (!data.authenticated) {
  // Redirect to QR auth
  window.location.href = '/qr-auth';
}
```

## QR Authentication Flow

1. Create a QR session
2. Poll for status
3. Redirect to app when authenticated

```javascript
async function startQRAuth() {
  const response = await fetch('/api/v1/settings/telegram/qr-code', {
    method: 'POST'
  });
  const { session_id, qr_url } = await response.json();

  // Open QR auth page
  window.open(qr_url, '_blank');

  // Poll for completion
  const poll = setInterval(async () => {
    const status = await fetch(`/api/v1/settings/telegram/qr-status/${session_id}`);
    const data = await status.json();

    if (data.status === 'authenticated') {
      clearInterval(poll);
      // Auth complete
    }
  }, 2000);
}
```

## Fetching Summaries

```javascript
async function getSummaries(chatId, page = 1) {
  const response = await fetch(
    `/api/v1/chats/${chatId}/summary?page=${page}&limit=10`
  );
  return response.json();
}

async function generateSummary(chatId, periodMinutes = 1440) {
  const response = await fetch(
    `/api/v1/chats/${chatId}/summary/generate`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ period_minutes: periodMinutes })
    }
  );
  return response.json();
}
```

## Polling Task Status

```javascript
async function pollTaskStatus(chatId, taskId) {
  const response = await fetch(
    `/api/v1/chats/${chatId}/summary/${taskId}`
  );
  return response.json();
}

// Poll every 3 seconds until complete
async function waitForTask(chatId, taskId) {
  return new Promise((resolve) => {
    const poll = setInterval(async () => {
      const task = await pollTaskStatus(chatId, taskId);
      if (task.status === 'completed' || task.status === 'failed') {
        clearInterval(poll);
        resolve(task);
      }
    }, 3000);
  });
}
```

## RAG Search

```javascript
async function search(query, chatId) {
  const response = await fetch('/api/v1/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, chat_id: chatId })
  });
  return response.json();
}
```

## Error Handling

All error responses include a `status` and `message` field:

```javascript
async function safeFetch(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.message || `HTTP ${response.status}`);
  }

  if (data.status === 'error') {
    throw new Error(data.message);
  }

  return data;
}
```

## CORS

The FastAPI application includes CORS middleware. Configure allowed origins in the application startup if needed.

## Swagger UI

For interactive API exploration, use the built-in Swagger UI at http://localhost:8000/docs.
