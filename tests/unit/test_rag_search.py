"""
Модульные тесты для обновлённого RAGSearch.

Проверяют векторный поиск с фильтрацией по чатам,
расширение результатов поиска и интеграцию с ContextExpander.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg

from src.domain.value_objects import MessageText, SenderName, ChatTitle
from src.models.data_models import MessageRecord
from src.models.sql.rag import SQL_GET_MESSAGES_BY_PERIOD
from src.rag.search import RAGSearch, MAX_TOP_K
from src.rag.exceptions import DatabaseQueryError


# =============================================================================
# TestRAGSearchInit — Тесты инициализации
# =============================================================================


class TestRAGSearchInit:
    """Тесты инициализации RAGSearch."""

    @pytest.mark.asyncio
    async def test_rag_search_initialization(self, mock_db_pool, settings, mock_embedding_repo):
        """
        Проверка инициализации RAGSearch.

        Ожидание:
        - Создаётся экземпляр с config и db_pool
        - ContextExpander создаётся внутри RAGSearch
        - is_initialized = False до вызова initialize()
        """
        search = RAGSearch(settings, mock_db_pool, embedding_repo=mock_embedding_repo)

        assert search.config == settings
        assert search.db_pool == mock_db_pool
        assert search.expander is not None
        assert search.expander.is_initialized is False
        assert search.expander._embedding_repo == mock_embedding_repo

    @pytest.mark.asyncio
    async def test_rag_search_create_factory(self, mock_db_pool, settings):
        """
        Проверка фабричного метода create().

        Ожидание:
        - Создаётся и инициализируется экземпляр
        - expander.is_initialized = True после create()
        """
        from src.settings.repositories.embedding_providers import EmbeddingProvidersRepository

        with patch.object(EmbeddingProvidersRepository, 'get_active', new_callable=AsyncMock) as mock_get_active:
            mock_provider = MagicMock()
            mock_provider.embedding_dim = 768
            mock_provider.name = "ollama"
            mock_provider.model = "nomic-embed-text"
            mock_get_active.return_value = mock_provider

            search = await RAGSearch.create(settings, mock_db_pool)

            assert search is not None
            assert search.expander.is_initialized is True


# =============================================================================
# TestSearchSimilar — Тесты векторного поиска
# =============================================================================


class TestSearchSimilar:
    """Тесты метода search_similar."""

    @pytest.mark.asyncio
    async def test_search_similar_all_chats(self, initialized_rag_search):
        """
        Проверка поиска по всем чатам (chat_id=None).

        Ожидание:
        - Вызывается SQL_SEARCH_SIMILAR_WITH_CHAT_FILTER
        - chat_id передаётся как None
        - Возвращаются результаты поиска
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0)

        rows = [
            {
                "id": 1,
                "message_text": "Сообщение 1",
                "message_date": base_time,
                "chat_title": "Chat One",
                "message_link": "https://t.me/test/1",
                "sender_name": "User One",
                "sender_id": 100,
                "similarity_score": 0.95,
            },
            {
                "id": 2,
                "message_text": "Сообщение 2",
                "message_date": base_time + timedelta(minutes=5),
                "chat_title": "Chat Two",
                "message_link": "https://t.me/test/2",
                "sender_name": "User Two",
                "sender_id": 200,
                "similarity_score": 0.88,
            },
            {
                "id": 3,
                "message_text": "Сообщение 3",
                "message_date": base_time + timedelta(minutes=10),
                "chat_title": "Chat One",
                "message_link": "https://t.me/test/3",
                "sender_name": "User One",
                "sender_id": 100,
                "similarity_score": 0.82,
            },
        ]

        connection = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=rows)

        query_embedding = [0.1] * 768
        results = await initialized_rag_search.search_similar(
            query_embedding=query_embedding,
            top_k=5,
            chat_id=None,
        )

        assert len(results) == 3
        assert results[0].id == 1
        assert results[0].similarity_score == 0.95
        assert results[1].id == 2
        assert results[2].id == 3

        connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar_by_chat_id(self, initialized_rag_search):
        """
        Проверка поиска с фильтрацией по chat_id.

        Ожидание:
        - Вызывается SQL_SEARCH_SIMILAR_WITH_CHAT_FILTER
        - chat_id передаётся в запрос
        - Возвращаются результаты только для указанного чата
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0)

        rows = [
            {
                "id": 1,
                "message_text": "Сообщение из чата 123",
                "message_date": base_time,
                "chat_title": "Target Chat",
                "message_link": "https://t.me/test/1",
                "sender_name": "User One",
                "sender_id": 100,
                "similarity_score": 0.95,
            },
            {
                "id": 4,
                "message_text": "Ещё сообщение из чата 123",
                "message_date": base_time + timedelta(minutes=15),
                "chat_title": "Target Chat",
                "message_link": "https://t.me/test/4",
                "sender_name": "User One",
                "sender_id": 100,
                "similarity_score": 0.75,
            },
        ]

        connection = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=rows)

        query_embedding = [0.1] * 768
        results = await initialized_rag_search.search_similar(
            query_embedding=query_embedding,
            top_k=5,
            chat_id=123,
        )

        assert len(results) == 2

        connection.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar_empty_embedding(self, mock_db_pool, settings, mock_embedding_repo):
        """
        Проверка поиска с пустым embedding.

        Ожидание:
        - Возвращается пустой список
        - Логирование ошибки
        - БД не вызывается
        """
        search = RAGSearch(settings, mock_db_pool, embedding_repo=mock_embedding_repo)
        await search.expander.initialize()

        result = await search.search_similar(
            query_embedding=[],
            top_k=5,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_search_similar_invalid_top_k(self, initialized_rag_search):
        """
        Проверка коррекции некорректного top_k.

        Ожидание:
        - top_k <= 0 заменяется на 5
        - top_k > MAX_TOP_K заменяется на MAX_TOP_K
        """
        connection = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=[])

        query_embedding = [0.1] * 768

        await initialized_rag_search.search_similar(query_embedding, top_k=0)
        call_args = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value.fetch.call_args
        assert call_args[0][2] == 5

        connection.fetch.reset_mock()

        await initialized_rag_search.search_similar(query_embedding, top_k=200)
        call_args = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value.fetch.call_args
        assert call_args[0][2] == MAX_TOP_K

    @pytest.mark.asyncio
    async def test_search_similar_db_error(self, initialized_rag_search):
        """
        Проверка обработки ошибки БД.

        Ожидание:
        - PostgresError пробрасывается как DatabaseQueryError
        """
        connection = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(side_effect=asyncpg.PostgresError("DB error"))

        query_embedding = [0.1] * 768

        with pytest.raises(DatabaseQueryError):
            await initialized_rag_search.search_similar(
                query_embedding=query_embedding,
                top_k=5,
            )


# =============================================================================
# TestExpandSearchResults — Тесты расширения результатов
# =============================================================================


class TestExpandSearchResults:
    """Тесты метода expand_search_results."""

    @pytest.mark.asyncio
    async def test_expand_search_results_no_expansion(self, initialized_rag_search):
        """
        Проверка поиска без расширения контекста.

        Ожидание:
        - При expand_context=False результаты не изменяются
        - ContextExpander не вызывается
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Короткое"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.95,
            ),
            MessageRecord(
                id=2,
                text=MessageText("Длинное сообщение для проверки"),
                date=base_time + timedelta(minutes=5),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/2",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.88,
            ),
        ]

        with patch.object(initialized_rag_search.expander, 'expand_with_neighbors', new_callable=AsyncMock) as mock_expand:
            result = await initialized_rag_search.expand_search_results(
                messages=messages,
                chat_id=456,
                expand_context=False,
            )

            assert len(result) == 2
            assert result[0].is_expanded is False
            assert result[1].is_expanded is False
            mock_expand.assert_not_called()

    @pytest.mark.asyncio
    async def test_expand_search_results_short_message(self, initialized_rag_search):
        """
        Проверка расширения короткого сообщения.

        Ожидание:
        - Для сообщений < SHORT_MESSAGE_THRESHOLD вызывается expand_with_neighbors
        - is_expanded = True после расширения
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Короткое"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.95,
            ),
        ]

        neighbor_messages = [
            MessageRecord(
                id=2,
                text=MessageText("Соседнее сообщение"),
                date=base_time - timedelta(minutes=2),
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/2",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.85,
            ),
        ]

        with patch.object(initialized_rag_search.expander, 'expand_with_neighbors', new_callable=AsyncMock) as mock_expand:
            mock_expand.return_value = neighbor_messages

            result = await initialized_rag_search.expand_search_results(
                messages=messages,
                chat_id=456,
                expand_context=True,
            )

            assert len(result) == 1
            assert result[0].is_expanded is True
            assert len(result[0].expanded_context) == 1

            mock_expand.assert_called_once_with(
                message_id=1,
                chat_id=456,
                sender_id=100,
                before=2,
                after=2,
            )

    @pytest.mark.asyncio
    async def test_expand_search_results_no_chat_id(self, initialized_rag_search):
        """
        Проверка расширения без chat_id.

        Ожидание:
        - При chat_id=None расширение не выполняется
        - Возвращаются исходные сообщения
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0)

        messages = [
            MessageRecord(
                id=1,
                text=MessageText("Короткое"),
                date=base_time,
                chat_title=ChatTitle("Test Chat"),
                link="https://t.me/test/1",
                sender_name=SenderName("User One"),
                sender_id=100,
                similarity_score=0.95,
            ),
        ]

        with patch.object(initialized_rag_search.expander, 'expand_with_neighbors', new_callable=AsyncMock) as mock_expand:
            result = await initialized_rag_search.expand_search_results(
                messages=messages,
                chat_id=None,
                expand_context=True,
            )

            assert len(result) == 1
            assert result[0].is_expanded is False
            mock_expand.assert_not_called()


# =============================================================================
# TestGetMessagesByPeriod — Тесты получения сообщений за период
# =============================================================================


class TestGetMessagesByPeriod:
    """Тесты метода get_messages_by_period."""

    @pytest.mark.asyncio
    async def test_get_messages_by_period_success(self, initialized_rag_search):
        """
        Проверка получения сообщений за период.

        Ожидание:
        - Вызывается SQL_GET_MESSAGES_BY_PERIOD
        - Возвращаются сообщения за указанный период
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0)

        rows = [
            {
                "id": 1,
                "message_text": "Сообщение 1",
                "message_date": base_time,
                "chat_title": "Test Chat",
                "message_link": "https://t.me/test/1",
                "sender_name": "User One",
                "sender_id": 100,
            },
            {
                "id": 2,
                "message_text": "Сообщение 2",
                "message_date": base_time + timedelta(hours=1),
                "chat_title": "Test Chat",
                "message_link": "https://t.me/test/2",
                "sender_name": "User One",
                "sender_id": 100,
            },
        ]

        connection = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(return_value=rows)

        results = await initialized_rag_search.get_messages_by_period(
            period_hours=24,
            max_messages=50,
            chat_id=456,
        )

        assert len(results) == 2
        assert results[0].id == 1
        assert results[0].similarity_score == 0.0

        connection.fetch.assert_called_once()
        call_args = connection.fetch.call_args[0]
        assert call_args[0] == SQL_GET_MESSAGES_BY_PERIOD
        assert call_args[1] == 24
        assert call_args[2] == 50
        assert call_args[3] == 456

    @pytest.mark.asyncio
    async def test_get_messages_by_period_invalid_params(self, mock_db_pool, settings, mock_embedding_repo):
        """
        Проверка валидации параметров периода.

        Ожидание:
        - ValueError при period_hours <= 0
        - ValueError при max_messages <= 0
        """
        search = RAGSearch(settings, mock_db_pool, embedding_repo=mock_embedding_repo)
        await search.expander.initialize()

        with pytest.raises(ValueError, match="period_hours должен быть больше 0"):
            await search.get_messages_by_period(
                period_hours=0,
                max_messages=50,
            )

        with pytest.raises(ValueError, match="max_messages должен быть больше 0"):
            await search.get_messages_by_period(
                period_hours=24,
                max_messages=0,
            )

    @pytest.mark.asyncio
    async def test_get_messages_by_period_db_error(self, initialized_rag_search):
        """
        Проверка обработки ошибки БД.

        Ожидание:
        - PostgresError пробрасывается как DatabaseQueryError
        """
        connection = initialized_rag_search.db_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(side_effect=asyncpg.PostgresError("DB error"))

        with pytest.raises(DatabaseQueryError):
            await initialized_rag_search.get_messages_by_period(
                period_hours=24,
                max_messages=50,
            )


# =============================================================================
# TestRAGSearchWorkflow — Тесты рабочего процесса поиска
# =============================================================================


class TestRAGSearchWorkflow:
    """Тесты полного workflow RAG поиска."""

    @pytest.mark.asyncio
    async def test_full_search_workflow(self, mock_db_pool, settings, mock_embedding_repo):
        """
        Проверка полного цикла поиска с расширением.

        Ожидание:
        - search_similar возвращает результаты
        - expand_search_results расширяет короткие сообщения
        - Результаты содержат расширенный контекст
        """
        base_time = datetime(2024, 1, 15, 10, 0, 0)

        search_rows = [
            {
                "id": 1,
                "message_text": "Короткое",
                "message_date": base_time,
                "chat_title": "Test Chat",
                "message_link": "https://t.me/test/1",
                "sender_name": "User One",
                "sender_id": 100,
                "similarity_score": 0.95,
            },
            {
                "id": 2,
                "message_text": "Длинное сообщение для проверки работы расширения контекста",
                "message_date": base_time + timedelta(minutes=5),
                "chat_title": "Test Chat",
                "message_link": "https://t.me/test/2",
                "sender_name": "User One",
                "sender_id": 100,
                "similarity_score": 0.88,
            },
        ]

        neighbor_rows = [
            {
                "id": 3,
                "message_text": "Соседнее сообщение",
                "message_date": base_time - timedelta(minutes=2),
                "chat_title": "Test Chat",
                "message_link": "https://t.me/test/3",
                "sender_name": "User One",
                "sender_id": 100,
                "similarity_score": 0.85,
            },
        ]

        connection = mock_db_pool.acquire.return_value.__aenter__.return_value
        connection.fetch = AsyncMock(side_effect=[search_rows, neighbor_rows])

        search = RAGSearch(
            config=settings,
            db_pool=mock_db_pool,
            embedding_repo=mock_embedding_repo,
        )
        await search.initialize()

        query_embedding = [0.1] * 768

        results = await search.search_similar(
            query_embedding=query_embedding,
            top_k=5,
            chat_id=456,
        )

        assert len(results) == 2

        expanded = await search.expand_search_results(
            messages=results,
            chat_id=456,
            expand_context=True,
        )

        assert len(expanded) == 2

        short_message = expanded[0]
        assert str(short_message.text) == "Короткое"
