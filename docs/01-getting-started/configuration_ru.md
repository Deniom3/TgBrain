# Конфигурация
Языки: [English](configuration.md) | [Русский](configuration_ru.md)

## Переменные окружения

Вся конфигурация управляется через переменные окружения. Скопируйте `.env.example` в `.env` и измените значения.

### Настройки Telegram

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `TG_API_ID` | Да | - | Telegram API ID с my.telegram.org |
| `TG_API_HASH` | Да | - | Telegram API Hash с my.telegram.org |
| `TG_PHONE_NUMBER` | Нет | - | Номер телефона для классической аутентификации (не QR) |
| `TG_CHAT_ENABLE` | Нет | - | Список ID чатов через запятую для включения при запуске |
| `TG_CHAT_DISABLE` | Нет | - | Список ID чатов через запятую для отключения при запуске |

### Настройки базы данных

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `DB_HOST` | Нет | localhost | Хост PostgreSQL |
| `DB_PORT` | Нет | 5432 | Порт PostgreSQL |
| `DB_NAME` | Нет | tg_db | Имя базы данных |
| `DB_USER` | Нет | postgres | Пользователь базы данных |
| `DB_PASSWORD` | Да | - | Пароль базы данных |
| `DB_URL` | Нет | автогенерируется | Полная строка подключения (переопределяет другие DB переменные) |

### Настройки LLM провайдера

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `LLM_ACTIVE_PROVIDER` | Нет | gemini | Активный LLM провайдер: gemini, openrouter, ollama, lm-studio |
| `LLM_FALLBACK_PROVIDERS` | Нет | openrouter,gemini | Список резервных провайдеров через запятую |
| `LLM_AUTO_FALLBACK` | Нет | true | Включить автоматическое переключение при ошибке |
| `LLM_FALLBACK_TIMEOUT` | Нет | 10 | Таймаут в секундах перед попыткой резервного варианта |

#### Gemini LLM

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `GEMINI_API_KEY` | Да* | - | Gemini API key (обязателен, если Gemini активен) |
| `GEMINI_BASE_URL` | Нет | https://generativelanguage.googleapis.com | Базовый URL |
| `GEMINI_MODEL` | Нет | gemini-2.5-flash | Имя модели |

#### OpenRouter LLM

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `OPENROUTER_API_KEY` | Да* | - | OpenRouter API key (обязателен, если OpenRouter активен) |
| `OPENROUTER_BASE_URL` | Нет | https://openrouter.ai/api/v1 | Базовый URL |
| `OPENROUTER_MODEL` | Нет | auto | Имя модели (auto = пусть OpenRouter выберет) |

#### Ollama LLM

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `OLLAMA_LLM_ENABLED` | Нет | true | Включить Ollama как LLM провайдер |
| `OLLAMA_LLM_BASE_URL` | Нет | http://localhost:11434 | URL сервера Ollama |
| `OLLAMA_LLM_MODEL` | Нет | deepseek-coder:6.7b | Имя модели |

#### LM Studio LLM

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `LM_STUDIO_ENABLED` | Нет | false | Включить LM Studio как LLM провайдер |
| `LM_STUDIO_BASE_URL` | Нет | http://localhost:1234 | Базовый URL |
| `LM_STUDIO_MODEL` | Нет | - | Имя модели |
| `LM_STUDIO_API_KEY` | Нет | - | API key (если требуется) |

### Настройки embedding провайдера

#### Ollama Embeddings

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `OLLAMA_EMBEDDING_PROVIDER` | Нет | ollama | Активный embedding провайдер |
| `OLLAMA_EMBEDDING_URL` | Нет | http://localhost:11434 | URL сервера Ollama |
| `OLLAMA_EMBEDDING_MODEL` | Нет | nomic-embed-text | Имя модели |
| `OLLAMA_EMBEDDING_DIM` | Нет | автоопределяется | Размерность вектора (автоопределяется при первом использовании) |
| `OLLAMA_EMBEDDING_MAX_RETRIES` | Нет | 3 | Максимальное количество повторных попыток |
| `OLLAMA_EMBEDDING_TIMEOUT` | Нет | 30 | Таймаут запроса в секундах |
| `OLLAMA_EMBEDDING_NORMALIZE` | Нет | false | Нормализовать выходные векторы |

#### Gemini Embeddings

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `GEMINI_EMBEDDING_URL` | Нет | https://generativelanguage.googleapis.com | Базовый URL |
| `GEMINI_EMBEDDING_MODEL` | Нет | text-embedding-004 | Имя модели |
| `GEMINI_EMBEDDING_DIM` | Нет | 768 | Размерность вектора |

#### OpenRouter Embeddings

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `OPENROUTER_EMBEDDING_URL` | Нет | https://openrouter.ai/api/v1 | Базовый URL |
| `OPENROUTER_EMBEDDING_MODEL` | Нет | openai/text-embedding-3-small | Имя модели |
| `OPENROUTER_EMBEDDING_DIM` | Нет | 1536 | Размерность вектора |
| `OPENROUTER_EMBEDDING_BATCH_SIZE` | Нет | 20 | Размер батча для embedding запросов |

#### LM Studio Embeddings

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `LM_STUDIO_EMBEDDING_URL` | Нет | http://localhost:1234 | Базовый URL |
| `LM_STUDIO_EMBEDDING_MODEL` | Нет | - | Имя модели |
| `LM_STUDIO_EMBEDDING_DIM` | Нет | - | Размерность вектора |
| `LM_STUDIO_EMBEDDING_API_KEY` | Нет | - | API key |

### Настройки приложения

| Переменная | Обязательна | По умолчанию | Описание |
|-----------|-------------|--------------|----------|
| `LOG_LEVEL` | Нет | INFO | Уровень логирования: DEBUG, INFO, WARNING, ERROR |
| `TIMEZONE` | Нет | Etc/UTC | Часовой пояс приложения (формат IANA) |
| `SUMMARY_DEFAULT_HOURS` | Нет | 24 | Период суммаризации по умолчанию в часах |
| `SUMMARY_MAX_MESSAGES` | Нет | 50 | Максимальное количество сообщений в суммаризации |
| `RAG_TOP_K` | Нет | 5 | Количество результатов для RAG поиска |
| `RAG_SCORE_THRESHOLD` | Нет | 0.3 | Минимальный порог схожести (0.0-1.0) |

## Хранение настроек

Настройки хранятся в двух слоях:

1. **Переменные окружения** — начальные значения по умолчанию из `.env`
2. **База данных** — переопределения во время выполнения, хранящиеся в таблицах `app_settings`, `llm_providers`, `embedding_providers` и `chat_settings`

При запуске приложение загружает настройки из базы данных, если они существуют, переопределяя значения `.env`. Все изменения, внесённые через API, сохраняются в базу данных.

## Получение учётных данных Telegram API

1. Перейдите на https://my.telegram.org
2. Войдите с помощью номера телефона
3. Перейдите в "API development tools"
4. Создайте новое приложение
5. Скопируйте `API ID` и `API Hash` в ваш `.env` файл

## Следующие шаги

1. [Настройка Docker](docker-setup_ru.md)
2. [Аутентификация в Telegram](qr-auth_ru.md)
