# Схема базы данных

Языки: [English](database-schema.md) | [Русский](database-schema_ru.md)

## Обзор

TgBrain использует PostgreSQL с расширением pgvector для хранения сообщений, настроек и векторных эмбеддингов.

## Таблицы

### telegram_auth

Хранит зашифрованные данные сессии Telegram. Таблица из одной строки (id = 1).

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | integer | Первичный ключ (всегда 1) |
| `api_id` | integer | Telegram API ID |
| `api_hash` | text | Telegram API Hash |
| `phone_number` | text | Номер телефона (опционально) |
| `session_name` | text | Имя сессии (по умолчанию: 'qr_auth_session') |
| `session_data` | bytea | Зашифрованные данные сессии |
| `updated_at` | timestamptz | Временная метка последнего обновления |

### chat_settings

Конфигурация отслеживаемых чатов Telegram.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | serial | Первичный ключ |
| `chat_id` | bigint | ID чата Telegram (UNIQUE) |
| `title` | text | Название чата |
| `type` | text | Тип чата (по умолчанию: 'private') |
| `last_message_id` | bigint | ID последнего обработанного сообщения |
| `is_monitored` | boolean | Отслеживается ли чат |
| `summary_enabled` | boolean | Включена ли генерация суммаризаций |
| `summary_period_minutes` | integer | Период суммаризации в минутах (по умолчанию: 1440) |
| `summary_schedule` | varchar(50) | Расписание (HH:MM или cron, хранится в UTC) |
| `custom_prompt` | text | Пользовательский промпт для суммаризации |
| `webhook_config` | jsonb | Конфигурация webhook |
| `webhook_enabled` | boolean | Включён ли webhook |
| `next_schedule_run` | timestamptz | Время следующего запуска по расписанию |
| `created_at` | timestamptz | Временная метка создания |
| `updated_at` | timestamptz | Временная метка последнего обновления |

### messages

Сохранённые сообщения Telegram с векторными эмбеддингами.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | bigint | Первичный ключ (ID сообщения Telegram) |
| `chat_id` | bigint | ID чата (FK к chat_settings) |
| `sender_id` | bigint | ID пользователя-отправителя |
| `sender_name` | text | Отображаемое имя |
| `message_text` | text | Содержимое сообщения |
| `message_date` | timestamptz | Временная метка сообщения |
| `message_link` | text | Ссылка на сообщение |
| `embedding` | vector(1024) | Векторный эмбеддинг |
| `embedding_model` | text | Название использованной модели эмбеддинга |
| `is_processed` | boolean | Обработано ли сообщение |
| `created_at` | timestamptz | Временная метка сохранения |

### pending_messages

Сообщения, ожидающие эмбеддинга или обработки.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | serial | Первичный ключ |
| `message_data` | jsonb | Полные данные сообщения в формате JSON |
| `retry_count` | integer | Количество повторных попыток |
| `last_error` | text | Текст последней ошибки |
| `created_at` | timestamptz | Временная метка создания |

### chat_summaries

Сгенерированные суммаризации и записи задач.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | serial | Первичный ключ |
| `chat_id` | bigint | ID чата (FK к chat_settings) |
| `status` | text | Статус задачи: pending, processing, completed, failed |
| `params_hash` | text | Хэш параметров генерации (для кэширования) |
| `result_text` | text | Текст суммаризации или сообщение об ошибке |
| `period_start` | timestamptz | Начало периода суммаризации |
| `period_end` | timestamptz | Конец периода суммаризации |
| `messages_count` | integer | Количество суммированных сообщений |
| `embedding` | vector(1024) | Векторный эмбеддинг суммаризации |
| `embedding_model` | text | Название использованной модели эмбеддинга |
| `generated_by` | text | Тип генератора (по умолчанию: 'llm') |
| `metadata` | jsonb | Метаданные генерации (llm_model, tokens_used и т.д.) |
| `created_at` | timestamptz | Временная метка создания |
| `updated_at` | timestamptz | Временная метка последнего обновления |

### llm_providers

Конфигурации LLM-провайдеров.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | serial | Первичный ключ |
| `name` | text | Название провайдера (UNIQUE) |
| `is_active` | boolean | Является ли провайдер активным |
| `api_key` | text | API ключ |
| `base_url` | text | Базовый URL |
| `model` | text | Название модели |
| `is_enabled` | boolean | Включён ли провайдер |
| `priority` | integer | Приоритет fallback |
| `description` | text | Описание провайдера |
| `created_at` | timestamptz | Временная метка создания |
| `updated_at` | timestamptz | Временная метка последнего обновления |

### embedding_providers

Конфигурации провайдеров эмбеддингов.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | serial | Первичный ключ |
| `name` | text | Название провайдера (UNIQUE) |
| `is_active` | boolean | Является ли провайдер активным |
| `api_key` | text | API ключ |
| `base_url` | text | Базовый URL |
| `model` | text | Название модели |
| `is_enabled` | boolean | Включён ли провайдер |
| `priority` | integer | Приоритет fallback |
| `description` | text | Описание провайдера |
| `embedding_dim` | integer | Размерность вектора (по умолчанию: 768) |
| `max_retries` | integer | Макс. повторных попыток (по умолчанию: 3) |
| `timeout` | integer | Таймаут запроса в секундах (по умолчанию: 30) |
| `normalize` | boolean | Нормализовать выходные векторы (по умолчанию: false) |
| `created_at` | timestamptz | Временная метка создания |
| `updated_at` | timestamptz | Временная метка последнего обновления |

### app_settings

Ключ-значение настроек уровня приложения.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | serial | Первичный ключ |
| `key` | text | Ключ настройки (UNIQUE) |
| `value` | text | Значение настройки |
| `value_type` | text | Тип значения: string, int, bool, float |
| `description` | text | Описание настройки |
| `is_sensitive` | boolean | Является ли значение конфиденциальным |
| `updated_at` | timestamptz | Временная метка последнего обновления |

### reindex_settings

Конфигурация сервиса переиндексации. Таблица из одной строки (id = 1).

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | integer | Первичный ключ (всегда 1) |
| `batch_size` | integer | Сообщений в пакете (по умолчанию: 50) |
| `delay_between_batches` | float | Задержка между пакетами в секундах |
| `auto_reindex_on_model_change` | boolean | Автопереиндексация при смене модели |
| `auto_reindex_new_messages` | boolean | Автопереиндексация новых сообщений |
| `reindex_new_messages_delay` | integer | Задержка перед переиндексацией новых сообщений |
| `max_concurrent_tasks` | integer | Макс. параллельных задач переиндексации |
| `max_retries` | integer | Макс. повторных попыток |
| `speed_mode` | text | Режим скорости: slow, medium, fast, aggressive |
| `current_batch_size` | integer | Текущий адаптивный размер пакета |
| `last_reindex_model` | text | Название последней переиндексированной модели |
| `low_priority_delay` | float | Задержка для низкоприоритетных задач |
| `normal_priority_delay` | float | Задержка для среднеприоритетных задач |
| `high_priority_delay` | float | Задержка для высокоприоритетных задач |
| `updated_at` | timestamptz | Временная метка последнего обновления |

### reindex_tasks

История задач переиндексации.

| Столбец | Тип | Описание |
|--------|------|----------|
| `id` | text | Первичный ключ (UUID задачи) |
| `status` | text | Статус задачи |
| `priority` | integer | Уровень приоритета (0=low, 1=normal, 2=high) |
| `target_model` | text | Целевая модель эмбеддинга |
| `total_messages` | integer | Всего сообщений для обработки |
| `processed_count` | integer | Обработано сообщений |
| `failed_count` | integer | Ошибок обработки |
| `batch_size` | integer | Размер пакета |
| `delay_between_batches` | float | Задержка между пакетами |
| `created_at` | timestamptz | Временная метка создания |
| `started_at` | timestamptz | Временная метка запуска |
| `completed_at` | timestamptz | Временная метка завершения |
| `error` | text | Сообщение об ошибке (при неудаче) |
| `progress_percent` | float | Процент выполнения |

## Индексы

### HNSW-индекс для векторов

Сообщения индексируются с помощью HNSW-индекса pgvector для быстрого приблизительного поиска ближайших соседей:

```sql
CREATE INDEX idx_embedding ON messages USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
```

Суммаризации чатов также имеют HNSW-индекс для семантического поиска:

```sql
CREATE INDEX idx_chat_summary_embedding ON chat_summaries USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
```

### Стандартные индексы

- `messages(chat_id)` -- Фильтрация по чату
- `messages(message_date DESC)` -- Запросы по диапазону дат
- `chat_summaries(chat_id)` -- Фильтрация по чату
- `chat_summaries(created_at DESC)` -- Поиск последних суммаризаций
- `chat_summaries(chat_id, period_start, period_end)` -- Поиск по периоду
- `chat_summaries(params_hash)` -- Поиск в кэше
- `chat_summaries(status)` -- Фильтрация по статусу задачи
- `chat_summaries(status, created_at)` -- Запросы очистки задач
