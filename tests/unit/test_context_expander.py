"""
Модульные тесты для ContextExpander.

Проверяют расширение контекста соседними сообщениями,
группировку последовательных сообщений и разбиение на сессии.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.domain.value_objects import MessageText, SenderName, ChatTitle
from src.models.data_models import MessageRecord, MessageGroup
from src.models.sql.messages import SQL_GET_MESSAGE_BY_ID, SQL_GET_MESSAGE_NEIGHBORS
from src.rag.context_expander import (
    ContextExpander,
    ExpandConfig,
    GroupConfig,
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_GROUPING_WINDOW_MINUTES,
)


# =============================================================================
# TestContextExpanderInit — Тесты инициализации
# =============================================================================


class TestContextExpanderInit:
    """Тесты инициализации ContextExpander."""

    def test_context_expander_default_initialization(self, mock_db_pool):
        """
        Проверка инициализации с конфигурацией по умолчанию.

        Ожидание:
        - Создаётся экземпляр с config по умолчанию
        - embedding_dim = 768 (значение по умолчанию)
        - is_initialized = False (до вызова initialize())
        """
        expander = ContextExpander(mock_db_pool)

        assert expander.db_pool == mock_db_pool
        assert expander.config.embedding_dim == 768
        assert expander.config.before == DEFAULT_CONTEXT_WINDOW
        assert expander.config.after == DEFAULT_CONTEXT_WINDOW
        assert expander.group_config.window_minutes == DEFAULT_GROUPING_WINDOW_MINUTES
        assert expander.is_initialized is False

    def test_context_expander_custom_config(self, mock_db_pool):
        """
        Проверка инициализации с кастомной конфигурацией.

        Ожидание:
        - Применяются переданные параметры конфигурации
        - before=3, after=4, embedding_dim=1024
        - window_minutes=10, max_group_size=15
        """
        config = ExpandConfig(
            before=3,
            after=4,
            embedding_dim=1024,
        )
        group_config = GroupConfig(
            window_minutes=10,
            max_group_size=15,
        )

        expander = ContextExpander(
            mock_db_pool,
            config=config,
            group_config=group_config,
        )

        assert expander.config.before == 3
        assert expander.config.after == 4
        assert expander.config.embedding_dim == 1024
        assert expander.group_config.window_minutes == 10
        assert expander.group_config.max_group_size == 15


# =============================================================================
# TestExpandWithNeighbors — Тесты расширения контекста
# =============================================================================


class TestExpandWithNeighbors:
    """Тесты метода expand_with_neighbors."""

    @pytest.mark.asyncio
    async def test_expand_with_neighbors_success(self, mock_db_pool):
        """
        Проверка успешного расширения контекста.

        Ожидание:
        - Вызывается SQL_GET_MESSAGE_NEIGHBORS
        - Возвращаются соседние сообщения
        - Сообщения сортируются по дате
        """
        from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        center_row = {
            "id": 100,
            "message_text": "Центральное сообщение",
            "message_date": base_time,
            "chat_title": "Test Chat",
            "message_link": "https://t.me/test/100",
            "sender_name": "Test User",
            "sender_id": 123,
        }

        neighbor_rows = [
            {
                "id": 98,
                "message_text": "Сообщение до",
                "message_date": base_time - timedelta(minutes=5),
                "chat_title": "Test Chat",
                "message_link": "https://t.me/test/98",
                "sender_name": "Test User",
                "sender_id": 123,
                "similarity_score": 0.85,
            },
            {
                "id": 102,
                "message_text": "Сообщение после",
                "message_date": base_time + timedelta(minutes=3),
                "chat_title": "Test Chat",
                "message_link": "https://t.me/test/102",
                "sender_name": "Test User",
                "sender_id": 123,
                "similarity_score": 0.90,
            },
        ]

        connection = mock_db_pool.acquire.return_value.__aenter__.return_value
        connection.fetchrow = AsyncMock(return_value=center_row)
        connection.fetch = AsyncMock(return_value=neighbor_rows)

        mock_repo = MagicMock(spec=EmbeddingProvidersRepository)
        mock_provider = MagicMock()
        mock_provider.embedding_dim = 768
        mock_provider.name = "ollama"
        mock_provider.model = "nomic-embed-text"
        mock_repo.get_active = AsyncMock(return_value=mock_provider)

        expander = ContextExpander(mock_db_pool, embedding_repo=mock_repo)
        await expander.initialize()

        result = await expander.expand_with_neighbors(
            message_id=100,
            chat_id=456,
            sender_id=123,
            before=2,
            after=2,
        )

        assert len(result) == 2
        assert result[0].id == 98
        assert result[1].id == 102
        assert result[0].similarity_score == 0.85
        assert result[1].similarity_score == 0.90

        connection.fetchrow.assert_called_once_with(
            SQL_GET_MESSAGE_BY_ID,
            100,
            456,
        )

        connection.fetch.assert_called_once()
        call_args = connection.fetch.call_args[0]
        assert call_args[0] == SQL_GET_MESSAGE_NEIGHBORS

    @pytest.mark.asyncio
    async def test_expand_with_neighbors_message_not_found(self, mock_db_pool):
        """
        Проверка случая, когда центральное сообщение не найдено.

        Ожидание:
        - fetchrow возвращает None
        - Возвращается пустой список
        - Логирование предупреждения
        """
        from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

        connection = mock_db_pool.acquire.return_value.__aenter__.return_value
        connection.fetchrow = AsyncMock(return_value=None)

        mock_repo = MagicMock(spec=EmbeddingProvidersRepository)
        mock_provider = MagicMock()
        mock_provider.embedding_dim = 768
        mock_repo.get_active = AsyncMock(return_value=mock_provider)

        expander = ContextExpander(mock_db_pool, embedding_repo=mock_repo)
        await expander.initialize()

        result = await expander.expand_with_neighbors(
            message_id=999,
            chat_id=456,
            sender_id=123,
        )

        assert result == []
        connection.fetchrow.assert_called_once()
        connection.fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_expand_with_neighbors_invalid_params(self, mock_db_pool):
        """
        Проверка валидации параметров.

        Ожидание:
        - ValueError при message_id <= 0
        - ValueError при chat_id <= 0
        - ValueError при sender_id <= 0
        - ValueError при before < 0 или after < 0
        """
        expander = ContextExpander(mock_db_pool)

        with pytest.raises(ValueError, match="Некорректные ID"):
            await expander.expand_with_neighbors(
                message_id=0,
                chat_id=456,
                sender_id=123,
            )

        with pytest.raises(ValueError, match="Некорректные ID"):
            await expander.expand_with_neighbors(
                message_id=100,
                chat_id=-1,
                sender_id=123,
            )

        with pytest.raises(ValueError, match="before и after должны быть неотрицательными"):
            await expander.expand_with_neighbors(
                message_id=100,
                chat_id=456,
                sender_id=123,
                before=-1,
            )


# =============================================================================
# TestGroupConsecutiveMessages — Тесты группировки сообщений
# =============================================================================


class TestGroupConsecutiveMessages:
    """Тесты метода group_consecutive_messages."""

    @pytest.mark.asyncio
    async def test_group_consecutive_messages_success(self, mock_db_pool, sample_message_records):
        """
        Проверка группировки последовательных сообщений.

        Ожидание:
        - Сообщения от одного sender_id с интервалом ≤ window_minutes группируются
        - Возвращается список MessageGroup
        - merged_text содержит объединённый текст
        """
        from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

        mock_repo = MagicMock(spec=EmbeddingProvidersRepository)
        mock_provider = MagicMock()
        mock_provider.embedding_dim = 768
        mock_repo.get_active = AsyncMock(return_value=mock_provider)

        expander = ContextExpander(mock_db_pool, embedding_repo=mock_repo)
        await expander.initialize()

        groups = await expander.group_consecutive_messages(
            chat_id=456,
            messages=sample_message_records,
            window_minutes=5,
        )

        assert len(groups) >= 1

        user_one_groups = [g for g in groups if g.sender_id == 100]
        if user_one_groups:
            group = user_one_groups[0]
            assert group.sender_id == 100
            assert group.sender_name == "User One"
            assert group.chat_id == 456
            assert len(group.messages) >= 1
            assert "Короткое сообщение 1" in group.merged_text

    @pytest.mark.asyncio
    async def test_group_consecutive_messages_empty(self, mock_db_pool):
        """
        Проверка группировки пустого списка сообщений.

        Ожидание:
        - Возвращается пустой список
        - Методы БД не вызываются
        """
        from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

        mock_repo = MagicMock(spec=EmbeddingProvidersRepository)
        mock_provider = MagicMock()
        mock_provider.embedding_dim = 768
        mock_repo.get_active = AsyncMock(return_value=mock_provider)

        expander = ContextExpander(mock_db_pool, embedding_repo=mock_repo)
        await expander.initialize()

        groups = await expander.group_consecutive_messages(
            chat_id=456,
            messages=[],
        )

        assert groups == []

    @pytest.mark.asyncio
    async def test_group_consecutive_messages_single_sender(self, mock_db_pool):
        """
        Проверка группировки сообщений от одного отправителя.

        Ожидание:
        - Все сообщения от одного sender_id группируются вместе
        - Если интервал > window_minutes, создаётся несколько групп
        """
        from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Сообщение 1"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.9,
            ),
            MessageRecord(
                id=2,
                text=MessageText("Сообщение 2"),
                date=base_time + timedelta(minutes=2),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/2",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.8,
            ),
            MessageRecord(
                id=3,
                text=MessageText("Сообщение 3"),
                date=base_time + timedelta(minutes=20),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/3",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.7,
            ),
        ]

        mock_repo = MagicMock(spec=EmbeddingProvidersRepository)
        mock_provider = MagicMock()
        mock_provider.embedding_dim = 768
        mock_repo.get_active = AsyncMock(return_value=mock_provider)

        expander = ContextExpander(mock_db_pool, embedding_repo=mock_repo)
        await expander.initialize()

        groups = await expander.group_consecutive_messages(
            chat_id=456,
            messages=messages,
            window_minutes=5,
        )

        assert len(groups) == 1

        group = groups[0]
        assert group.sender_id == 100
        assert len(group.messages) == 2
        assert group.messages[0].id == 1
        assert group.messages[1].id == 2


# =============================================================================
# TestSplitIntoSessions — Тесты разбиения на сессии
# =============================================================================


class TestSplitIntoSessions:
    """Тесты метода _split_into_sessions."""

    def test_split_into_sessions_single_session(self, mock_db_pool):
        """
        Проверка разбиения на сессии — все сообщения в одной сессии.

        Ожидание:
        - Все сообщения с интервалом ≤ window_minutes в одной сессии
        """

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Сообщение 1"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.9,
            ),
            MessageRecord(
                id=2,
                text=MessageText("Сообщение 2"),
                date=base_time + timedelta(minutes=2),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/2",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.8,
            ),
            MessageRecord(
                id=3,
                text=MessageText("Сообщение 3"),
                date=base_time + timedelta(minutes=4),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/3",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.7,
            ),
        ]

        expander = ContextExpander(mock_db_pool)

        sessions = expander._split_into_sessions(messages, window_minutes=5)

        assert len(sessions) == 1
        assert len(sessions[0]) == 3

    def test_split_into_sessions_multiple_sessions(self, mock_db_pool):
        """
        Проверка разбиения на сессии — несколько сессий.

        Ожидание:
        - Сообщения с интервалом > window_minutes разбиваются на разные сессии
        """

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Сообщение 1"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.9,
            ),
            MessageRecord(
                id=2,
                text=MessageText("Сообщение 2"),
                date=base_time + timedelta(minutes=2),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/2",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.8,
            ),
            MessageRecord(
                id=3,
                text=MessageText("Сообщение 3"),
                date=base_time + timedelta(minutes=20),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/3",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.7,
            ),
        ]

        expander = ContextExpander(mock_db_pool)

        sessions = expander._split_into_sessions(messages, window_minutes=5)

        assert len(sessions) == 2
        assert len(sessions[0]) == 2
        assert len(sessions[1]) == 1

    def test_split_into_sessions_empty(self, mock_db_pool):
        """
        Проверка разбиения пустого списка сообщений.

        Ожидание:
        - Возвращается пустой список
        """
        expander = ContextExpander(mock_db_pool)

        sessions = expander._split_into_sessions([], window_minutes=5)

        assert sessions == []


# =============================================================================
# TestMessageGroup — Тесты модели MessageGroup
# =============================================================================


class TestMessageGroup:
    """Тесты модели MessageGroup."""

    def test_message_group_creation(self):
        """
        Проверка создания MessageGroup.

        Ожидание:
        - Создаётся экземпляр с правильными полями
        - grouped_count возвращает количество сообщений
        - similarity_score в диапазоне 0.0-1.0
        """

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Сообщение 1"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.9,
            ),
            MessageRecord(
                id=2,
                text=MessageText("Сообщение 2"),
                date=base_time + timedelta(minutes=2),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/2",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.8,
            ),
        ]

        merged_text = "\n".join([str(msg.text) for msg in messages])

        group = MessageGroup(
            sender_id=100,
            sender_name="User One",
            chat_id=456,
            chat_title="Test Chat",
            messages=messages,
            start_date=base_time,
            end_date=base_time + timedelta(minutes=2),
            merged_text=merged_text,
            similarity_score=0.85,
        )

        assert group.sender_id == 100
        assert group.sender_name == "User One"
        assert group.chat_id == 456
        assert group.chat_title == "Test Chat"
        assert group.grouped_count == 2
        assert group.similarity_score == 0.85
        assert "Сообщение 1" in group.merged_text
        assert "Сообщение 2" in group.merged_text

    def test_message_group_invalid_score(self):
        """
        Проверка валидации similarity_score.

        Ожидание:
        - ValueError при similarity_score < 0.0
        - ValueError при similarity_score > 1.0
        """

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Сообщение 1"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.9,
            ),
        ]

        with pytest.raises(ValueError, match="similarity_score должен быть в диапазоне"):
            MessageGroup(
                sender_id=100,
                sender_name="User One",
                chat_id=456,
                chat_title="Test Chat",
                messages=messages,
                start_date=base_time,
                end_date=base_time,
                merged_text="Тест",
                similarity_score=-0.1,
            )

        with pytest.raises(ValueError, match="similarity_score должен быть в диапазоне"):
            MessageGroup(
                sender_id=100,
                sender_name="User One",
                chat_id=456,
                chat_title="Test Chat",
                messages=messages,
                start_date=base_time,
                end_date=base_time,
                merged_text="Тест",
                similarity_score=1.5,
            )


# =============================================================================
# TestCreateGroup — Тесты метода _create_group
# =============================================================================


class TestCreateGroup:
    """Тесты метода _create_group."""

    def test_create_group_success(self, mock_db_pool):
        """
        Проверка создания группы сообщений.

        Ожидание:
        - Создаётся MessageGroup с правильными полями
        - merged_text содержит объединённый текст
        - similarity_score — среднее значение
        """

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Сообщение 1"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.9,
            ),
            MessageRecord(
                id=2,
                text=MessageText("Сообщение 2"),
                date=base_time + timedelta(minutes=2),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/2",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.7,
            ),
        ]

        expander = ContextExpander(mock_db_pool)

        group = expander._create_group(
            chat_id=456,
            sender_id=100,
            messages=messages,
        )

        assert isinstance(group, MessageGroup)
        assert group.sender_id == 100
        assert group.chat_id == 456
        assert group.chat_title == "Test Chat"
        assert group.sender_name == "User One"
        assert len(group.messages) == 2
        assert group.similarity_score == 0.8
        assert "Сообщение 1" in group.merged_text
        assert "Сообщение 2" in group.merged_text

    def test_create_group_max_size_exceeded(self, mock_db_pool):
        """
        Проверка обрезки группы при превышении max_group_size.

        Ожидание:
        - Группа обрезается до max_group_size
        - Логирование предупреждения
        """

        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=i,
                text=MessageText(f"Сообщение {i}"),
                date=base_time + timedelta(minutes=i),
                chat_title=ChatTitle("Test Chat"),
                link=f"https://t.me/test/{i}",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.9 - (i * 0.05),
            )
            for i in range(15)
        ]

        expander = ContextExpander(
            mock_db_pool,
            group_config=GroupConfig(max_group_size=10),
        )

        group = expander._create_group(
            chat_id=456,
            sender_id=100,
            messages=messages,
        )

        assert len(group.messages) == 10
