# System API
Языки: [English](system-api.md) | [Русский](system-api_ru.md)

## Проверка работоспособности

### GET /health

Возвращает статус работоспособности всех подсистем.

```bash
curl http://localhost:8000/health
```

Ответ:

```json
{
  "status": "ok",
  "components": {
    "database": "ok",
    "ollama_embeddings": "ok",
    "llm": "ok",
    "telegram": "not_configured"
  },
  "timestamp": "2026-04-10T12:00:00Z"
}
```

Значения статуса компонентов: `ok`, `error`, `degraded`, `not_configured`.
Общий статус: `ok`, `degraded`, `error`.

### GET /

Возвращает базовую информацию о приложении.

## Статистика системы

### GET /api/v1/system/stats

Возвращает общую статистику системы, включая количество сообщений, количество чатов и статус сервисов.

```bash
curl http://localhost:8000/api/v1/system/stats
```

### GET /api/v1/system/throughput

Возвращает текущие метрики пропускной способности системы.

```bash
curl http://localhost:8000/api/v1/system/throughput
```

### GET /api/v1/system/flood-history

Возвращает историю инцидентов FloodWait от ограничителя частоты Telegram.

```bash
curl http://localhost:8000/api/v1/system/flood-history
```

### GET /api/v1/system/request-history

Возвращает недавнюю историю запросов.

```bash
curl http://localhost:8000/api/v1/system/request-history
```

## Статистика ограничителя частоты

### GET /api/v1/system/rate-limiter/stats

Возвращает детальную статистику ограничителя частоты.

### GET /api/v1/system/rate-limiter/incidents

Возвращает детальную историю инцидентов FloodWait.
