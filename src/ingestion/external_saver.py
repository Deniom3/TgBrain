"""
Ingestion — сервис для сохранения внешних сообщений.

Оптимизированная проверка дубликатов (перед векторизацией).
Приоритет последнему сообщению (UPDATE при изменении текста).
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import asyncpg

from ..models.sql.external_messages import (
    SQL_CHECK_CHAT_MONITORED,
    SQL_CHECK_DUPLICATE,
    SQL_UPSERT_EXTERNAL_MESSAGE,
    SQL_UPSERT_CHAT_SETTINGS,
)
from .filters import should_process_message
from .saver import IMessageSaver

logger = logging.getLogger(__name__)


@dataclass
class SaveStatus:
    """Статус обработки сообщения."""

    status: str  # processed, pending, filtered, duplicate, updated, error
    filtered: bool = False
    pending: bool = False
    duplicate: bool = False
    updated: bool = False


@dataclass
class SaveResult:
    """Результат сохранения внешнего сообщения."""

    success: bool
    status: SaveStatus
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    reason: Optional[str] = None


@dataclass
class DuplicateCheck:
    """Результат проверки дубликата."""

    is_duplicate: bool
    needs_update: bool
    message_id: Optional[int]


class ExternalMessageSaver:
    """
    Сервис для обработки внешних сообщений.

    Алгоритм:
    1. Проверка мониторинга чата (EXT-002 = 400 если не мониторится)
    2. Проверка дубликатов (перед векторизацией — оптимизация)
    3. Фильтрация (реклама, боты, короткие)
    4. Векторизация (если не дубликат и не отфильтровано)
    5. Сохранение в БД (UPSERT с приоритетом последнему)
    6. Сохранение в pending при ошибках (embedding/DB)

    Безопасность:
    - Параметризованные SQL запросы (защита от SQL injection)
    - Валидация chat_id против БД
    - Санитизация входных данных (sender_name, text)
    - Лимиты на размер текста (защита от DoS)
    """

    TEXT_MAX_LENGTH = 4096
    DUPLICATE_WINDOW_SECONDS = 60
    SENDER_NAME_MAX_LENGTH = 100
    EXTERNAL_CHAT_TITLE_PREFIX = "External Chat"
    EXTERNAL_CHAT_TYPE = "external"

    def __init__(self, pool: asyncpg.Pool, message_saver: IMessageSaver):
        self.pool = pool
        self.saver = message_saver  # Теперь интерфейс, не конкретный класс

    async def save_external_message(
        self,
        chat_id: int,
        text: str,
        date: datetime,
        sender_id: Optional[int] = None,
        sender_name: Optional[str] = None,
        message_link: Optional[str] = None,
        is_bot: bool = False,
        is_action: bool = False,
    ) -> SaveResult:
        """
        Сохранение внешнего сообщения.

        Args:
            chat_id: ID чата в Telegram.
            text: Текст сообщения.
            date: Дата отправки.
            sender_id: ID отправителя (опционально).
            sender_name: Имя отправителя (опционально).
            message_link: Ссылка на сообщение (опционально).
            is_bot: Отправлено ботом.
            is_action: Системное сообщение.

        Returns:
            SaveResult с результатом обработки.
        """
        # Санитизация входных данных
        text = self._sanitize_text(text)
        sender_name = self._sanitize_sender_name(sender_name)

        async with self.pool.acquire() as conn:
            # 1. Проверка мониторинга чата
            is_monitored = await self._ensure_chat_monitored(conn, chat_id)
            if not is_monitored:
                logger.warning(
                    "External message rejected: chat_id=%d not monitored",
                    chat_id,
                )
                return SaveResult(
                    success=False,
                    status=SaveStatus(status="error"),
                    chat_id=chat_id,
                    reason="Chat not monitored",
                )

            # 2. Проверка дубликатов (оптимизация: ДО векторизации)
            duplicate_check = await self._check_duplicate(conn, chat_id, text, date)
            if duplicate_check.is_duplicate:
                logger.debug(
                    "External message duplicate: chat_id=%d, text matches",
                    chat_id,
                )
                return SaveResult(
                    success=True,
                    status=SaveStatus(status="duplicate", duplicate=True),
                    message_id=duplicate_check.message_id,
                    chat_id=chat_id,
                )
            elif duplicate_check.needs_update:
                # Текст изменён — нужна векторизация и UPDATE
                if duplicate_check.message_id is None:
                    # Не должно произойти, но для безопасности
                    logger.error("Unexpected: needs_update=True but message_id=None")
                    return SaveResult(
                        success=False,
                        status=SaveStatus(status="error"),
                        chat_id=chat_id,
                        reason="Internal error",
                    )

                try:
                    embedding = await self.saver.embeddings.get_embedding(text)
                except Exception as e:
                    # API boundary: wide exception catch for ingestion resilience — errors are logged and saved to pending for retry
                    logger.warning(
                        "External message embedding error (update): chat_id=%d, error_type=%s",
                        chat_id,
                        type(e).__name__,
                    )
                    await self._save_to_pending(
                        conn,
                        chat_id,
                        text,
                        date,
                        sender_id,
                        sender_name,
                        message_link,
                        is_bot,
                        is_action,
                        str(e),
                    )
                    return SaveResult(
                        success=True,
                        status=SaveStatus(status="pending", pending=True),
                        chat_id=chat_id,
                        reason="Embedding error",
                    )

                await self._update_message(
                    conn,
                    duplicate_check.message_id,
                    text,
                    embedding,
                )
                logger.info(
                    "External message updated: chat_id=%d, message_id=%d",
                    chat_id,
                    duplicate_check.message_id,
                )
                return SaveResult(
                    success=True,
                    status=SaveStatus(status="updated", updated=True),
                    message_id=duplicate_check.message_id,
                    chat_id=chat_id,
                )

            # 3. Фильтрация
            should_process, reason = should_process_message(text, is_bot, is_action)
            if not should_process:
                logger.debug(
                    "External message filtered: chat_id=%d, reason=%s",
                    chat_id,
                    reason,
                )
                return SaveResult(
                    success=True,
                    status=SaveStatus(status="filtered", filtered=True),
                    chat_id=chat_id,
                    reason=reason,
                )

            # 4. Векторизация
            try:
                embedding = await self.saver.embeddings.get_embedding(text)
            except ConnectionError as e:
                # Сервис эмбеддингов недоступен (EXT-007)
                logger.warning(
                    "External message embedding unavailable: chat_id=%d, error_type=%s",
                    chat_id,
                    type(e).__name__,
                )
                # Сохранение в pending
                await self._save_to_pending(
                    conn,
                    chat_id,
                    text,
                    date,
                    sender_id,
                    sender_name,
                    message_link,
                    is_bot,
                    is_action,
                    str(e),
                )
                return SaveResult(
                    success=True,
                    status=SaveStatus(status="pending", pending=True),
                    chat_id=chat_id,
                    reason="Embedding unavailable",
                )
            except Exception as e:
                # API boundary: wide exception catch for ingestion resilience — errors are logged and saved to pending for retry
                logger.warning(
                    "External message embedding error: chat_id=%d, error_type=%s",
                    chat_id,
                    type(e).__name__,
                )
                # Сохранение в pending
                await self._save_to_pending(
                    conn,
                    chat_id,
                    text,
                    date,
                    sender_id,
                    sender_name,
                    message_link,
                    is_bot,
                    is_action,
                    str(e),
                )
                return SaveResult(
                    success=True,
                    status=SaveStatus(status="pending", pending=True),
                    chat_id=chat_id,
                    reason="Embedding error",
                )

            # 5. Сохранение в БД
            try:
                message_id = await self._save_to_db(
                    conn,
                    chat_id,
                    text,
                    date,
                    sender_id,
                    sender_name,
                    message_link,
                    embedding,
                )
                logger.info(
                    "External message processed: chat_id=%d, message_id=%d",
                    chat_id,
                    message_id,
                )
                return SaveResult(
                    success=True,
                    status=SaveStatus(status="processed"),
                    message_id=message_id,
                    chat_id=chat_id,
                )
            except Exception as e:
                # API boundary: wide exception catch for ingestion resilience — errors are logged and saved to pending for retry
                logger.error(
                    "External message DB error: chat_id=%d, error_type=%s",
                    chat_id,
                    type(e).__name__,
                )
                # Сохранение в pending
                await self._save_to_pending(
                    conn,
                    chat_id,
                    text,
                    date,
                    sender_id,
                    sender_name,
                    message_link,
                    is_bot,
                    is_action,
                    f"DB error: {e}",
                )
                return SaveResult(
                    success=True,
                    status=SaveStatus(status="pending", pending=True),
                    chat_id=chat_id,
                    reason="Database error",
                )

    def _sanitize_text(self, text: str) -> str:
        """Санитизация текста сообщения."""
        # Обрезка до максимального размера
        if len(text) > self.TEXT_MAX_LENGTH:
            text = text[: self.TEXT_MAX_LENGTH]
        # Удаление control characters (кроме newline/tab)
        text = "".join(char for char in text if char.isprintable() or char in "\n\t\r")
        return text.strip()

    def _sanitize_sender_name(self, sender_name: Optional[str]) -> Optional[str]:
        """Санитизация имени отправителя (XSS protection)."""
        if sender_name is None:
            return None
        # HTML-экранирование специальных символов
        sender_name = sender_name.replace("&", "&amp;")
        sender_name = sender_name.replace("<", "&lt;")
        sender_name = sender_name.replace(">", "&gt;")
        sender_name = sender_name.replace('"', "&quot;")
        sender_name = sender_name.replace("'", "&#x27;")
        # Обрезка до разумного размера
        if len(sender_name) > 256:
            sender_name = sender_name[:256]
        return sender_name.strip()

    async def _ensure_chat_monitored(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
    ) -> bool:
        """
        Проверка мониторинга чата с авто-созданием при отсутствии.

        Если чат найден и is_monitored=TRUE — разрешает обработку.
        Если чат найден и is_monitored=FALSE — отклоняет.
        Если чат не найден — создаёт запись с is_monitored=TRUE.

        Args:
            conn: Соединение с БД.
            chat_id: ID чата.

        Returns:
            True если чат мониторится (существует или создан).
        """
        row = await conn.fetchrow(
            SQL_CHECK_CHAT_MONITORED,
            chat_id,
        )
        if row is not None:
            return bool(row["is_monitored"])

        logger.info(
            "External chat not found in settings, auto-creating: chat_id=%d",
            chat_id,
        )
        await conn.execute(
            SQL_UPSERT_CHAT_SETTINGS,
            chat_id,
            f"{self.EXTERNAL_CHAT_TITLE_PREFIX} {chat_id}",
            self.EXTERNAL_CHAT_TYPE,
        )
        return True

    async def _check_duplicate(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        text: str,
        date: datetime,
    ) -> DuplicateCheck:
        """
        Проверка дубликата.

        Args:
            conn: Соединение с БД.
            chat_id: ID чата.
            text: Текст сообщения.
            date: Дата сообщения.

        Returns:
            DuplicateCheck с результатом проверки.
        """
        # Проверка по (chat_id, text, date ±60sec)
        row = await conn.fetchrow(
            SQL_CHECK_DUPLICATE,
            chat_id,
            text,
            date,
            self.DUPLICATE_WINDOW_SECONDS,
        )

        if row:
            existing_text = row["message_text"]
            if existing_text == text:
                return DuplicateCheck(is_duplicate=True, needs_update=False, message_id=row["id"])
            else:
                return DuplicateCheck(is_duplicate=False, needs_update=True, message_id=row["id"])

        return DuplicateCheck(is_duplicate=False, needs_update=False, message_id=None)

    async def _save_to_db(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        text: str,
        date: datetime,
        sender_id: Optional[int],
        sender_name: Optional[str],
        message_link: Optional[str],
        embedding: list[float],
    ) -> int:
        """
        Сохранение в БД.

        Args:
            conn: Соединение с БД.
            chat_id: ID чата.
            text: Текст сообщения.
            date: Дата сообщения.
            sender_id: ID отправителя.
            sender_name: Имя отправителя.
            message_link: Ссылка на сообщение.
            embedding: Вектор эмбеддинга.

        Returns:
            ID сохранённого сообщения.
        """
        # Генерация ID для внешнего сообщения (хеш)
        message_id = self._generate_message_id(chat_id, text, date)

        embedding_model = self.saver.embeddings.get_model_name()

        # UPSERT
        row = await conn.fetchrow(
            SQL_UPSERT_EXTERNAL_MESSAGE,
            message_id,
            chat_id,
            sender_id,
            sender_name,
            text,
            date,
            message_link,
            embedding,
            embedding_model,
            True,
        )

        return row["id"]

    async def _save_to_pending(
        self,
        conn: asyncpg.Connection,
        chat_id: int,
        text: str,
        date: datetime,
        sender_id: Optional[int],
        sender_name: Optional[str],
        message_link: Optional[str],
        is_bot: bool,
        is_action: bool,
        error: str,
    ) -> None:
        """
        Сохранение в pending_messages.

        Args:
            conn: Соединение с БД.
            chat_id: ID чата.
            text: Текст сообщения.
            date: Дата сообщения.
            sender_id: ID отправителя.
            sender_name: Имя отправителя.
            message_link: Ссылка на сообщение.
            is_bot: Отправлено ботом.
            is_action: Системное сообщение.
            error: Описание ошибки.
        """
        message_data = {
            "chat_id": chat_id,
            "text": text,
            "date": date.isoformat(),
            "sender_id": sender_id,
            "sender_name": sender_name,
            "message_link": message_link,
            "is_bot": is_bot,
            "is_action": is_action,
            "source": "external",
        }

        await conn.execute(
            """
            INSERT INTO pending_messages (message_data, retry_count, last_error)
            VALUES ($1::JSONB, 0, $2)
            """,
            json.dumps(message_data),
            error,
        )

    async def _update_message(
        self,
        conn: asyncpg.Connection,
        message_id: int,
        text: str,
        embedding: list[float],
    ) -> None:
        """
        Обновление сообщения.

        Args:
            conn: Соединение с БД.
            message_id: ID сообщения.
            text: Новый текст.
            embedding: Новый вектор эмбеддинга.
        """
        embedding_model = self.saver.embeddings.get_model_name()

        await conn.execute(
            """
            UPDATE messages SET
                message_text = $2,
                embedding = $3::VECTOR,
                embedding_model = $4,
                updated_at = NOW()
            WHERE id = $1
            """,
            message_id,
            text,
            embedding,
            embedding_model,
        )

    @staticmethod
    def _generate_message_id(chat_id: int, text: str, date: datetime) -> int:
        """
        Генерация уникального ID для внешнего сообщения.

        Args:
            chat_id: ID чата.
            text: Текст сообщения.
            date: Дата сообщения.

        Returns:
            Уникальный ID (15-значное число).
        """
        # Нормализация даты до UTC
        if date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        hash_input = f"{chat_id}:{text}:{date.isoformat()}"
        return int(hashlib.sha256(hash_input.encode()).hexdigest()[:15], 16)
