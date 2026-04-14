# Webhook
Языки: [English](webhook.md) | [Русский](webhook_ru.md)

## Обзор

Система вебхуков доставляет сгенерированные суммаризации на внешние URL. Каждый чат может иметь собственную конфигурацию вебхука с настраиваемыми шаблонами и логикой повторных попыток.

## Конфигурация

### Структура конфигурации вебхука

Конфигурация вебхука содержит следующие поля:

| Поле | Тип | Обязателен | Описание |
|-------|------|----------|----------|
| `url` | string | Да | Целевой URL (должен начинаться с http:// или https://) |
| `method` | string | Нет | HTTP метод: `POST`, `GET`, `PUT`, `PATCH`, `DELETE` (по умолчанию: `POST`) |
| `headers` | object | Нет | Пользовательские HTTP заголовки |
| `body_template` | object | Да | Шаблон тела запроса (должен содержать переменную `{{summary}}`) |

### Установка вебхука

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

### Получение конфигурации вебхука

```bash
curl http://localhost:8000/api/v1/settings/chats/{chat_id}/webhook/config
```

### Тестирование вебхука

```bash
curl -X POST http://localhost:8000/api/v1/settings/chats/{chat_id}/webhook/test
```

### Отключение вебхука

```bash
curl -X DELETE http://localhost:8000/api/v1/settings/chats/{chat_id}/webhook/config
```

## Полезная нагрузка вебхука

Структура полезной нагрузки по умолчанию:

```json
{
  "chat_id": -1001234567890,
  "chat_title": "Мой чат",
  "period_start": "2026-04-01T00:00:00Z",
  "period_end": "2026-04-02T00:00:00Z",
  "summary": "Текст суммаризации...",
  "generated_at": "2026-04-02T09:00:00Z",
  "message_count": 150
}
```

## Шаблоны

Шаблоны тела запроса используют простую подстановку строк с переменными `{{summary}}` и `{{chat_id}}`. `body_template` должен содержать хотя бы один плейсхолдер `{{summary}}`, который будет заменён текстом сгенерированной суммаризации.

## Доставка

Вебхуки доставляются с:

- **Логикой повторных попыток** -- неудачные доставки повторяются с экспоненциальной задержкой
- **Ограничением скорости** -- aiolimiter предотвращает перегрузку целевого эндпоинта
- **Таймаутом** -- запросы имеют настраиваемый таймаут

## Автоматическая доставка

Когда суммаризация генерируется (через API или расписание) и для этого чата настроен вебхук, суммаризация автоматически доставляется. Ручную доставку можно запустить через:

```bash
curl -X POST http://localhost:8000/api/v1/chats/{chat_id}/summary/send-webhook
```
