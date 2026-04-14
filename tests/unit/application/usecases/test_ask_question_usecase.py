"""Тесты для AskQuestionUseCase.

11 unit-тестов с AAA-структурой, моки портов.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from src.application.exceptions import (
    ChatNotFoundError,
    DatabaseError,
    EmbeddingGenerationError,
    LLMGenerationError,
    NoResultsFoundError,
)
from src.application.usecases.ask_question import (
    AskQuestionRequest,
    AskQuestionUseCase,
    AskResult,
)
from src.application.usecases.protocols import (
    ChatExistenceChecker,
    EmbeddingGeneratorPort,
    LLMGenerationPort,
    SummarySearchPort,
    VectorSearchPort,
)
from src.application.usecases.result import Failure, Success
from src.domain.value_objects import ChatTitle, MessageText, SenderName
from src.models.data_models import MessageRecord, SummaryRecord


def _make_message_record(
    message_id: int = 1,
    chat_id: int = -100,
    text: str = "Test message",
    author: str = "Author",
    similarity_score: float = 0.8,
    is_expanded: bool = False,
) -> MessageRecord:
    return MessageRecord(
        id=message_id,
        text=MessageText(text),
        date=datetime(2024, 1, 1, 12, 0),
        chat_title=ChatTitle(f"Chat {chat_id}"),
        link=f"https://t.me/c/{chat_id}/{message_id}",
        sender_name=SenderName(author),
        sender_id=1,
        similarity_score=similarity_score,
        is_expanded=is_expanded,
    )


def _make_summary_record(
    summary_id: int = 1,
    chat_id: int = -100,
    text: str = "Test summary",
    similarity_score: float = 0.7,
) -> SummaryRecord:
    return SummaryRecord(
        id=summary_id,
        chat_id=chat_id,
        chat_title=ChatTitle(f"Chat {chat_id}"),
        result_text=text,
        period_start=datetime(2024, 1, 1),
        period_end=datetime(2024, 1, 2),
        messages_count=10,
        similarity_score=similarity_score,
        created_at=datetime(2024, 1, 2, 12, 0),
    )


@pytest.fixture
def embedding_generator() -> EmbeddingGeneratorPort:
    mock = AsyncMock(spec=EmbeddingGeneratorPort)
    mock.get_embedding.return_value = [0.1] * 768
    return mock


@pytest.fixture
def vector_search() -> VectorSearchPort:
    mock = AsyncMock(spec=VectorSearchPort)
    mock.search_similar.return_value = [_make_message_record()]
    mock.expand_search_results.return_value = [_make_message_record(is_expanded=True)]
    return mock


@pytest.fixture
def summary_search() -> SummarySearchPort:
    mock = AsyncMock(spec=SummarySearchPort)
    mock.search_summaries.return_value = [_make_summary_record()]
    return mock


@pytest.fixture
def llm_generator() -> LLMGenerationPort:
    mock = AsyncMock(spec=LLMGenerationPort)
    mock.generate.return_value = "Generated answer based on context"
    return mock


@pytest.fixture
def chat_checker() -> ChatExistenceChecker:
    mock = AsyncMock(spec=ChatExistenceChecker)
    mock.check_chat_exists.return_value = True
    return mock


@pytest.fixture
def usecase(
    embedding_generator: EmbeddingGeneratorPort,
    vector_search: VectorSearchPort,
    summary_search: SummarySearchPort,
    llm_generator: LLMGenerationPort,
    chat_checker: ChatExistenceChecker,
) -> AskQuestionUseCase:
    return AskQuestionUseCase(
        embedding_generator=embedding_generator,
        vector_search=vector_search,
        summary_search=summary_search,
        llm_generator=llm_generator,
        chat_checker=chat_checker,
    )


class TestAskQuestionUseCaseExecute:
    async def test_execute_success_returns_ask_result(
        self,
        usecase: AskQuestionUseCase,
        embedding_generator: AsyncMock,
        vector_search: AsyncMock,
        llm_generator: AsyncMock,
    ) -> None:
        request = AskQuestionRequest(
            question="Как настроить авторизацию?",
            chat_id=None,
            search_in="messages",
            expand_context=False,
        )

        result = await usecase.execute(request)

        assert isinstance(result, Success)
        assert isinstance(result.value, AskResult)
        assert result.value.answer == "Generated answer based on context"
        assert len(result.value.sources) > 0
        assert result.value.query == "Как настроить авторизацию?"
        assert result.value.search_source == "messages"
        assert result.value.total_found == 1

    async def test_execute_chat_not_found_raises_error(
        self,
        chat_checker: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        chat_checker.check_chat_exists.return_value = False
        request = AskQuestionRequest(
            question="Test question",
            chat_id=999,
            search_in="messages",
        )

        result = await usecase.execute(request)

        assert isinstance(result, Failure)
        assert isinstance(result.error, ChatNotFoundError)
        assert result.error.chat_id == 999

    async def test_execute_no_results_raises_error(
        self,
        vector_search: AsyncMock,
        summary_search: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        vector_search.search_similar.return_value = []
        summary_search.search_summaries.return_value = []
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="both",
            expand_context=False,
        )

        result = await usecase.execute(request)

        assert isinstance(result, Failure)
        assert isinstance(result.error, NoResultsFoundError)
        assert result.error.search_source == "both"

    async def test_execute_embedding_error_raises_error(
        self,
        embedding_generator: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        embedding_generator.get_embedding.side_effect = Exception("Embedding service down")
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="messages",
        )

        result = await usecase.execute(request)

        assert isinstance(result, Failure)
        assert isinstance(result.error, EmbeddingGenerationError)
        assert "Embedding generation failed" in result.error.message

    async def test_execute_llm_error_raises_error(
        self,
        llm_generator: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        llm_generator.generate.side_effect = Exception("LLM service unavailable")
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="messages",
            expand_context=False,
        )

        result = await usecase.execute(request)

        assert isinstance(result, Failure)
        assert isinstance(result.error, LLMGenerationError)
        assert "LLM generation failed" in result.error.message

    async def test_execute_database_error_raises_error(
        self,
        vector_search: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        vector_search.search_similar.side_effect = Exception("Connection refused")
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="messages",
        )

        result = await usecase.execute(request)

        assert isinstance(result, Failure)
        assert isinstance(result.error, DatabaseError)
        assert "Database operation failed" in result.error.message

    async def test_execute_messages_only_calls_message_search(
        self,
        summary_search: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="messages",
            expand_context=False,
        )

        await usecase.execute(request)

        summary_search.search_summaries.assert_not_called()

    async def test_execute_summaries_only_calls_summary_search(
        self,
        vector_search: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="summaries",
            expand_context=False,
        )

        await usecase.execute(request)

        vector_search.search_similar.assert_not_called()

    async def test_execute_both_calls_both_searches_and_merges(
        self,
        vector_search: AsyncMock,
        summary_search: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="both",
            expand_context=False,
        )

        result = await usecase.execute(request)

        vector_search.search_similar.assert_called_once()
        summary_search.search_summaries.assert_called_once()
        assert isinstance(result, Success)
        assert result.value.total_found == 2

    async def test_execute_expand_context_calls_expand(
        self,
        vector_search: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="messages",
            expand_context=True,
            context_window=3,
        )

        await usecase.execute(request)

        vector_search.expand_search_results.assert_called_once()

    async def test_execute_no_expand_does_not_call_expand(
        self,
        vector_search: AsyncMock,
        usecase: AskQuestionUseCase,
    ) -> None:
        request = AskQuestionRequest(
            question="Test question",
            chat_id=None,
            search_in="messages",
            expand_context=False,
        )

        await usecase.execute(request)

        vector_search.expand_search_results.assert_not_called()
