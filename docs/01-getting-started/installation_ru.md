# Установка
Языки: [English](installation.md) | [Русский](installation_ru.md)

## Системные требования

- Python 3.12 или выше
- PostgreSQL 14+ с расширением pgvector
- Docker и Docker Compose (опционально, рекомендуется)
- Учётные данные Telegram API (API ID и API Hash)

## Способы установки

### Способ 1: Docker Compose (рекомендуется)

Самый простой способ запуска TgBrain — с помощью Docker Compose. Этот способ включает PostgreSQL с pgvector.

```bash
# Запуск всех сервисов
scripts\start.bat

# Просмотр логов
scripts\logs.bat app

# Остановка всех сервисов
scripts\stop.bat
```

### Способ 2: Ручная установка

#### Шаг 1: Клонирование репозитория

```bash
git clone <repository-url>
cd TelegramMessageSummarizer
```

#### Шаг 2: Создание виртуального окружения

```bash
python -m venv venv
venv\Scripts\activate
```

#### Шаг 3: Установка зависимостей

```bash
pip install -r requirements.txt
```

#### Шаг 4: Настройка окружения

```bash
copy .env.example .env
```

Отредактируйте `.env` с вашими настройками. Как минимум, вам нужно:

```env
# Учётные данные Telegram API (обязательно)
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash

# База данных (обязательно)
DB_PASSWORD=your_password
```

#### Шаг 5: Запуск PostgreSQL

Убедитесь, что PostgreSQL запущен с установленным расширением pgvector.

#### Шаг 6: Запуск приложения

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Проверка

После запуска приложения:

- **Swagger UI:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

Эндпоинт health возвращает статус всех подсистем:

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

## Следующие шаги

1. [Конфигурация приложения](configuration_ru.md)
2. [Настройка Docker](docker-setup_ru.md)
3. [Аутентификация в Telegram](qr-auth_ru.md)
