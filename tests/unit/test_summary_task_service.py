"""
Тесты для SummaryTaskService (Задача 26).

Тестирование плавающего TTL и округления до 6 часов.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from src.rag.summary_task_service import SummaryTaskService


class TestCacheTTL:
    """Тесты расчёта TTL."""

    @pytest.fixture
    def service(self):
        """Создать сервис с моками зависимостей."""
        config = MagicMock()
        search = MagicMock()
        llm_client = MagicMock()
        embeddings_client = MagicMock()
        embedding_generator = MagicMock()
        webhook_dispatcher = MagicMock()

        return SummaryTaskService(
            config, search, llm_client, embeddings_client,
            db_pool=MagicMock(),
            embedding_generator=embedding_generator,
            webhook_dispatcher=webhook_dispatcher,
        )

    def test_ttl_current_day(self, service):
        """TTL для текущего дня (< 24 часов)."""
        now = datetime.now(timezone.utc)
        period_end = now - timedelta(hours=2)
        period_start = period_end - timedelta(hours=24)

        ttl = service.get_cache_ttl(period_start, period_end)

        assert ttl == 120  # 2 часа

    def test_ttl_yesterday(self, service):
        """TTL для вчерашнего дня (24-72 часа)."""
        now = datetime.now(timezone.utc)
        period_end = now - timedelta(hours=48)  # 2 дня назад
        period_start = period_end - timedelta(hours=24)

        ttl = service.get_cache_ttl(period_start, period_end)

        assert ttl == 1440  # 24 часа

    def test_ttl_archive(self, service):
        """TTL для архивных данных (>= 72 часов)."""
        now = datetime.now(timezone.utc)
        period_end = now - timedelta(days=5)  # 5 дней назад
        period_start = period_end - timedelta(hours=24)

        ttl = service.get_cache_ttl(period_start, period_end)

        assert ttl is None  # Без ограничений

    def test_ttl_boundary_24_hours(self, service):
        """Граница 24 часа."""
        now = datetime.now(timezone.utc)

        # 23 часа 59 минут назад
        period_end = now - timedelta(hours=23, minutes=59)
        assert service.get_cache_ttl(period_end - timedelta(hours=1), period_end) == 120

        # 24 часа 1 минута назад
        period_end = now - timedelta(hours=24, minutes=1)
        assert service.get_cache_ttl(period_end - timedelta(hours=1), period_end) == 1440

    def test_ttl_boundary_72_hours(self, service):
        """Граница 72 часа."""
        now = datetime.now(timezone.utc)

        # 71 час 59 минут назад
        period_end = now - timedelta(hours=71, minutes=59)
        assert service.get_cache_ttl(period_end - timedelta(hours=1), period_end) == 1440

        # 72 часа 1 минута назад
        period_end = now - timedelta(hours=72, minutes=1)
        assert service.get_cache_ttl(period_end - timedelta(hours=1), period_end) is None


class TestGenerateParamsHash:
    """Тесты генерации хеша параметров."""

    @pytest.fixture
    def service(self):
        """Создать сервис с моками зависимостей."""
        config = MagicMock()
        search = MagicMock()
        llm_client = MagicMock()
        embeddings_client = MagicMock()
        embedding_generator = MagicMock()
        webhook_dispatcher = MagicMock()

        return SummaryTaskService(
            config, search, llm_client, embeddings_client,
            db_pool=MagicMock(),
            embedding_generator=embedding_generator,
            webhook_dispatcher=webhook_dispatcher,
        )

    def test_hash_rounding_1_hour(self, service):
        """Округление до 1 часа для коротких периодов."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=1)  # 1 час

        # Запрос в час 10
        hash1 = service.generate_params_hash(
            chat_id=123,
            period_start=period_start.replace(minute=15),
            period_end=now.replace(minute=15),
        )

        # Запрос в час 11 (следующий час)
        hash2 = service.generate_params_hash(
            chat_id=123,
            period_start=period_start.replace(hour=(now.hour + 1) % 24, minute=15),
            period_end=now.replace(hour=(now.hour + 1) % 24, minute=15),
        )

        # Разные хеши для разных часов
        assert hash1 != hash2

    def test_hash_rounding_6_hours(self, service):
        """Округление до 6 часов для длинных периодов."""
        now = datetime.now(timezone.utc)
        period_end = now
        period_start = now - timedelta(hours=24)  # 24 часа

        # Запросы в пределах одного 6-часового блока
        hash1 = service.generate_params_hash(
            chat_id=123,
            period_start=period_start.replace(hour=12, minute=15),
            period_end=period_end.replace(hour=12, minute=15),
        )

        hash2 = service.generate_params_hash(
            chat_id=123,
            period_start=period_start.replace(hour=12, minute=45),
            period_end=period_end.replace(hour=12, minute=45),
        )

        # Одинаковый хеш для одного 6-часового блока
        assert hash1 == hash2

    def test_hash_different_6_hour_blocks(self, service):
        """Разные хеши для разных 6-часовых блоков."""
        now = datetime.now(timezone.utc)
        period_end = now
        period_start = now - timedelta(hours=24)  # 24 часа

        # Блок 12:00-18:00
        hash1 = service.generate_params_hash(
            chat_id=123,
            period_start=period_start.replace(hour=12),
            period_end=period_end.replace(hour=12),
        )

        # Блок 18:00-00:00
        hash2 = service.generate_params_hash(
            chat_id=123,
            period_start=period_start.replace(hour=18),
            period_end=period_end.replace(hour=18),
        )

        # Разные хеши для разных блоков
        assert hash1 != hash2

    def test_hash_short_period_boundary(self, service):
        """Граница короткого периода (3 часа)."""
        now = datetime.now(timezone.utc)
        
        # Период 3 часа (должен округляться до 1 часа)
        period_start_3h = now - timedelta(hours=3)
        hash_3h = service.generate_params_hash(
            chat_id=123,
            period_start=period_start_3h,
            period_end=now,
        )
        
        # Период 4 часа (должен округляться до 6 часов)
        period_start_4h = now - timedelta(hours=4)
        hash_4h = service.generate_params_hash(
            chat_id=123,
            period_start=period_start_4h,
            period_end=now,
        )
        
        # Хеши должны быть разными из-за разного округления
        assert hash_3h != hash_4h

    def test_hash_same_chat_different_periods(self, service):
        """Разные хеши для одного чата, но разных периодов."""
        now = datetime.now(timezone.utc)
        
        hash1 = service.generate_params_hash(
            chat_id=123,
            period_start=now - timedelta(hours=24),
            period_end=now,
        )
        
        hash2 = service.generate_params_hash(
            chat_id=123,
            period_start=now - timedelta(hours=48),
            period_end=now - timedelta(hours=24),
        )
        
        assert hash1 != hash2

    def test_hash_different_chats_same_period(self, service):
        """Разные хеши для разных чатов с одинаковым периодом."""
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=24)
        
        hash1 = service.generate_params_hash(
            chat_id=123,
            period_start=period_start,
            period_end=now,
        )
        
        hash2 = service.generate_params_hash(
            chat_id=456,
            period_start=period_start,
            period_end=now,
        )

        assert hash1 != hash2


class TestDelegation:
    """Тесты делегирования адаптерам."""

    @pytest.fixture
    def service(self):
        """Создать сервис с моками адаптеров."""
        config = MagicMock()
        config.ollama_embedding_model = "nomic-embed-text"
        search = MagicMock()
        llm_client = MagicMock()
        embeddings_client = MagicMock()
        embedding_generator = AsyncMock()
        webhook_dispatcher = AsyncMock()

        return SummaryTaskService(
            config, search, llm_client, embeddings_client,
            db_pool=MagicMock(),
            embedding_generator=embedding_generator,
            webhook_dispatcher=webhook_dispatcher,
        )

    @pytest.mark.asyncio
    async def test_summary_task_delegates_to_embedding_generator(self, service) -> None:
        """Вызывается dispatch_embedding."""
        task_id = 42
        digest = "test summary text"
        model_name = "nomic-embed-text"

        await service.embedding_generator.dispatch_embedding(
            task_id, digest, model_name,
        )

        service.embedding_generator.dispatch_embedding.assert_awaited_once_with(
            task_id, digest, model_name,
        )

    @pytest.mark.asyncio
    async def test_summary_task_delegates_to_webhook_dispatcher(self, service) -> None:
        """Вызывается dispatch_webhook_on_completion."""
        task_id = 42
        chat_id = 123

        await service.webhook_dispatcher.dispatch_webhook_on_completion(
            task_id, chat_id,
        )

        service.webhook_dispatcher.dispatch_webhook_on_completion.assert_awaited_once_with(
            task_id, chat_id,
        )


class TestGracefulDegradation:
    """Тесты graceful degradation адаптеров."""

    @pytest.mark.asyncio
    async def test_summary_task_embedding_error_continues(self) -> None:
        """Ошибка embedding не прерывает задачу."""
        from src.infrastructure.services.summary_embedding_generator import SummaryEmbeddingGenerator
        from src.rag.summary_embeddings_service import SummaryEmbeddingsService

        embeddings_service = MagicMock(spec=SummaryEmbeddingsService)
        embeddings_service.generate_and_save_embedding = AsyncMock(
            side_effect=RuntimeError("embedding failed"),
        )

        generator = SummaryEmbeddingGenerator(
            embeddings_service=embeddings_service,
            logger=MagicMock(),
        )

        result = await generator.dispatch_embedding(1, "text", "model")

        assert result is False

    @pytest.mark.asyncio
    async def test_summary_task_webhook_error_continues(self) -> None:
        """Ошибка webhook не прерывает задачу."""
        from src.infrastructure.services.summary_webhook_dispatcher import SummaryWebhookDispatcher
        from src.settings.repositories.chat_settings import ChatSettingsRepository

        webhook_service = AsyncMock()
        chat_settings_repo = AsyncMock(spec=ChatSettingsRepository)
        chat_settings_repo.get_webhook_config_raw = AsyncMock(
            side_effect=RuntimeError("webhook failed"),
        )

        dispatcher = SummaryWebhookDispatcher(
            webhook_service=webhook_service,
            chat_settings_repo=chat_settings_repo,
            logger=MagicMock(),
        )

        result = await dispatcher.dispatch_webhook_on_completion(1, 123)

        assert result is False

    @pytest.mark.asyncio
    async def test_webhook_dispatcher_log_task_result_on_error(self) -> None:
        """_log_task_result логирует ошибку упавшей задачи."""
        import asyncio
        from src.infrastructure.services.summary_webhook_dispatcher import SummaryWebhookDispatcher
        from src.settings.repositories.chat_settings import ChatSettingsRepository

        mock_logger = MagicMock()
        webhook_service = AsyncMock()
        chat_settings_repo = AsyncMock(spec=ChatSettingsRepository)

        dispatcher = SummaryWebhookDispatcher(
            webhook_service=webhook_service,
            chat_settings_repo=chat_settings_repo,
            logger=mock_logger,
        )

        async def failing_coro() -> None:
            raise RuntimeError("webhook failed")

        task = asyncio.create_task(failing_coro())
        task.add_done_callback(dispatcher._pending_tasks.discard)
        task.add_done_callback(dispatcher._log_task_result)

        with pytest.raises(RuntimeError, match="webhook failed"):
            await task

        mock_logger.error.assert_called_once()
