# QR Auth API
Языки: [English](qr-auth-api.md) | [Русский](qr-auth-api_ru.md)

## Статус аутентификации

### GET /api/v1/settings/telegram/auth-status

Проверить, активна ли Telegram-сессия.

```bash
curl http://localhost:8000/api/v1/settings/telegram/auth-status
```

## Выход из сессии

### POST /api/v1/settings/telegram/logout

Уничтожить текущую Telegram-сессию.

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/logout
```

## Сессия QR-кода

### POST /api/v1/settings/telegram/qr-code

Создать новую сессию аутентификации через QR-код.

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/qr-code
```

Ответ:

```json
{
  "session_id": "abc123",
  "session_name": "session_abc123",
  "qr_code_data": "tg://resolve?domain=...",
  "expires_in": 300
}
```

## Статус сессии QR

### GET /api/v1/settings/telegram/qr-status/{session_id}

Проверить статус сессии аутентификации через QR-код.

```bash
curl http://localhost:8000/api/v1/settings/telegram/qr-status/abc123
```

Ответ:

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

Поля ответа:
- `exists` -- Сессия существует
- `is_completed` -- Аутентификация успешно завершена
- `is_expired` -- Сессия истекла
- `user_id` -- ID пользователя Telegram (если аутентифицирован)
- `user_username` -- Имя пользователя Telegram (если аутентифицирован)
- `error` -- Сообщение об ошибке (если есть)
- `saved_to_db` -- Данные сессии сохранены в БД
- `reconnect_attempted` -- Попытка переподключения к Telegram выполнена

## Отмена сессии QR

### POST /api/v1/settings/telegram/qr-cancel/{session_id}

Отменить сессию аутентификации через QR-код.

```bash
curl -X POST http://localhost:8000/api/v1/settings/telegram/qr-cancel/abc123
```

## Веб-интерфейс

Веб-интерфейс аутентификации через QR-код доступен по адресу:

```
GET /qr-auth
GET /qr-auth?session={session_id}
```

Это обслуживает HTML-страницу, отображающую QR-код для указанной сессии.
