"""
Тесты для SummaryEmbeddingGenerator.

Unit-тесты: проверка делегирования и graceful degradation.
Integration-тест: полный цикл с mock SummaryEmbeddingsService.
"""

import logging
from unittest.mock import AsyncMock

import pytest

from src.infrastructure.services.summary_embedding_generator import (
    SummaryEmbeddingGenerator,
)
from src.rag.summary_embeddings_service import SummaryEmbeddingsService


@pytest.fixture
def mock_embeddings_service() -> AsyncMock:
    """Фикстура mock SummaryEmbeddingsService."""
    return AsyncMock(spec=SummaryEmbeddingsService)


@pytest.fixture
def test_logger() -> logging.Logger:
    """Фикстура логгера для тестов."""
    return logging.getLogger("test.embedding_generator")


@pytest.fixture
def generator(
    mock_embeddings_service: AsyncMock,
    test_logger: logging.Logger,
) -> SummaryEmbeddingGenerator:
    """Фикстура SummaryEmbeddingGenerator с мокнутыми зависимостями."""
    return SummaryEmbeddingGenerator(
        embeddings_service=mock_embeddings_service,
        logger=test_logger,
    )


class TestDispatchEmbeddingSuccess:
    """Тесты успешного вызова dispatch_embedding."""

    async def test_dispatch_embedding_success(
        self,
        generator: SummaryEmbeddingGenerator,
        mock_embeddings_service: AsyncMock,
    ) -> None:
        """Успешный вызов — возврат True, делегирование в embeddings_service."""
        mock_embeddings_service.generate_and_save_embedding.return_value = True

        result = await generator.dispatch_embedding(
            task_id=42,
            digest="Test summary digest",
            model_name="nomic-embed-text",
        )

        assert result is True
        mock_embeddings_service.generate_and_save_embedding.assert_awaited_once_with(
            42,
            "Test summary digest",
            "nomic-embed-text",
        )


class TestDispatchEmbeddingGenerateError:
    """Тесты ошибки генерации эмбеддинга."""

    async def test_dispatch_embedding_generate_error(
        self,
        generator: SummaryEmbeddingGenerator,
        mock_embeddings_service: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Ошибка генерации — warning лог, возврат False."""
        mock_embeddings_service.generate_and_save_embedding.side_effect = (
            RuntimeError("Embedding generation failed")
        )

        with caplog.at_level(logging.DEBUG):
            result = await generator.dispatch_embedding(
                task_id=42,
                digest="Test summary",
                model_name="nomic-embed-text",
            )

        assert result is False
        assert any(
            "Не удалось сохранить эмбеддинг для задачи 42: RuntimeError"
            in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )


class TestDispatchEmbeddingSaveError:
    """Тесты ошибки сохранения эмбеддинга."""

    async def test_dispatch_embedding_save_error(
        self,
        generator: SummaryEmbeddingGenerator,
        mock_embeddings_service: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Ошибка сохранения — warning лог, возврат False."""
        mock_embeddings_service.generate_and_save_embedding.side_effect = (
            ConnectionError("Database connection lost")
        )

        with caplog.at_level(logging.DEBUG):
            result = await generator.dispatch_embedding(
                task_id=99,
                digest="Another summary",
                model_name="nomic-embed-text",
            )

        assert result is False
        assert any(
            "Не удалось сохранить эмбеддинг для задачи 99: ConnectionError"
            in record.message
            for record in caplog.records
            if record.levelno == logging.WARNING
        )


class TestDispatchEmbeddingEmptyDigest:
    """Тесты пустого digest."""

    async def test_dispatch_embedding_empty_digest(
        self,
        generator: SummaryEmbeddingGenerator,
        mock_embeddings_service: AsyncMock,
    ) -> None:
        """Пустой digest — делегирование происходит, сервис обрабатывает валидацию."""
        mock_embeddings_service.generate_and_save_embedding.return_value = True

        result = await generator.dispatch_embedding(
            task_id=1,
            digest="",
            model_name="nomic-embed-text",
        )

        assert result is True
        mock_embeddings_service.generate_and_save_embedding.assert_awaited_once_with(
            1,
            "",
            "nomic-embed-text",
        )

    async def test_dispatch_embedding_whitespace_digest(
        self,
        generator: SummaryEmbeddingGenerator,
        mock_embeddings_service: AsyncMock,
    ) -> None:
        """Digest с пробелами — делегирование происходит, сервис обрабатывает."""
        mock_embeddings_service.generate_and_save_embedding.return_value = True

        result = await generator.dispatch_embedding(
            task_id=2,
            digest="   ",
            model_name="nomic-embed-text",
        )

        assert result is True


@pytest.mark.integration
class TestDispatchEmbeddingIntegration:
    """Integration-тесты для dispatch_embedding."""

    async def test_dispatch_embedding_integration(
        self,
        mock_embeddings_service: AsyncMock,
        test_logger: logging.Logger,
    ) -> None:
        """Полный цикл: генератор вызывает сервис, возвращает True."""
        mock_embeddings_service.generate_and_save_embedding.return_value = True

        generator = SummaryEmbeddingGenerator(
            embeddings_service=mock_embeddings_service,
            logger=test_logger,
        )

        result = await generator.dispatch_embedding(
            task_id=100,
            digest="Integration test summary",
            model_name="test-model",
        )

        assert result is True
        mock_embeddings_service.generate_and_save_embedding.assert_awaited_once_with(
            100,
            "Integration test summary",
            "test-model",
        )
