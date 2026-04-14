"""
ContextExpander — Сервис расширения контекста и группировки сообщений.

Расширяет короткие сообщения соседними (±2) и группирует последовательные
сообщения от одного пользователя (окно 5 минут).

Размерность эмбеддинга загружается из БД (таблица embedding_providers)
после явного вызова метода initialize().

Пример использования:
    expander = ContextExpander(db_pool)
    await expander.initialize()  # ✨ Явный вызов
    expanded = await expander.expand_with_neighbors(message_id=123, chat_id=456, sender_id=789)
    groups = await expander.group_consecutive_messages(chat_id=456, messages=expanded)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from asyncpg import Pool

from src.domain.value_objects import MessageText, SenderName, ChatTitle
from src.models.data_models import MessageGroup, MessageRecord
from src.models.sql import SQL_GET_MESSAGE_BY_ID, SQL_GET_MESSAGE_NEIGHBORS
from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

logger = logging.getLogger(__name__)

# =============================================================================
# Константы
# =============================================================================

ANONYMOUS_SENDER: str = "Аноним"
"""Имя отправителя по умолчанию."""

UNKNOWN_CHAT: str = "Unknown"
"""Название чата по умолчанию."""


# Константы
DEFAULT_CONTEXT_WINDOW = 2
DEFAULT_GROUPING_WINDOW_MINUTES = 5
MIN_MESSAGE_LENGTH_FOR_GROUPING = 15
MAX_GROUP_SIZE = 10


@dataclass
class ExpandConfig:
    """Конфигурация расширения контекста.
    
    Attributes:
        before: Количество соседей до сообщения (по умолчанию: 2)
        after: Количество соседей после сообщения (по умолчанию: 2)
        auto_expand_short: Автоматически расширять короткие сообщения (по умолчанию: True)
        short_message_threshold: Порог длины сообщения для авто-расширения (по умолчанию: 15)
        embedding_dim: Размерность вектора эмбеддинга (определяется из БД)
    """

    before: int = DEFAULT_CONTEXT_WINDOW
    after: int = DEFAULT_CONTEXT_WINDOW
    auto_expand_short: bool = True
    short_message_threshold: int = MIN_MESSAGE_LENGTH_FOR_GROUPING
    embedding_dim: int = 768  # Будет переопределено из БД при инициализации


@dataclass
class GroupConfig:
    """Конфигурация группировки сообщений.
    
    Attributes:
        window_minutes: Временное окно для группировки в минутах (по умолчанию: 5)
        same_sender_only: Группировать только сообщения одного отправителя (по умолчанию: True)
        max_group_size: Максимальный размер группы (по умолчанию: 10)
    """

    window_minutes: int = DEFAULT_GROUPING_WINDOW_MINUTES
    same_sender_only: bool = True
    max_group_size: int = MAX_GROUP_SIZE


class ContextExpander:
    """
    Сервис расширения контекста и группировки сообщений.

    Расширяет короткие сообщения соседними и группирует последовательные
    сообщения от одного пользователя в сессии.

    Размерность эмбеддинга загружается из БД при вызове метода initialize().
    До вызова initialize() используется значение по умолчанию (768).

    Пример использования:
        expander = ContextExpander(db_pool)
        await expander.initialize()  # ✨ Загрузить embedding_dim из БД

        if expander.is_initialized:
            # Использовать expander
        else:
            # Обработать ошибку инициализации

    Attributes:
        db_pool: Пул подключений к PostgreSQL
        config: Конфигурация расширения (с размерностью из БД после initialize())
        group_config: Конфигурация группировки
        _initialized: Флаг успешной инициализации
        _embedding_repo: Репозиторий провайдеров эмбеддингов

    Properties:
        is_initialized: Проверка успешной инициализации
    """

    def __init__(
        self,
        db_pool: Pool,
        config: Optional[ExpandConfig] = None,
        group_config: Optional[GroupConfig] = None,
        embedding_repo: Optional[EmbeddingProvidersRepository] = None,
    ):
        """
        Инициализация ContextExpander.

        Args:
            db_pool: Пул подключений к PostgreSQL
            config: Конфигурация расширения (по умолчанию создаётся новый)
            group_config: Конфигурация группировки (по умолчанию создаётся новая)
            embedding_repo: Репозиторий провайдеров эмбеддингов (по умолчанию создаётся новый)
        """
        self.db_pool = db_pool
        self.config = config or ExpandConfig()
        self.group_config = group_config or GroupConfig()
        self._embedding_repo = embedding_repo
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """
        Проверка успешной инициализации.

        Returns:
            True если initialize() был успешно выполнен,
            False если инициализация ещё не проводилась или завершилась ошибкой.
        """
        return self._initialized

    async def initialize(self) -> bool:
        """
        Инициализация размерности эмбеддинга из БД.

        Загружает размерность из таблицы embedding_providers
        для активного провайдера и обновляет конфигурацию.

        Returns:
            True если размерность успешно загружена из БД,
            False если использовано значение по умолчанию или произошла ошибка

        Raises:
            ConnectionError: Если БД недоступна
        """
        # ✨ Защита от повторной инициализации
        if self._initialized:
            logger.debug("ContextExpander уже инициализирован")
            return True

        try:
            # ✨ Создаём репозиторий если не был передан
            if self._embedding_repo is None:
                self._embedding_repo = EmbeddingProvidersRepository(self.db_pool)
            
            active_provider = await self._embedding_repo.get_active()
            if active_provider:
                self.config.embedding_dim = active_provider.embedding_dim
                logger.info(
                    f"Размерность эмбеддинга загружена из БД: "
                    f"dim={active_provider.embedding_dim}, provider={active_provider.name}, "
                    f"model={active_provider.model}"
                )
                self._initialized = True
                return True  # ✨ Успех
            else:
                logger.warning(
                    "Активный провайдер эмбеддингов не найден в БД. "
                    f"Используем размерность по умолчанию: {self.config.embedding_dim}"
                )
                self._initialized = True
                return False  # ✨ Не найдено (повторная попытка не нужна)
        except Exception as e:
            logger.error(f"Ошибка загрузки размерности эмбеддинга из БД: {e}", exc_info=True)
            logger.warning(
                f"Используем размерность по умолчанию: {self.config.embedding_dim}"
            )
            # ❌ Флаг НЕ устанавливается — позволяет повторную попытку инициализации
            return False  # ✨ Ошибка (возможна повторная попытка)

    async def expand_with_neighbors(
        self,
        message_id: int,
        chat_id: int,
        sender_id: int,
        query_embedding: Optional[List[float]] = None,
        before: Optional[int] = None,
        after: Optional[int] = None,
    ) -> List[MessageRecord]:
        """
        Расширение контекста сообщения соседними сообщениями.

        Получает ±N соседних сообщений от того же пользователя для
        расширения контекста коротких сообщений.

        Args:
            message_id: ID сообщения для расширения
            chat_id: ID чата
            sender_id: ID отправителя
            query_embedding: Вектор запроса для расчёта similarity (опционально)
            before: Количество соседей до (по умолчанию: config.before)
            after: Количество соседей после (по умолчанию: config.after)

        Returns:
            Список соседних сообщений (до + после), отсортированных по дате

        Raises:
            ValueError: Если message_id, chat_id или sender_id некорректны
            ConnectionError: Если БД недоступна
        """
        if message_id <= 0 or chat_id <= 0 or sender_id <= 0:
            raise ValueError(
                f"Некорректные ID: message_id={message_id}, chat_id={chat_id}, sender_id={sender_id}"
            )

        before_count = before if before is not None else self.config.before
        after_count = after if after is not None else self.config.after

        if before_count < 0 or after_count < 0:
            raise ValueError("before и after должны быть неотрицательными")

        logger.info(
            f"Расширение контекста для message_id={message_id}, chat_id={chat_id}, "
            f"before={before_count}, after={after_count}"
        )

        try:
            async with self.db_pool.acquire() as conn:
                center_message = await self._get_message_by_id(conn, message_id, chat_id)
                if not center_message:
                    logger.warning(f"Сообщение {message_id} не найдено в чате {chat_id}")
                    return []

                # ✨ AUTO-EXPAND для коротких сообщений
                text_length = len(str(center_message.text))
                if self.config.auto_expand_short and text_length < self.config.short_message_threshold:
                    logger.info(
                        f"Сообщение короткое ({text_length} < {self.config.short_message_threshold}), "
                        f"авто-расширение контекста"
                    )
                    before_count = max(before_count, 5)
                    after_count = max(after_count, 5)

                before_date = center_message.date - timedelta(minutes=30)
                after_date = center_message.date + timedelta(minutes=30)

                neighbors = await conn.fetch(
                    SQL_GET_MESSAGE_NEIGHBORS,
                    chat_id,
                    sender_id,
                    before_date,
                    query_embedding or [0.0] * self.config.embedding_dim,
                    after_date,
                    message_id,
                    before_count + after_count,
                )

                result = [self._row_to_message_record(row) for row in neighbors]

                logger.info(f"Найдено {len(result)} соседних сообщений")
                return result

        except Exception as e:
            logger.error(f"Ошибка расширения контекста: {e}", exc_info=True)
            raise

    async def group_consecutive_messages(
        self,
        chat_id: int,
        messages: List[MessageRecord],
        window_minutes: Optional[int] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[MessageGroup]:
        """
        Группировка последовательных сообщений от одного пользователя.

        Объединяет сообщения от одного sender_id с интервалом ≤ window_minutes
        в группы для формирования связного контекста.

        Args:
            chat_id: ID чата
            messages: Сообщения для группировки
            window_minutes: Временное окно в минутах (по умолчанию: config.window_minutes)
            query_embedding: Вектор для расчёта similarity (опционально)

        Returns:
            Список групп сообщений, отсортированных по дате начала

        Example:
            groups = await expander.group_consecutive_messages(
                chat_id=123,
                messages=found_messages,
                window_minutes=5
            )
        """
        window = window_minutes or self.group_config.window_minutes

        logger.info(f"Группировка сообщений в чате {chat_id}, окно={window} мин")

        if not messages:
            return []

        sender_messages: Dict[int, List[MessageRecord]] = {}
        for msg in messages:
            if msg.sender_id not in sender_messages:
                sender_messages[msg.sender_id] = []
            sender_messages[msg.sender_id].append(msg)

        groups: List[MessageGroup] = []

        for sender_id, sender_msgs in sender_messages.items():
            sorted_msgs = sorted(sender_msgs, key=lambda m: m.date)
            sessions = self._split_into_sessions(sorted_msgs, window)

            for session in sessions:
                if len(session) >= 2:
                    group = self._create_group(chat_id, sender_id, session)
                    groups.append(group)
                else:
                    logger.debug(f"Сообщение от {sender_id} не сгруппировано (одиночное)")

        logger.info(f"Сформировано {len(groups)} групп сообщений")
        return groups

    def _split_into_sessions(
        self,
        messages: List[MessageRecord],
        window_minutes: int,
    ) -> List[List[MessageRecord]]:
        """
        Разбиение сообщений на сессии по временному окну.

        Args:
            messages: Отсортированные по дате сообщения
            window_minutes: Максимальный интервал между сообщениями в сессии

        Returns:
            Список сессий (групп сообщений)
        """
        if not messages:
            return []

        sessions: List[List[MessageRecord]] = []
        current_session: List[MessageRecord] = [messages[0]]

        for i in range(1, len(messages)):
            prev_msg = messages[i - 1]
            curr_msg = messages[i]

            time_diff = (curr_msg.date - prev_msg.date).total_seconds() / 60

            if time_diff <= window_minutes:
                current_session.append(curr_msg)
            else:
                if current_session:
                    sessions.append(current_session)
                current_session = [curr_msg]

        if current_session:
            sessions.append(current_session)

        return sessions

    def _create_group(
        self,
        chat_id: int,
        sender_id: int,
        messages: List[MessageRecord],
    ) -> MessageGroup:
        """
        Создание группы сообщений.

        Args:
            chat_id: ID чата
            sender_id: ID отправителя
            messages: Сообщения в группе

        Returns:
            MessageGroup с объединённым текстом и средним score
        """
        if len(messages) > self.group_config.max_group_size:
            logger.warning(
                f"Группа из {len(messages)} сообщений обрезана до "
                f"{self.group_config.max_group_size} (sender_id={sender_id}, chat_id={chat_id})"
            )
            messages = messages[: self.group_config.max_group_size]

        merged_text = "\n".join([str(msg.text) for msg in messages])
        avg_score = sum(msg.similarity_score for msg in messages) / len(messages)

        return MessageGroup(
            sender_id=sender_id,
            sender_name=str(messages[0].sender_name),
            chat_id=chat_id,
            chat_title=str(messages[0].chat_title),
            messages=messages,
            start_date=messages[0].date,
            end_date=messages[-1].date,
            merged_text=merged_text,
            similarity_score=avg_score,
        )

    async def _get_message_by_id(
        self,
        conn: Any,
        message_id: int,
        chat_id: int,
    ) -> Optional[MessageRecord]:
        """
        Получение сообщения по ID.

        Args:
            conn: Подключение к БД
            message_id: ID сообщения
            chat_id: ID чата

        Returns:
            MessageRecord или None если не найдено
        """
        row = await conn.fetchrow(
            SQL_GET_MESSAGE_BY_ID,
            message_id,
            chat_id,
        )

        if not row:
            return None

        return MessageRecord(
            id=row["id"],
            text=MessageText(row["message_text"] or ""),
            date=row["message_date"],
            chat_title=ChatTitle(row["chat_title"] or UNKNOWN_CHAT),
            link=row["message_link"] or "",
            sender_name=SenderName(row["sender_name"] or ANONYMOUS_SENDER),
            sender_id=row["sender_id"] or 0,
        )

    def _row_to_message_record(self, row: Any) -> MessageRecord:
        """Конвертация строки БД в MessageRecord."""
        return MessageRecord(
            id=row["id"],
            text=MessageText(row["message_text"] or ""),
            date=row["message_date"],
            chat_title=ChatTitle(row["chat_title"] or UNKNOWN_CHAT),
            link=row["message_link"] or "",
            sender_name=SenderName(row["sender_name"] or ANONYMOUS_SENDER),
            sender_id=row["sender_id"] or 0,
            similarity_score=float(row["similarity_score"]) if row["similarity_score"] else 0.0,
        )
