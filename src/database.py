"""
Модуль подключения к PostgreSQL с поддержкой pgvector.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg

from src.config import Settings
from src.models.sql import (
    SQL_CREATE_APP_SETTINGS,
    SQL_CREATE_CHAT_SETTINGS,
    SQL_CREATE_CHAT_SUMMARIES,
    SQL_CREATE_EMBEDDING_PROVIDERS,
    SQL_CREATE_LLM_PROVIDERS,
    SQL_CREATE_REINDEX_SETTINGS,
    SQL_CREATE_REINDEX_TASKS,
    SQL_CREATE_TELEGRAM_AUTH,
)

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
_vector_type_checked: bool = False
_vector_type_check_lock = asyncio.Lock()

DB_STARTUP_MAX_RETRIES = 5
DB_STARTUP_RETRY_DELAY_SECONDS = 3


def _get_settings() -> Settings:
    """Получить настройки для подключения к БД."""
    from src.config import get_settings
    return get_settings()


class DatabaseConnectionError(Exception):
    """Исключение при невозможности подключения к БД после всех попыток."""

    def __init__(self, host: str, port: int, max_retries: int, last_error: Exception | None = None) -> None:
        self.host = host
        self.port = port
        self.max_retries = max_retries
        self.last_error = last_error
        message = (
            f"Не удалось подключиться к PostgreSQL ({host}:{port}) "
            f"после {max_retries} попыток. "
            f"Убедитесь что база данных запущена."
        )
        super().__init__(message)


async def get_pool() -> asyncpg.Pool:
    """Получить пул подключений к БД с retry-логикой при старте."""
    global _pool
    if _pool is None:
        settings = _get_settings()
        _pool = await _create_pool_with_retry(settings)

        # Установка оптимального параметра ef_search для всех подключений
        async with _pool.acquire() as conn:
            await conn.execute("SET hnsw.ef_search = 64")

        logger.info("Пул подключений к PostgreSQL создан, hnsw.ef_search = 64")
    return _pool


async def _create_pool_with_retry(settings: Settings) -> asyncpg.Pool:
    """
    Создать пул подключений с retry-логикой.

    Args:
        settings: Настройки подключения к БД.

    Returns:
        Созданный пул подключений asyncpg.Pool.

    Raises:
        DatabaseConnectionError: Если все попытки подключения исчерпаны.
    """
    last_error: Exception | None = None

    for attempt in range(1, DB_STARTUP_MAX_RETRIES + 1):
        try:
            logger.info("Попытка подключения к БД %d/%d...", attempt, DB_STARTUP_MAX_RETRIES)
            pool = await asyncpg.create_pool(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                min_size=2,
                max_size=25,
                command_timeout=30,
                init=_init_connection,
            )
            if attempt > 1:
                logger.info("Подключение к БД установлено с попытки %d", attempt)
            return pool
        except (ConnectionRefusedError, OSError, asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
            last_error = exc
            logger.warning(
                "Попытка %d/%d не удалась: %s",
                attempt,
                DB_STARTUP_MAX_RETRIES,
                exc,
            )
            if attempt < DB_STARTUP_MAX_RETRIES:
                await asyncio.sleep(DB_STARTUP_RETRY_DELAY_SECONDS)

    raise DatabaseConnectionError(
        host=settings.db_host,
        port=settings.db_port,
        max_retries=DB_STARTUP_MAX_RETRIES,
        last_error=last_error,
    )


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Инициализация подключения: регистрация типов и настройки."""
    global _vector_type_checked

    if not _vector_type_checked:
        async with _vector_type_check_lock:
            if not _vector_type_checked:
                type_exists = await conn.fetchval(
                    "SELECT 1 FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE t.typname = 'vector' AND n.nspname = 'public'"
                )
                if type_exists:
                    await _register_vector_codec(conn)
                _vector_type_checked = True
    else:
        await _register_vector_codec(conn)

    await conn.execute("SET hnsw.ef_search = 64")


async def _register_vector_codec(conn: asyncpg.Connection) -> None:
    """Зарегистрировать codec для типа vector на конкретном подключении."""
    await conn.set_type_codec(
        "vector",
        encoder=lambda v: v if isinstance(v, str) else _format_vector(v),
        decoder=lambda v: _parse_vector(v),
        schema="public",
        format="text",
    )


def _format_vector(value: list[float]) -> str:
    """Преобразует list[float] в строковый формат для pgvector."""
    if isinstance(value, str):
        return value
    return "[" + ",".join(str(x) for x in value) + "]"


def _parse_vector(value: bytes | str) -> list[float]:
    """Парсит строковое представление вектора из pgvector."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    # Формат: "[0.1,0.2,0.3]" или "[]"
    value = value.strip("[]")
    if not value:
        return []
    return [float(x) for x in value.split(",")]


async def close_pool() -> None:
    """Закрыть пул подключений."""
    global _pool, _vector_type_checked
    if _pool:
        await _pool.close()
        _pool = None
        _vector_type_checked = False
        logger.info("Пул подключений к PostgreSQL закрыт")


@asynccontextmanager
async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """
    Получить подключение из пула.

    Usage:
        async with get_db() as conn:
            await conn.fetch("SELECT * FROM chat_settings")
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def init_extensions_direct() -> None:
    """Создать расширения PostgreSQL через прямое подключение (БЕЗ пула)."""
    settings = _get_settings()
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )
    try:
        await _init_extensions(conn)
        logger.info("Расширения PostgreSQL активированы (direct connection)")
    finally:
        await conn.close()


async def init_db_tables() -> None:
    """Создание таблиц, индексов (без расширений — они созданы в init_extensions_direct)."""
    async with get_db() as conn:
        async with conn.transaction():
            await _create_auth_tables(conn)
            await _create_chat_tables(conn)
            await _create_message_tables(conn)
            await _create_provider_tables(conn)
            await _create_app_tables(conn)
            await _create_rate_limiter_tables(conn)
            await _create_reindex_tables(conn)
            await _create_indices(conn)

        logger.info("Инициализация таблиц БД завершена")


async def migrate_chat_ids() -> dict[str, int]:
    """
    Исправить неверные chat_id для каналов/супергрупп.

    Старая формула: -1000000000000 + raw_id (неверная)
    Новая формула: -1000000000000 - raw_id (верная)

    Returns:
        Словарь с количеством мигрированных и пропущенных записей.
    """
    from src.ingestion.chat_sync_service import normalize_chat_id

    stats: dict[str, int] = {"migrated": 0, "skipped": 0, "errors": 0}

    async with get_db() as conn:
        rows = await conn.fetch(
            "SELECT chat_id FROM chat_settings WHERE chat_id <= -1000000000 AND chat_id > -1000000000000"
        )

        for row in rows:
            old_chat_id = row["chat_id"]
            raw_id = old_chat_id + 1000000000000

            if raw_id <= 0:
                stats["skipped"] += 1
                continue

            correct_chat_id = normalize_chat_id(raw_id, is_channel=True)

            if old_chat_id == correct_chat_id:
                stats["skipped"] += 1
                continue

            try:
                async with conn.transaction():
                    affected = await conn.execute(
                        "UPDATE chat_settings SET chat_id = $1 WHERE chat_id = $2",
                        correct_chat_id,
                        old_chat_id,
                    )
                    if affected:
                        stats["migrated"] += 1

                    await conn.execute(
                        "UPDATE messages SET chat_id = $1 WHERE chat_id = $2",
                        correct_chat_id,
                        old_chat_id,
                    )

                    await conn.execute(
                        "UPDATE chat_summaries SET chat_id = $1 WHERE chat_id = $2",
                        correct_chat_id,
                        old_chat_id,
                    )
            except Exception as exc:
                logger.warning(
                    "Ошибка миграции chat_id %s → %s: %s",
                    old_chat_id,
                    correct_chat_id,
                    type(exc).__name__,
                )
                stats["errors"] += 1

    if stats["migrated"] > 0:
        logger.info("Миграция chat_id: %s", stats)

    return stats


async def migrate_chat_types() -> dict[str, int]:
    """
    Заполнить поле type для существующих чатов.

    Returns:
        Словарь с количеством обновлённых записей.
    """
    stats: dict[str, int] = {"updated": 0, "skipped": 0}

    async with get_db() as conn:
        rows = await conn.fetch(
            "SELECT chat_id, type FROM chat_settings WHERE type IS NULL OR type = ''"
        )

        for row in rows:
            chat_id = row["chat_id"]

            if chat_id > 0:
                chat_type = "private"
            elif chat_id < -1000000000000:
                chat_type = "channel"
            elif chat_id < 0:
                chat_type = "group"
            else:
                chat_type = "private"

            try:
                await conn.execute(
                    "UPDATE chat_settings SET type = $1 WHERE chat_id = $2",
                    chat_type,
                    chat_id,
                )
                stats["updated"] += 1
            except Exception as exc:
                logger.warning(
                    "Ошибка обновления type для chat_id=%s: %s",
                    chat_id,
                    type(exc).__name__,
                )

    if stats["updated"] > 0:
        logger.info("Миграция chat_type: %s", stats)

    return stats


async def _init_extensions(conn: asyncpg.Connection) -> None:
    """Включить расширения PostgreSQL."""
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    logger.info("Расширение pgvector активировано")


async def _create_auth_tables(conn: asyncpg.Connection) -> None:
    """Создать таблицы аутентификации."""
    await conn.execute(SQL_CREATE_TELEGRAM_AUTH)
    logger.info("Таблица telegram_auth создана")

    await conn.execute("""
        ALTER TABLE telegram_auth
        DROP COLUMN IF EXISTS session_path
    """)
    logger.info("Колонка session_path удалена (миграция)")


async def _create_chat_tables(conn: asyncpg.Connection) -> None:
    """Создать таблицы чатов."""
    await conn.execute(SQL_CREATE_CHAT_SETTINGS)
    logger.info("Таблица chat_settings создана")


async def _create_message_tables(conn: asyncpg.Connection) -> None:
    """Создать таблицы сообщений."""
    await conn.execute("""
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
    """)
    logger.info("Таблица messages создана")

    await conn.execute("""
        ALTER TABLE messages
        ADD COLUMN IF NOT EXISTS embedding_model TEXT
    """)
    logger.info("Колонка embedding_model добавлена (миграция)")

    await conn.execute("""
        ALTER TABLE chat_settings
        ADD COLUMN IF NOT EXISTS filter_bots BOOLEAN DEFAULT TRUE
    """)
    await conn.execute("""
        ALTER TABLE chat_settings
        ADD COLUMN IF NOT EXISTS filter_actions BOOLEAN DEFAULT TRUE
    """)
    await conn.execute("""
        ALTER TABLE chat_settings
        ADD COLUMN IF NOT EXISTS filter_min_length INTEGER DEFAULT 15
    """)
    await conn.execute("""
        ALTER TABLE chat_settings
        ADD COLUMN IF NOT EXISTS filter_ads BOOLEAN DEFAULT TRUE
    """)
    await conn.execute("""
        ALTER TABLE messages
        ADD COLUMN IF NOT EXISTS is_bot BOOLEAN DEFAULT FALSE
    """)
    logger.info("Колонки filter_* и is_bot добавлены (миграция)")

    await conn.execute("""
        DO $$ BEGIN
            ALTER TABLE chat_settings
            ADD CONSTRAINT chk_filter_min_length CHECK (filter_min_length >= 0);
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
    """)
    logger.info("CHECK констрейнт chk_filter_min_length добавлен (миграция)")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_messages (
            id SERIAL PRIMARY KEY,
            message_data JSONB NOT NULL,
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    logger.info("Таблица pending_messages создана")


async def _create_provider_tables(conn: asyncpg.Connection) -> None:
    """Создать таблицы провайдеров."""
    await conn.execute(SQL_CREATE_LLM_PROVIDERS)
    logger.info("Таблица llm_providers создана")

    await conn.execute(SQL_CREATE_EMBEDDING_PROVIDERS)
    logger.info("Таблица embedding_providers создана")


async def _create_app_tables(conn: asyncpg.Connection) -> None:
    """Создать таблицы приложения."""
    await conn.execute(SQL_CREATE_APP_SETTINGS)
    logger.info("Таблица app_settings создана")

    # ✨ НОВОЕ: Таблица chat_summaries
    await conn.execute(SQL_CREATE_CHAT_SUMMARIES)
    logger.info("Таблица chat_summaries создана")

    # Создаём индексы для chat_summaries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_summaries_chat_id
            ON chat_summaries (chat_id)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_summaries_created_at
            ON chat_summaries (created_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_summaries_period
            ON chat_summaries (chat_id, period_start, period_end)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_summaries_params_hash
            ON chat_summaries (params_hash)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_summaries_status
            ON chat_summaries (status)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_summaries_status_created
            ON chat_summaries (status, created_at)
    """)
    logger.info("Индексы для chat_summaries созданы")


async def _create_rate_limiter_tables(conn: asyncpg.Connection) -> None:
    """Создать таблицы Rate Limiter."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS request_statistics (
            id SERIAL PRIMARY KEY,
            method_name VARCHAR(100) NOT NULL,
            chat_id BIGINT,
            priority INTEGER NOT NULL DEFAULT 2,
            execution_time_ms INTEGER,
            is_success BOOLEAN NOT NULL DEFAULT TRUE,
            error_message TEXT,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("Таблица request_statistics создана")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS flood_wait_incidents (
            id SERIAL PRIMARY KEY,
            method_name VARCHAR(100) NOT NULL,
            chat_id BIGINT,
            error_seconds INTEGER NOT NULL,
            actual_wait_seconds INTEGER NOT NULL,
            batch_size_before INTEGER,
            batch_size_after INTEGER,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("Таблица flood_wait_incidents создана")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_request_statistics_created
        ON request_statistics(created_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_request_statistics_method
        ON request_statistics(method_name)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_request_statistics_success
        ON request_statistics(is_success)
    """)
    logger.info("Индексы для request_statistics созданы")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_flood_wait_incidents_created
        ON flood_wait_incidents(created_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_flood_wait_incidents_method
        ON flood_wait_incidents(method_name)
    """)
    logger.info("Индексы для flood_wait_incidents созданы")


async def _create_reindex_tables(conn: asyncpg.Connection) -> None:
    """Создать таблицы переиндексации."""
    await conn.execute(SQL_CREATE_REINDEX_SETTINGS)
    logger.info("Таблица reindex_settings создана")

    await conn.execute("""
        INSERT INTO reindex_settings (
            id, batch_size, delay_between_batches,
            auto_reindex_on_model_change, auto_reindex_new_messages,
            speed_mode, current_batch_size
        ) VALUES (1, 50, 1.0, TRUE, TRUE, 'medium', 50)
        ON CONFLICT (id) DO NOTHING
    """)
    logger.info("Запись reindex_settings инициализирована")

    await conn.execute(SQL_CREATE_REINDEX_TASKS)
    logger.info("Таблица reindex_tasks создана")


async def _create_indices(conn: asyncpg.Connection) -> None:
    """Создать индексы."""
    await conn.execute("SET maintenance_work_mem = '256MB'")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_embedding
        ON messages USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 128)
    """)
    logger.info("Индекс idx_embedding (HNSW) создан")

    await conn.execute("RESET maintenance_work_mem")
    await conn.execute("SET hnsw.ef_search = 64")
    logger.info("Параметр hnsw.ef_search установлен в 64")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_message_date
        ON messages (message_date DESC)
    """)
    logger.info("Индекс idx_message_date создан")

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_id
        ON messages (chat_id)
    """)
    logger.info("Индекс idx_chat_id создан")


async def check_db_health() -> bool:
    """
    Проверка подключения к БД.
    
    Returns:
        True если подключение успешно, False в случае ошибки.
    """
    try:
        async with get_db() as conn:
            await conn.fetchval("SELECT 1")
        logger.debug("Подключение к БД успешно")
        return True
    except Exception:
        # Broad exception acceptable for health check — we want to catch all errors
        logger.error("DB connection failed", exc_info=True)
        return False


async def reset_pool() -> None:
    """Сбросить пул подключений (для переподключения)."""
    await close_pool()
    await get_pool()
