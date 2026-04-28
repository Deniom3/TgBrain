"""
SQL запросы для создания таблиц.

Содержит CREATE TABLE запросы для всех таблиц базы данных.
"""

# ==================== Таблицы ====================

SQL_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id BIGINT PRIMARY KEY,
    chat_id BIGINT REFERENCES chat_settings(chat_id) ON DELETE CASCADE,
    sender_id BIGINT,
    sender_name TEXT,
    message_text TEXT NOT NULL,
    message_date TIMESTAMPTZ NOT NULL,
    message_link TEXT,
    embedding VECTOR(1024),
    embedding_model TEXT,
    is_processed BOOLEAN DEFAULT FALSE,
    is_bot BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
)
"""

SQL_CREATE_PENDING_MESSAGES = """
CREATE TABLE IF NOT EXISTS pending_messages (
    id SERIAL PRIMARY KEY,
    message_data JSONB NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
)
"""

SQL_CREATE_INDICES = """
-- Индекс HNSW для векторного поиска (косинусное расстояние)
-- m = 16: количество связей в графе
-- ef_construction = 128: качество построения (оптимизировано для Ryzen 7)
CREATE INDEX IF NOT EXISTS idx_embedding
    ON messages USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

-- Индекс для сортировки по дате сообщений
CREATE INDEX IF NOT EXISTS idx_message_date
    ON messages (message_date DESC);

-- Индекс для фильтрации по chat_id
CREATE INDEX IF NOT EXISTS idx_chat_id
    ON messages (chat_id);
"""

SQL_CREATE_TELEGRAM_AUTH = """
CREATE TABLE IF NOT EXISTS telegram_auth (
    id INTEGER PRIMARY KEY DEFAULT 1,
    api_id INTEGER,
    api_hash TEXT,
    phone_number TEXT,
    session_name TEXT DEFAULT 'qr_auth_session',
    session_data BYTEA DEFAULT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
)
"""

SQL_CREATE_CHAT_SETTINGS = """
CREATE TABLE IF NOT EXISTS chat_settings (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'private',
    last_message_id BIGINT DEFAULT 0,
    is_monitored BOOLEAN DEFAULT TRUE,
    summary_enabled BOOLEAN DEFAULT TRUE,
    summary_period_minutes INTEGER DEFAULT 1440,
    summary_schedule VARCHAR(50) DEFAULT NULL,
    custom_prompt TEXT,
    webhook_config JSONB,
    webhook_enabled BOOLEAN DEFAULT FALSE,
    filter_bots BOOLEAN DEFAULT TRUE,
    filter_actions BOOLEAN DEFAULT TRUE,
    filter_min_length INTEGER DEFAULT 15 CHECK (filter_min_length >= 0),
    filter_ads BOOLEAN DEFAULT TRUE,
    next_schedule_run TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

SQL_CREATE_LLM_PROVIDERS = """
CREATE TABLE IF NOT EXISTS llm_providers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT FALSE,
    api_key TEXT,
    base_url TEXT NOT NULL,
    model TEXT NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

SQL_CREATE_EMBEDDING_PROVIDERS = """
CREATE TABLE IF NOT EXISTS embedding_providers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT FALSE,
    api_key TEXT,
    base_url TEXT NOT NULL,
    model TEXT NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    description TEXT,
    embedding_dim INTEGER DEFAULT 768,
    max_retries INTEGER DEFAULT 3,
    timeout INTEGER DEFAULT 30,
    normalize BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

SQL_CREATE_APP_SETTINGS = """
CREATE TABLE IF NOT EXISTS app_settings (
    id SERIAL PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    value_type TEXT DEFAULT 'string',
    description TEXT,
    is_sensitive BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

SQL_CREATE_REINDEX_SETTINGS = """
CREATE TABLE IF NOT EXISTS reindex_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    batch_size INTEGER DEFAULT 50,
    delay_between_batches FLOAT DEFAULT 1.0,
    auto_reindex_on_model_change BOOLEAN DEFAULT TRUE,
    auto_reindex_new_messages BOOLEAN DEFAULT TRUE,
    reindex_new_messages_delay INTEGER DEFAULT 60,
    max_concurrent_tasks INTEGER DEFAULT 1,
    max_retries INTEGER DEFAULT 3,
    low_priority_delay FLOAT DEFAULT 2.0,
    normal_priority_delay FLOAT DEFAULT 1.0,
    high_priority_delay FLOAT DEFAULT 0.5,
    last_reindex_model TEXT,
    speed_mode TEXT DEFAULT 'medium',
    current_batch_size INTEGER DEFAULT 50,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT single_row CHECK (id = 1)
)
"""

SQL_CREATE_REINDEX_TASKS = """
CREATE TABLE IF NOT EXISTS reindex_tasks (
    id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'idle',
    priority INTEGER DEFAULT 2,
    target_model TEXT,
    total_messages INTEGER DEFAULT 0,
    processed_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    batch_size INTEGER DEFAULT 50,
    delay_between_batches FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    progress_percent FLOAT DEFAULT 0.0
)
"""

SQL_CREATE_CHAT_SUMMARIES = """
CREATE TABLE IF NOT EXISTS chat_summaries (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL REFERENCES chat_settings(chat_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,  -- ✨ НОВОЕ: для отслеживания обновлений

    -- ✨ НОВЫЕ: Поля жизненного цикла задачи
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    params_hash TEXT,  -- ✨ НОВОЕ: хеш для кэширования
    result_text TEXT,  -- ✨ НОВОЕ: результат (текст summary или ошибка)

    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    messages_count INTEGER DEFAULT 0,
    embedding VECTOR(1024),
    embedding_model TEXT,
    generated_by TEXT DEFAULT 'llm',
    metadata JSONB  -- {llm_model, tokens_used, execution_time_sec, ...}
)
"""

SQL_CREATE_CHAT_SUMMARIES_INDICES = """
CREATE INDEX IF NOT EXISTS idx_chat_summaries_chat_id
    ON chat_summaries (chat_id);

CREATE INDEX IF NOT EXISTS idx_chat_summaries_created_at
    ON chat_summaries (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_summaries_period
    ON chat_summaries (chat_id, period_start, period_end);

CREATE INDEX IF NOT EXISTS idx_chat_summary_embedding
    ON chat_summaries USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);

-- ✨ НОВЫЕ: Индексы для управления задачами
CREATE INDEX IF NOT EXISTS idx_chat_summaries_params_hash
    ON chat_summaries (params_hash);

CREATE INDEX IF NOT EXISTS idx_chat_summaries_status
    ON chat_summaries (status);

CREATE INDEX IF NOT EXISTS idx_chat_summaries_status_created
    ON chat_summaries (status, created_at);  -- ✨ Для производительности очистки
"""

__all__ = [
    "SQL_CREATE_MESSAGES",
    "SQL_CREATE_PENDING_MESSAGES",
    "SQL_CREATE_INDICES",
    "SQL_CREATE_TELEGRAM_AUTH",
    "SQL_CREATE_CHAT_SETTINGS",
    "SQL_CREATE_LLM_PROVIDERS",
    "SQL_CREATE_EMBEDDING_PROVIDERS",
    "SQL_CREATE_APP_SETTINGS",
    "SQL_CREATE_REINDEX_SETTINGS",
    "SQL_CREATE_REINDEX_TASKS",
    "SQL_CREATE_CHAT_SUMMARIES",
    "SQL_CREATE_CHAT_SUMMARIES_INDICES",
]
