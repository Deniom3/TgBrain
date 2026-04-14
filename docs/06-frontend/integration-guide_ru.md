# Руководство по интеграции фронтенда
Языки: [English](integration-guide.md) | [Русский](integration-guide_ru.md)

## Обзор

TgBrain предоставляет REST API, которое может использоваться любым фронтенд-фреймворком. Это руководство охватывает распространённые паттерны интеграции.

## Базовый URL

```
http://localhost:8000
```

## Аутентификация

Большинство эндпоинтов требуют активной сессии Telegram. Проверяйте статус аутентификации перед отправкой запросов на управление:

```javascript
const status = await fetch('/api/v1/settings/telegram/auth-status');
const data = await status.json();

if (!data.authenticated) {
  // Redirect to QR auth
  window.location.href = '/qr-auth';
}
```

## Поток QR-аутентификации

1. Создать сессию QR
2. Опрос статуса
3. Перенаправление в приложение после аутентификации

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

## Получение саммари

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

## Опрос статуса задачи

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

## RAG-поиск

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

## Обработка ошибок

Все ответы с ошибками включают поля `status` и `message`:

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

Приложение FastAPI включает middleware CORS. При необходимости настройте разрешённые origins при запуске приложения.

## Swagger UI

Для интерактивного изучения API используйте встроенный Swagger UI по адресу http://localhost:8000/docs.
