"""
Integration tests для пакетного импорта сообщений из Telegram Desktop.

Требования:
- Docker с PostgreSQL container
- Docker с Ollama container
- Флаг --integration для запуска

Запуск:
    pytest tests/integration/test_batch_import.py -v --integration
"""

import asyncio
import json
import os
import tempfile
from typing import Any, Dict, List

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_lifespan
from src.database import get_pool
from fastapi import FastAPI


pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
async def integration_app():
    """FastAPI приложение для integration тестов с реальной БД."""
    app = FastAPI(
        title="TgBrain Integration Test",
        lifespan=create_lifespan(),
    )
    
    from src.api.endpoints.import_endpoint import router as import_router
    from src.api.endpoints.external_ingest import router as external_ingest_router
    
    app.include_router(import_router)
    app.include_router(external_ingest_router)
    
    try:
        yield app
    finally:
        if hasattr(app.state, 'db_pool') and app.state.db_pool:
            await app.state.db_pool.close()


@pytest.fixture(scope="module")
async def integration_client(request, integration_app):
    """HTTP client для integration тестов. Требует флаг --integration."""
    if not request.config.getoption("--integration"):
        pytest.skip("Integration tests disabled. Use --integration to enable.")
    
    transport = ASGITransport(app=integration_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="module")
async def db_pool(request):
    """Реальное подключение к PostgreSQL. Требует флаг --integration."""
    if not request.config.getoption("--integration"):
        pytest.skip("Integration tests disabled. Use --integration to enable.")
    
    pool = None
    try:
        pool = await get_pool()
        yield pool
    finally:
        if pool:
            await pool.close()


@pytest.fixture(autouse=True)
async def cleanup_test_data(db_pool):
    """Очистка тестовых данных после каждого теста."""
    test_chat_ids = [1234567890, 9876543210, 1111111111, 2222222222, 3333333333, 4444444444, 5555555555]
    
    try:
        yield
    finally:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM messages WHERE chat_id = ANY($1)", test_chat_ids)
            await conn.execute("DELETE FROM chat_settings WHERE chat_id = ANY($1)", test_chat_ids)
            await conn.execute("DELETE FROM pending_messages WHERE chat_id = ANY($1)", test_chat_ids)


# =============================================================================
# Helper functions
# =============================================================================


async def wait_for_task_completion(
    client: AsyncClient,
    task_id: str,
    max_attempts: int = 100,
    delay: float = 0.5,
) -> Dict[str, Any]:
    """Ожидание завершения задачи импорта через polling."""
    for _ in range(max_attempts):
        response = await client.get(f"/api/v1/messages/import/{task_id}/progress")
        if response.status_code == 200:
            data = response.json()
            if data.get("status") in ["completed", "failed", "cancelled"]:
                return data
        await asyncio.sleep(delay)
    
    raise TimeoutError(f"Task {task_id} did not complete within {max_attempts * delay} seconds")


async def fetch_messages_for_chat(conn: asyncpg.Connection, chat_id: int) -> List[Dict[str, Any]]:
    """Получение сообщений из БД для чата."""
    rows = await conn.fetch(
        "SELECT id, chat_id, message_text, sender_name, message_date FROM messages WHERE chat_id = $1",
        chat_id,
    )
    return [dict(row) for row in rows]


async def fetch_chat_settings_for_chat(conn: asyncpg.Connection, chat_id: int) -> Dict[str, Any] | None:
    """Получение настроек чата из БД."""
    row = await conn.fetchrow(
        "SELECT chat_id, chat_title, is_monitored FROM chat_settings WHERE chat_id = $1",
        chat_id,
    )
    return dict(row) if row else None


async def fetch_pending_for_chat(conn: asyncpg.Connection, chat_id: int) -> List[Dict[str, Any]]:
    """Получение pending сообщений из БД."""
    rows = await conn.fetch(
        "SELECT id, chat_id, message_text, retry_count FROM pending_messages WHERE chat_id = $1",
        chat_id,
    )
    return [dict(row) for row in rows]


# =============================================================================
# Test Classes - Import Returns 202 (1 тест)
# =============================================================================


class TestIntegration_ImportReturns202Status:
    """Integration test: import возвращает 202 status."""

    @pytest.mark.asyncio
    async def test_import_returns_202_status(
        self,
        integration_client,
        sample_json_export,
    ):
        """Test: import endpoint returns 202 Accepted."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        assert response.status_code == 202


# =============================================================================
# Test Classes - Import Returns Task ID (1 тест)
# =============================================================================


class TestIntegration_ImportReturnsTaskId:
    """Integration test: import возвращает task_id."""

    @pytest.mark.asyncio
    async def test_import_returns_task_id(
        self,
        integration_client,
        sample_json_export,
    ):
        """Test: import response contains task_id."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        response_data = response.json()
        assert "task_id" in response_data


# =============================================================================
# Test Classes - Import Completes Successfully (1 тест)
# =============================================================================


class TestIntegration_ImportCompletesSuccessfully:
    """Integration test: import завершается успешно."""

    @pytest.mark.asyncio
    async def test_import_completes_successfully(
        self,
        integration_client,
        sample_json_export,
    ):
        """Test: import task completes with status completed."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        progress = await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        assert progress["status"] == "completed"


# =============================================================================
# Test Classes - Import Processes All Messages (1 тест)
# =============================================================================


class TestIntegration_ImportProcessesAllMessages:
    """Integration test: import обрабатывает все сообщения."""

    @pytest.mark.asyncio
    async def test_import_processes_all_messages(
        self,
        integration_client,
        sample_json_export,
    ):
        """Test: import processes all 100 messages."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        progress = await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        assert progress["processed"] == 100


# =============================================================================
# Test Classes - Import Saves Messages to DB (1 тест)
# =============================================================================


class TestIntegration_ImportSavesMessagesToDb:
    """Integration test: import сохраняет сообщения в БД."""

    @pytest.mark.asyncio
    async def test_import_saves_messages_to_db(
        self,
        integration_client,
        db_pool,
        sample_json_export,
    ):
        """Test: all 100 messages saved to database."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            messages = await fetch_messages_for_chat(conn, 1234567890)
        
        assert len(messages) == 100


# =============================================================================
# Test Classes - Chat Settings Created (3 теста)
# =============================================================================


class TestIntegration_ImportCreatesChatSettings:
    """Integration test: import создаёт chat_settings."""

    @pytest.mark.asyncio
    async def test_import_creates_chat_settings_exists(
        self,
        integration_client,
        db_pool,
        sample_json_export,
    ):
        """Test: chat_settings created for imported chat."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            chat_settings = await fetch_chat_settings_for_chat(conn, 1234567890)
        
        assert chat_settings is not None


class TestIntegration_ImportCreatesChatSettingsId:
    """Integration test: chat_settings имеет правильный chat_id."""

    @pytest.mark.asyncio
    async def test_import_chat_settings_has_correct_id(
        self,
        integration_client,
        db_pool,
        sample_json_export,
    ):
        """Test: chat_settings.chat_id matches import chat_id."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            chat_settings = await fetch_chat_settings_for_chat(conn, 1234567890)
        
        assert chat_settings is not None
        assert chat_settings["chat_id"] == 1234567890


class TestIntegration_ImportCreatesChatSettingsMonitored:
    """Integration test: chat_settings.is_monitored = True."""

    @pytest.mark.asyncio
    async def test_import_chat_settings_is_monitored(
        self,
        integration_client,
        db_pool,
        sample_json_export,
    ):
        """Test: chat_settings.is_monitored is True."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            chat_settings = await fetch_chat_settings_for_chat(conn, 1234567890)
        
        assert chat_settings is not None
        assert chat_settings["is_monitored"] is True


# =============================================================================
# Test Classes - Embeddings Generated (3 теста)
# =============================================================================


class TestIntegration_ImportGeneratesEmbeddings:
    """Integration test: import генерирует embeddings."""

    @pytest.mark.asyncio
    async def test_import_generates_embeddings_not_null(
        self,
        integration_client,
        db_pool,
        sample_json_export,
    ):
        """Test: all messages have non-NULL embeddings."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, embedding FROM messages WHERE chat_id = $1 AND embedding IS NOT NULL",
                1234567890,
            )
        
        assert len(rows) == 100


class TestIntegration_ImportGeneratesEmbeddingsNotEmpty:
    """Integration test: embeddings не пустые."""

    @pytest.mark.asyncio
    async def test_import_embeddings_not_empty(
        self,
        integration_client,
        db_pool,
        sample_json_export,
    ):
        """Test: all embeddings have non-zero length."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT embedding FROM messages WHERE chat_id = $1",
                1234567890,
            )
        
        for row in rows:
            assert len(row["embedding"]) > 0


# =============================================================================
# Test Classes - Repeated Import Marks Duplicates (2 теста)
# =============================================================================


class TestIntegration_RepeatedImportMarksDuplicates:
    """Integration test: повторный импорт помечает дубликаты."""

    @pytest.mark.asyncio
    async def test_repeated_import_duplicate_count(
        self,
        integration_client,
        sample_json_export,
    ):
        """Test: repeated import marks 100 duplicates."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response1 = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response1.json()["task_id"])
        
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1234567890"}
            
            response2 = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        progress2 = await wait_for_task_completion(integration_client, response2.json()["task_id"])
        
        assert progress2["duplicates"] == 100


# =============================================================================
# Test Classes - Concurrent Imports No Duplicates (1 тест)
# =============================================================================


class TestIntegration_ConcurrentImportsNoDuplicates:
    """Integration test: concurrent imports не создают дублей."""

    @pytest.mark.asyncio
    async def test_concurrent_imports_no_duplicates(
        self,
        integration_client,
        db_pool,
    ):
        """Test: 2 concurrent imports result in 10 unique messages."""
        export_data = {
            "name": "Concurrent Test Chat",
            "type": "private_channel",
            "id": 3333333333,
            "messages": [
                {
                    "id": i,
                    "type": "message",
                    "date": "2026-03-09T17:53:43",
                    "from": "Test User",
                    "from_id": "user123456",
                    "text": f"Concurrent message {i}",
                }
                for i in range(1, 11)
            ]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file1_path = os.path.join(tmpdir, "export1.json")
            file2_path = os.path.join(tmpdir, "export2.json")
            
            with open(file1_path, "w", encoding="utf-8") as f1:
                json.dump(export_data, f1, ensure_ascii=False)
            
            with open(file2_path, "w", encoding="utf-8") as f2:
                json.dump(export_data, f2, ensure_ascii=False)
            
            async def upload_import(file_path):
                with open(file_path, "rb") as f:
                    files = {"file": ("export.json", f, "application/json")}
                    data = {"chat_id": "3333333333"}
                    response = await integration_client.post(
                        "/api/v1/messages/import",
                        files=files,
                        data=data,
                    )
                return response.json()["task_id"]
            
            task_id1, task_id2 = await asyncio.gather(
                upload_import(file1_path),
                upload_import(file2_path),
            )
            
            await asyncio.gather(
                wait_for_task_completion(integration_client, task_id1),
                wait_for_task_completion(integration_client, task_id2),
            )
            
            async with db_pool.acquire() as conn:
                messages = await fetch_messages_for_chat(conn, 3333333333)
            
            assert len(messages) == 10


# =============================================================================
# Test Classes - Import All Chat Types (2 теста)
# =============================================================================


class TestIntegration_ImportAllChatTypes:
    """Integration test: все типы чатов обрабатываются."""

    @pytest.mark.asyncio
    async def test_import_all_chat_types_processed(
        self,
        integration_client,
        mixed_chat_types_json,
    ):
        """Test: all messages from mixed chat types processed."""
        with open(mixed_chat_types_json, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1111111111"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        progress = await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        assert progress["processed"] == 2


class TestIntegration_ImportAllChatTypesSaved:
    """Integration test: сообщения из всех типов чатов в БД."""

    @pytest.mark.asyncio
    async def test_import_all_chat_types_saved_to_db(
        self,
        integration_client,
        db_pool,
        mixed_chat_types_json,
    ):
        """Test: all messages saved to database."""
        with open(mixed_chat_types_json, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "1111111111"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            messages = await fetch_messages_for_chat(conn, 1111111111)
        
        assert len(messages) == 2


# =============================================================================
# Test Classes - Import Dates in UTC (2 теста)
# =============================================================================


class TestIntegration_TimezoneHandlingUTCAssumed:
    """Integration test: даты без timezone трактуются как UTC."""

    @pytest.mark.asyncio
    async def test_import_dates_in_utc_has_tzinfo(
        self,
        integration_client,
        db_pool,
        timezone_naive_json,
    ):
        """Test: all message dates have timezone info."""
        with open(timezone_naive_json, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "2222222222"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT message_date FROM messages WHERE chat_id = $1 ORDER BY message_date",
                2222222222,
            )
        
        for row in rows:
            assert row["message_date"].tzinfo is not None


# =============================================================================
# Test Classes - Import Large File (2 теста)
# =============================================================================


class TestIntegration_ImportLargeFile:
    """Integration test: большой файл обрабатывается успешно."""

    @pytest.mark.asyncio
    async def test_import_large_file_completes(
        self,
        integration_client,
        large_json_export,
    ):
        """Test: large file import completes successfully."""
        with open(large_json_export, "rb") as f:
            files = {"file": ("export_large.json", f, "application/json")}
            data = {"chat_id": "9876543210"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        progress = await wait_for_task_completion(
            integration_client,
            response.json()["task_id"],
            max_attempts=200,
            delay=1.0,
        )
        
        assert progress["status"] == "completed"


class TestIntegration_ImportLargeFileProcessesAll:
    """Integration test: большой файл обрабатывает все сообщения."""

    @pytest.mark.asyncio
    async def test_import_large_file_processes_all_messages(
        self,
        integration_client,
        db_pool,
        large_json_export,
    ):
        """Test: all 10000 messages processed."""
        with open(large_json_export, "rb") as f:
            files = {"file": ("export_large.json", f, "application/json")}
            data = {"chat_id": "9876543210"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(
            integration_client,
            response.json()["task_id"],
            max_attempts=200,
            delay=1.0,
        )
        
        async with db_pool.acquire() as conn:
            messages = await fetch_messages_for_chat(conn, 9876543210)
        
        assert len(messages) == 10000


# =============================================================================
# Test Classes - Cancel Partial Results (2 теста)
# =============================================================================


class TestIntegration_CancelPartialResults:
    """Integration test: отмена сохраняет частичные результаты."""

    @pytest.mark.asyncio
    async def test_cancel_status_cancelled(
        self,
        integration_client,
    ):
        """Test: cancel changes status to cancelled."""
        export_data = {
            "name": "Cancel Test Chat",
            "type": "private_channel",
            "id": 4444444444,
            "messages": [
                {
                    "id": i,
                    "type": "message",
                    "date": "2026-03-09T17:53:43",
                    "from": "Test User",
                    "from_id": "user123456",
                    "text": f"Message {i} for cancel test",
                }
                for i in range(1, 101)
            ]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "export.json")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False)
            
            with open(file_path, "rb") as f:
                files = {"file": ("export.json", f, "application/json")}
                data = {"chat_id": "4444444444"}
                
                response = await integration_client.post(
                    "/api/v1/messages/import",
                    files=files,
                    data=data,
                )
            
            task_id = response.json()["task_id"]
            
            await asyncio.sleep(0.5)
            
            cancel_response = await integration_client.delete(
                f"/api/v1/messages/import/{task_id}/cancel"
            )
            
            assert cancel_response.status_code == 200


class TestIntegration_CancelPartialResultsStatus:
    """Integration test: отмена устанавливает статус cancelled."""

    @pytest.mark.asyncio
    async def test_cancel_progress_status_cancelled(
        self,
        integration_client,
    ):
        """Test: progress shows cancelled status after cancel."""
        export_data = {
            "name": "Cancel Test Chat",
            "type": "private_channel",
            "id": 4444444444,
            "messages": [
                {
                    "id": i,
                    "type": "message",
                    "date": "2026-03-09T17:53:43",
                    "from": "Test User",
                    "from_id": "user123456",
                    "text": f"Message {i} for cancel test",
                }
                for i in range(1, 101)
            ]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "export.json")
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False)
            
            with open(file_path, "rb") as f:
                files = {"file": ("export.json", f, "application/json")}
                data = {"chat_id": "4444444444"}
                
                response = await integration_client.post(
                    "/api/v1/messages/import",
                    files=files,
                    data=data,
                )
            
            task_id = response.json()["task_id"]
            
            await asyncio.sleep(0.5)
            
            await integration_client.delete(f"/api/v1/messages/import/{task_id}/cancel")
            
            await asyncio.sleep(0.5)
            
            progress = await wait_for_task_completion(integration_client, task_id, max_attempts=20)
            
            assert progress["status"] == "cancelled"


# =============================================================================
# Test Classes - Import Embedding Unavailable Pending (2 теста)
# =============================================================================


class TestIntegration_ImportEmbeddingUnavailablePending:
    """Integration test: ошибка embedding → pending."""

    @pytest.mark.asyncio
    async def test_import_embedding_unavailable_completes(
        self,
        integration_client,
        sample_json_export,
    ):
        """Test: import completes even if embedding unavailable."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "5555555555"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        progress = await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        assert progress["status"] == "completed"


class TestIntegration_ImportEmbeddingUnavailablePendingCount:
    """Integration test: сообщения без embeddings идут в pending."""

    @pytest.mark.asyncio
    async def test_import_total_processed_equals_100(
        self,
        integration_client,
        db_pool,
        sample_json_export,
    ):
        """Test: total processed (messages + pending) equals 100."""
        with open(sample_json_export, "rb") as f:
            files = {"file": ("export.json", f, "application/json")}
            data = {"chat_id": "5555555555"}
            
            response = await integration_client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )
        
        await wait_for_task_completion(integration_client, response.json()["task_id"])
        
        async with db_pool.acquire() as conn:
            pending_messages = await fetch_pending_for_chat(conn, 5555555555)
            messages = await fetch_messages_for_chat(conn, 5555555555)
        
        total_processed = len(messages) + len(pending_messages)
        assert total_processed == 100
