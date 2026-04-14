# API управления чатами
Языки: [English](chat-management-api.md) | [Русский](chat-management-api_ru.md)

## Обзор

Управление чатами осуществляется через эндпоинты Settings API по пути `/api/v1/settings/chats`. Эти эндпоинты контролируют, какие Telegram-чаты отслеживаются для ingest сообщений.

## Эндпоинты

### Список всех чатов

```bash
GET /api/v1/settings/chats
```

Возвращает все зарегистрированные настройки чатов.

### Список чатов с метаданными

```bash
GET /api/v1/settings/chats/list
```

Возвращает чаты с дополнительными метаданными, такими как название, количество участников и последняя активность.

### Список отслеживаемых чатов

```bash
GET /api/v1/settings/chats/monitored
```

Возвращает только чаты с включённым мониторингом.

### Получить настройки чата

```bash
GET /api/v1/settings/chats/{chat_id}
```

Возвращает настройки конкретного чата.

### Обновить настройки чата

```bash
PUT /api/v1/settings/chats/{chat_id}
```

Обновить конфигурацию чата.

### Удалить чат

```bash
DELETE /api/v1/settings/chats/{chat_id}
```

Удалить чат из системы.

### Включить мониторинг

```bash
POST /api/v1/settings/chats/{chat_id}/enable
```

Включить ingest сообщений для чата.

### Отключить мониторинг

```bash
POST /api/v1/settings/chats/{chat_id}/disable
```

Отключить ingest сообщений для чата.

### Переключить мониторинг

```bash
POST /api/v1/settings/chats/{chat_id}/toggle
```

Переключить состояние мониторинга (включить, если отключён; отключить, если включён).

### Массовое обновление

```bash
POST /api/v1/settings/chats/bulk-update
```

Обновить несколько чатов в одном запросе.

```json
{
  "chats": [
    {"chat_id": -1001234567890, "enabled": true},
    {"chat_id": -1009876543210, "enabled": false}
  ]
}
```

### Синхронизация с Telegram

```bash
POST /api/v1/settings/chats/sync
```

Синхронизировать список чатов с Telegram. Обнаруживает новые чаты и обновляет метаданные.

### Добавить пользователя для мониторинга

```bash
POST /api/v1/settings/chats/user/add
```

Добавить приватный чат пользователя в мониторинг.

### Удалить пользователя из мониторинга

```bash
POST /api/v1/settings/chats/user/remove
```

Удалить приватный чат пользователя из мониторинга.
