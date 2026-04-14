"""
Тесты для Chat Summary API endpoints.

⚠️ SKIP: Тесты используют реальную БД. Требуют мокификации.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta, timezone


pytestmark = pytest.mark.skip(reason="Требует мокификации — использует реальную БД")


class TestGetSummary:
    """Тесты получения summary."""

    async def test_get_chat_summaries(self, client: AsyncClient, db_pool):
        """Получение списка summary для чата."""
        # Создаём тестовые данные
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_settings (chat_id, title, type)
                VALUES (888888, 'Test Chat API', 'private')
                ON CONFLICT (chat_id) DO NOTHING
            """)

            now = datetime.now(timezone.utc)
            for i in range(5):
                period_start = now - timedelta(hours=i + 1)
                await conn.execute("""
                    INSERT INTO chat_summaries
                    (chat_id, period_start, period_end, summary_text, messages_count)
                    VALUES ($1, $2, $3, $4, $5)
                """, 888888, period_start, now, f"Summary {i}", 10)

        # Получаем summary (новый путь /summary вместо /summaries)
        response = await client.get("/api/v1/chats/888888/summary?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    async def test_get_chat_summaries_paginated(self, client: AsyncClient, db_pool):
        """Получение summary с пагинацией."""
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_settings (chat_id, title, type)
                VALUES (888889, 'Test Pagination', 'private')
                ON CONFLICT (chat_id) DO NOTHING
            """)

            now = datetime.now(timezone.utc)
            for i in range(10):
                period_start = now - timedelta(hours=i + 1)
                await conn.execute("""
                    INSERT INTO chat_summaries
                    (chat_id, period_start, period_end, summary_text, messages_count)
                    VALUES ($1, $2, $3, $4, $5)
                """, 888889, period_start, now, f"Summary {i}", 10)

        response = await client.get("/api/v1/chats/888889/summary?limit=5&offset=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    async def test_get_latest_summary(self, client: AsyncClient, db_pool):
        """Получение последнего summary."""
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_settings (chat_id, title, type)
                VALUES (777777, 'Test Latest', 'private')
                ON CONFLICT (chat_id) DO NOTHING
            """)

            now = datetime.now(timezone.utc)
            await conn.execute("""
                INSERT INTO chat_summaries
                (chat_id, period_start, period_end, summary_text, messages_count)
                VALUES ($1, $2, $3, $4, $5)
            """, 777777, now - timedelta(hours=24), now, "Latest summary", 20)

        response = await client.get("/api/v1/chats/777777/summary/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["summary_text"] == "Latest summary"
        assert data["messages_count"] == 20

    async def test_get_latest_summary_not_found(self, client: AsyncClient):
        """Summary не найдено."""
        response = await client.get(
            "/api/v1/chats/999999/summary/latest"
        )

        assert response.status_code == 404


class TestGetSummaryById:
    """Тесты получения summary по ID."""

    async def test_get_summary_by_id(self, client: AsyncClient, db_pool):
        """Получение summary по ID."""
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_settings (chat_id, title, type)
                VALUES (666666, 'Test By ID', 'private')
                ON CONFLICT (chat_id) DO NOTHING
            """)

            now = datetime.now(timezone.utc)
            result = await conn.fetchrow("""
                INSERT INTO chat_summaries
                (chat_id, period_start, period_end, summary_text, messages_count)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, 666666, now - timedelta(hours=12), now, "Summary by ID", 15)

            summary_id = result["id"]

        response = await client.get(
            f"/api/v1/chats/666666/summary/{summary_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == summary_id
        assert data["summary_text"] == "Summary by ID"

    async def test_get_summary_wrong_chat_id(self, client: AsyncClient, db_pool):
        """Summary не принадлежит указанному чату."""
        async with db_pool.acquire() as conn:
            now = datetime.now(timezone.utc)
            result = await conn.fetchrow("""
                INSERT INTO chat_summaries
                (chat_id, period_start, period_end, summary_text, messages_count)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, 555555, now - timedelta(hours=6), now, "Wrong chat", 8)

            summary_id = result["id"]

        response = await client.get(
            f"/api/v1/chats/999999/summary/{summary_id}"
        )

        assert response.status_code == 400


class TestDeleteSummary:
    """Тесты удаления summary."""

    async def test_delete_summary_success(self, client: AsyncClient, db_pool):
        """Успешное удаление summary."""
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_settings (chat_id, title, type)
                VALUES (444444, 'Test Delete', 'private')
                ON CONFLICT (chat_id) DO NOTHING
            """)

            now = datetime.now(timezone.utc)
            result = await conn.fetchrow("""
                INSERT INTO chat_summaries
                (chat_id, period_start, period_end, summary_text, messages_count)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, 444444, now - timedelta(hours=3), now, "To delete", 5)

            summary_id = result["id"]

        response = await client.delete(
            f"/api/v1/chats/444444/summary/{summary_id}"
        )

        assert response.status_code == 200

        # Проверяем что удалено
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) as count FROM chat_summaries WHERE id = $1",
                summary_id,
            )
            assert row["count"] == 0


class TestCleanupSummaries:
    """Тесты очистки summary."""

    async def test_cleanup_summaries(self, client: AsyncClient, db_pool):
        """Очистка старых summary."""
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_settings (chat_id, title, type)
                VALUES (333333, 'Test Cleanup', 'private')
                ON CONFLICT (chat_id) DO NOTHING
            """)

            now = datetime.now(timezone.utc)

            # Старое summary (60 дней назад)
            old_date = now - timedelta(days=60)
            await conn.execute("""
                INSERT INTO chat_summaries
                (chat_id, period_start, period_end, summary_text, messages_count)
                VALUES ($1, $2, $3, $4, $5)
            """, 333333, old_date - timedelta(hours=24), old_date, "Old", 5)

            # Новое summary
            await conn.execute("""
                INSERT INTO chat_summaries
                (chat_id, period_start, period_end, summary_text, messages_count)
                VALUES ($1, $2, $3, $4, $5)
            """, 333333, now - timedelta(hours=24), now, "New", 10)

        response = await client.post(
            "/api/v1/chats/333333/summary/cleanup",
            json={"older_than_days": 30},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 1
        assert "Удалено 1 summary" in data["message"]


class TestGetStats:
    """Тесты статистики."""

    async def test_get_summaries_stats(self, client: AsyncClient, db_pool):
        """Получение статистики по summary."""
        async with db_pool.acquire() as conn:
            now = datetime.now(timezone.utc)

            for chat_id in [123456, 654321]:
                await conn.execute("""
                    INSERT INTO chat_settings (chat_id, title, type)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (chat_id) DO NOTHING
                """, chat_id, f"Chat {chat_id}", "private")

                for i in range(3):
                    period_start = now - timedelta(hours=i + 1)
                    await conn.execute("""
                        INSERT INTO chat_summaries
                        (chat_id, period_start, period_end, summary_text, messages_count)
                        VALUES ($1, $2, $3, $4, $5)
                    """, chat_id, period_start, now, f"Stat {i}", 10 + i)

        response = await client.get("/api/v1/chats/summary/stats")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

        chat_stats = {s["chat_id"]: s for s in data}
        assert 123456 in chat_stats
        assert chat_stats[123456]["total_summaries"] == 3


class TestGenerateSummary:
    """Тесты генерации summary."""

    async def test_generate_summary_for_chat(self, client: AsyncClient):
        """Генерация summary для одного чата."""
        # Тест требует настроенного RAG сервиса, поэтому проверяем только структуру
        response = await client.post(
            "/api/v1/chats/-1001234567890/summary/generate",
            json={"period_minutes": 60}
        )
        # Может вернуть 503 если RAG недоступен, или 404 если нет сообщений
        assert response.status_code in [200, 404, 503]

    async def test_generate_summary_with_custom_period(self, client: AsyncClient):
        """Генерация с явным указанием периода."""
        response = await client.post(
            "/api/v1/chats/-1001234567890/summary/generate",
            json={
                "period_start": "2026-03-14T10:00:00Z",
                "period_end": "2026-03-14T12:00:00Z"
            }
        )
        assert response.status_code in [200, 404, 503]

    async def test_generate_summary_force_regenerate(self, client: AsyncClient):
        """Принудительная генерация (игнорирование кэша)."""
        response = await client.post(
            "/api/v1/chats/-1001234567890/summary/generate",
            json={"force_regenerate": True, "period_minutes": 60}
        )
        assert response.status_code in [200, 404, 503]

    async def test_generate_summary_for_all_chats(self, client: AsyncClient):
        """Генерация для всех чатов."""
        response = await client.post(
            "/api/v1/chats/summary/generate",
            json={"period_minutes": 60}
        )
        # Может вернуть 200 с пустым списком или 503 если RAG недоступен
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert "summaries" in data
            assert "total_chats" in data
            assert "successful" in data
            assert "failed" in data
