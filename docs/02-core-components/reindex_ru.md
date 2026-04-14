# Reindex
Языки: [English](reindex.md) | [Русский](reindex_ru.md)

## Обзор

Служба реиндексации перегенерирует векторные эмбеддинги для всех сообщений при изменении модели или провайдера эмбеддингов. Она работает как фоновая служба с приоритетной очередью и поддерживает операции паузы, возобновления и отмены.

## Когда требуется реиндексация

Реиндексация необходима, когда:
- Изменяется модель эмбеддинга (например, `nomic-embed-text` на `mxbai-embed-large`)
- Изменяется провайдер эмбеддингов (например, Ollama на Gemini)
- Изменяется размерность вектора

Система автоматически определяет необходимость реиндексации через эндпоинт проверки.

## Reindex API

### Проверка необходимости реиндексации

```bash
curl http://localhost:8000/api/v1/settings/reindex/check
```

### Получение статуса реиндексации

```bash
curl http://localhost:8000/api/v1/settings/reindex/status
```

Ответ:

```json
{
  "running": false,
  "current_task": null,
  "queue_size": 0
}
```

### Получение статистики реиндексации

```bash
curl http://localhost:8000/api/v1/settings/reindex/stats
```

Ответ:

```json
{
  "models": {
    "nomic-embed-text": {
      "dimension": 768,
      "message_count": 50000,
      "summary_count": 200
    }
  }
}
```

### Запуск реиндексации

```bash
curl -X POST http://localhost:8000/api/v1/settings/reindex/start \
  -H "Content-Type: application/json" \
  -d '{
    "priority": "normal",
    "model_name": "nomic-embed-text"
  }'
```

### Управление реиндексацией

```bash
# Пауза
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'

# Возобновление
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'

# Отмена
curl -X POST http://localhost:8000/api/v1/settings/reindex/control \
  -H "Content-Type: application/json" \
  -d '{"action": "cancel"}'
```

### История реиндексаций

```bash
curl http://localhost:8000/api/v1/settings/reindex/history
```

## Режимы скорости

Реиндексация поддерживает различные режимы скорости для баланса между временем завершения и нагрузкой на систему:

| Режим | Описание |
|------|-------------|
| low | Минимальное влияние на систему, самый медленный |
| medium | Сбалансированная скорость и нагрузка |
| aggressive | Самый быстрый, наибольшая нагрузка на систему |

### Получение текущей скорости

```bash
curl http://localhost:8000/api/v1/settings/reindex/speed
```

### Изменение скорости

```bash
curl -X PATCH http://localhost:8000/api/v1/settings/reindex/speed \
  -H "Content-Type: application/json" \
  -d '{"mode": "aggressive"}'
```

## Архитектура

```
ReindexService
  |-- TaskQueue           -- приоритетная очередь задач реиндексации
  |-- BatchProcessor      -- обработка сообщений батчами
  |-- TaskExecutor        -- выполнение отдельных задач реиндексации
  |-- TaskManagement      -- создание, пауза, возобновление, отмена задач
  |-- Repository          -- операции с БД для состояния реиндексации
  |-- DirectReindex       -- прямая реиндексация для конкретных моделей
```

## Уровни приоритета

| Приоритет | Описание |
|----------|-------------|
| high | Обрабатывается перед normal и low |
| normal | Приоритет по умолчанию |
| low | Обрабатывается, когда очередь пуста от более высоких приоритетов |
