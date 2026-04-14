# Docker Setup
Языки: [English](docker-setup.md) | [Русский](docker-setup_ru.md)

## Обзор

TgBrain предоставляет конфигурацию Docker Compose для простого развёртывания. Compose-настройка включает:

- PostgreSQL 16 с расширением pgvector
- Приложение TgBrain

## Предварительные требования

- Docker Desktop для Windows
- Docker Compose v2+

## Запуск приложения

### Запуск всех сервисов

```bash
scripts\start.bat
```

Эта команда запускает `docker compose up -d` и стартует PostgreSQL и приложение.

### Просмотр логов

```bash
# Логи приложения
scripts\logs.bat app

# Логи PostgreSQL
scripts\logs.bat db

# Все логи
scripts\logs.bat
```

### Остановка приложения

```bash
scripts\stop.bat
```

Эта команда запускает `docker compose down` и останавливает все сервисы.

## Конфигурация Docker Compose

Файл `docker-compose.yml` определяет два сервиса:

### Сервис PostgreSQL

- Образ: `pgvector/pgvector:pg16`
- Порт: 5432 (только внутренний, не доступен на хосте)
- Том: `pgdata` для постоянного хранения
- Проверка здоровья: тестирует подключение к базе данных

### Сервис приложения

- Сборка: из `Dockerfile`
- Порт: 8000 (доступен на хосте)
- Зависит от: сервис PostgreSQL
- Окружение: загружается из файла `.env`
- Тома: исходный код смонтирован для разработки

## Сетевое взаимодействие Docker

### Доступ к внешним сервисам из Docker

Если вы запускаете Ollama или другие внешние сервисы на вашей хост-машине, используйте `host.docker.internal` вместо `localhost`:

```env
# Неправильно - localhost указывает на контейнер, а не на хост
OLLAMA_EMBEDDING_URL=http://localhost:11434

# Правильно - разрешается в адрес хост-машины
OLLAMA_EMBEDDING_URL=http://host.docker.internal:11434
```

## Сохранение данных

Данные PostgreSQL хранятся в именованном томе Docker `pgdata`. Эти данные сохраняются при перезапуске и пересборке контейнеров.

Для сброса всех данных:

```bash
docker compose down -v
```

## Пользовательский Dockerfile

`Dockerfile` основан на Python 3.12-slim:

1. Установка системных зависимостей
2. Копирование и установка Python-зависимостей
3. Копирование исходного кода приложения
4. Запуск от имени пользователя без root-прав
5. Открытие порта 8000

## Docker Compose для тестирования

Отдельный `docker-compose.test.yml` доступен для запуска тестов в изолированном окружении:

```bash
docker compose -f docker-compose.test.yml up
```

## Устранение неполадок

### Контейнер не запускается

Проверьте логи на наличие ошибок:

```bash
scripts\logs.bat
```

### Отказано в подключении к базе данных

Убедитесь, что PostgreSQL работает нормально перед запуском приложения:

```bash
docker compose ps
```

Сервис PostgreSQL должен показывать статус `(healthy)`.

### Ollama недоступен

Не забудьте использовать `host.docker.internal` в вашем `.env`:

```env
OLLAMA_EMBEDDING_URL=http://host.docker.internal:11434
OLLAMA_LLM_BASE_URL=http://host.docker.internal:11434
```

## Следующие шаги

1. [Аутентификация в Telegram](qr-auth_ru.md)
2. [Конфигурация приложения](configuration_ru.md)
