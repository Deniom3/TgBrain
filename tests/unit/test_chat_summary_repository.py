"""
Тесты для ChatSummaryRepository.

⚠️ SKIP: Тесты используют реальную БД. Требуют мокификации.
"""

import pytest
from datetime import datetime, timedelta, timezone
from src.settings.repositories.chat_summary.repository import ChatSummaryRepository


pytestmark = pytest.mark.skip(reason="Требует мокификации — использует реальную БД")


class TestSaveSummary:
    """Тесты сохранения summary."""

    async def test_save_summary_success(self, db_pool):
        """Успешное сохранение summary."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            # Создаём тестовый чат
            await conn.execute("""
                INSERT INTO chat_settings (chat_id, title, type)
                VALUES (999999, 'Test Chat', 'private')
                ON CONFLICT (chat_id) DO NOTHING
            """)

            # Сохраняем summary через update_summary_status
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=24)
            period_end = now

            task_result = await repo.create_summary_task(
                conn=conn,
                chat_id=999999,
                period_start=period_start,
                period_end=period_end,
                params_hash="test_hash",
            )

            assert task_result is not None
            task_id = task_result[0]

            summary = await repo.get_summary_task(conn, task_id)

            assert summary is not None
            assert summary.chat_id == 999999
            assert summary.messages_count == 0

    async def test_save_summary_with_metadata(self, db_pool):
        """Сохранение summary с метаданными."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=12)
            period_end = now

            metadata = {"llm_model": "gpt-4", "prompt_hash": "abc123"}

            task_result = await repo.create_summary_task(
                conn=conn,
                chat_id=999999,
                period_start=period_start,
                period_end=period_end,
                params_hash="test_hash_meta",
                metadata=metadata,
            )

            assert task_result is not None
            task_id = task_result[0]

            summary = await repo.get_summary_task(conn, task_id)

            assert summary is not None
            assert summary.metadata == metadata


class TestGetSummary:
    """Тесты получения summary."""

    async def test_get_latest_summary(self, db_pool):
        """Получение последнего summary."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            now = datetime.now(timezone.utc)

            for i in range(3):
                period_start = now - timedelta(hours=24 * (i + 1))
                await repo.create_summary_task(
                    conn=conn,
                    chat_id=999999,
                    period_start=period_start,
                    period_end=now,
                    params_hash=f"test_hash_{i}",
                )

            # Получаем последнее
            latest = await repo.get_latest_summary(conn, 999999)

            assert latest is not None

    async def test_get_summary_by_id(self, db_pool):
        """Получение summary по ID."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=24)

            task_result = await repo.create_summary_task(
                conn=conn,
                chat_id=999999,
                period_start=period_start,
                period_end=now,
                params_hash="test_hash_by_id",
            )

            assert task_result is not None
            task_id = task_result[0]

            retrieved = await repo.get_summary_by_id(conn, task_id)

            assert retrieved is not None
            assert retrieved.id == task_id

    async def test_get_summaries_by_chat_paginated(self, db_pool):
        """Получение summary с пагинацией."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            now = datetime.now(timezone.utc)

            # Создаём 15 summary
            for i in range(15):
                period_start = now - timedelta(hours=i + 1)
                await repo.create_summary_task(
                    conn=conn,
                    chat_id=999999,
                    period_start=period_start,
                    period_end=now,
                    params_hash=f"test_hash_page_{i}",
                )

            # Получаем первую страницу
            page1 = await repo.get_summaries_by_chat(
                conn, 999999, limit=10, offset=0
            )
            assert len(page1) == 10

            # Получаем вторую страницу
            page2 = await repo.get_summaries_by_chat(
                conn, 999999, limit=10, offset=10
            )
            assert len(page2) == 5


class TestCheckSummaryExists:
    """Тесты проверки существования summary."""

    async def test_summary_exists(self, db_pool):
        """Summary существует."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=24)
            period_end = now

            await repo.create_summary_task(
                conn=conn,
                chat_id=999999,
                period_start=period_start,
                period_end=period_end,
                params_hash="test_hash_exists",
            )

            exists = await repo.check_summary_exists(
                conn, 999999, period_start, period_end
            )

            assert exists is True

    async def test_summary_not_exists(self, db_pool):
        """Summary не существует."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            now = datetime.now(timezone.utc)
            period_start = now - timedelta(hours=24)
            period_end = now

            exists = await repo.check_summary_exists(
                conn, 999999, period_start, period_end
            )

            assert exists is False


class TestDeleteOldSummaries:
    """Тесты удаления старых summary."""

    async def test_delete_old_summaries(self, db_pool):
        """Удаление старых записей."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            now = datetime.now(timezone.utc)

            # Удаляем старше 30 дней
            cutoff = now - timedelta(days=30)
            deleted = await repo.delete_old_summaries(
                conn, 999999, cutoff
            )

            assert deleted >= 0


class TestGetStats:
    """Тесты статистики."""

    async def test_get_summary_stats(self, db_pool):
        """Получение статистики по summary."""
        async with db_pool.acquire() as conn:
            repo = ChatSummaryRepository(db_pool)
            stats = await repo.get_stats(conn)

            assert isinstance(stats, list)
