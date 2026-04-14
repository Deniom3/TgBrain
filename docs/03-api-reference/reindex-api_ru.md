# Reindex API
Языки: [English](reindex-api.md) | [Русский](reindex-api_ru.md)

## Проверка необходимости реиндекса

### GET /api/v1/settings/reindex/check

Возвращает, требуется ли реиндекс на основе изменений embedding модели.

```bash
curl http://localhost:8000/api/v1/settings/reindex/check
```

Ответ:

```json
{
  "reindex_needed": false,
  "reason": null
}
```

## Статус реиндекса

### GET /api/v1/settings/reindex/status

Возвращает текущий статус сервиса реиндекса.

```bash
curl http://localhost:8000/api/v1/settings/reindex/status
```

Ответ:

```json
{
  "running": false,
  "current_task": null,
  "queue_size": 0,
  "progress": null
}
```

## Статистика реиндекса

### GET /api/v1/settings/reindex/stats

Возвращает статистику по embedding моделям и количеству сообщений.

```bash
curl http://localhost:8000/api/v1/settings/reindex/stats
```

## Запуск реиндекса

### POST /api/v1/settings/reindex/start

Запустить операцию реиндекса.

```bash
curl -X POST http://localhost:8000/api/v1/settings/reindex/start \
  -H "Content-Type: application/json" \
  -d '{
    "priority": "normal",
    "model_name": "nomic-embed-text"
  }'
```

## Управление реиндексом

### POST /api/v1/settings/reindex/control

Приостановить, возобновить или отменить выполняющийся реиндекс.

```bash
# Приостановить
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'

# Возобновить
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'

# Отменить
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "cancel"}'
```

## История реиндекса

### GET /api/v1/settings/reindex/history

Возвращает историю задач реиндекса.

## Управление скоростью

### GET /api/v1/settings/reindex/speed

Получить текущий режим скорости реиндекса.

### PATCH /api/v1/settings/reindex/speed

Обновить режим скорости реиндекса (low, medium, aggressive).
