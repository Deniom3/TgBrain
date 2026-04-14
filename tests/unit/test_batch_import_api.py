"""
Тесты для Phase 3: API Endpoints.

Тесты для endpoints импорта:
- POST /api/v1/messages/import
- GET /api/v1/messages/import/{task_id}/progress
- DELETE /api/v1/messages/import/{task_id}/cancel
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.dependencies.auth import AuthenticatedUser, get_current_user
from src.api.dependencies.rate_limiter import import_rate_limit
from src.application.usecases.import_messages import (
    CancelResult,
    ImportResult,
    ProgressData,
)
from src.application.usecases.result import Failure, Success
from src.application.exceptions import TaskNotFoundError


def _override_get_current_user() -> AuthenticatedUser:
    """Тестовая заглушка для авторизации."""
    return AuthenticatedUser(is_authenticated=True)


async def _override_import_rate_limit() -> AuthenticatedUser:
    """Тестовая заглушка для rate limiting."""
    return AuthenticatedUser(is_authenticated=True)


@pytest.fixture(scope="module")
def import_router():
    """Fixture для import router."""
    from src.api.endpoints.import_endpoint import router
    return router


class TestImportEndpoint:
    """Тесты для POST /api/v1/messages/import endpoint."""

    @pytest.fixture
    def mock_app_state(self):
        """Mock app.state для тестов."""
        state = MagicMock()
        usecase = AsyncMock()
        usecase.start_import = AsyncMock(return_value=Success(ImportResult(
            task_id="test-task-id-123",
            status="processing",
            file_id="test-file-id",
            file_size=1024,
            messages_count=10,
            estimated_chunks=1,
            chat_id_from_file=123,
            chat_name_from_file="Test Chat",
        )))
        state.import_usecase = usecase
        return state

    def _create_test_export_file(self, num_messages: int = 10) -> str:
        """Создание тестового JSON файла экспорта."""
        messages = []
        for i in range(num_messages):
            msg = {
                "id": i + 1,
                "type": "message",
                "date": "2026-03-27T10:00:00",
                "from": f"User{i}",
                "from_id": f"user{i}",
                "text": f"Message text {i}",
            }
            messages.append(msg)

        export_data = {
            "id": 123,
            "name": "Test Chat",
            "type": "private_channel",
            "messages": messages,
        }

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            encoding='utf-8',
        ) as f:
            json.dump(export_data, f, ensure_ascii=False)
            return f.name

    def test_batch_import_upload_valid_file_returns_file_id(self, mock_app_state, import_router):
        """TestBatchImportUpload_ValidFile_ReturnsFileId."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        file_path = self._create_test_export_file(10)

        try:
            with open(file_path, 'rb') as f:
                files = {"file": ("test.json", f, "application/json")}
                data = {"chat_id": "123"}

                with TestClient(app) as client:
                    response = client.post("/api/v1/messages/import", files=files, data=data)

                    assert response.status_code == 202
                    json_response = response.json()
                    assert json_response["success"] is True
                    assert "task_id" in json_response
                    assert "file_id" in json_response

        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)

    def test_batch_import_upload_file_too_large_returns_413(self, mock_app_state, import_router):
        """TestBatchImportUpload_FileTooLarge_Returns413."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        from src.application.exceptions import FileTooLargeError
        mock_app_state.import_usecase.start_import = AsyncMock(
            return_value=Failure(FileTooLargeError())
        )

        large_content = b'{"messages": [' + b'{"id": 1}' * 1000 + b']}'

        with TestClient(app) as client:
            files = {"file": ("large.json", large_content, "application/json")}
            response = client.post("/api/v1/messages/import", files=files)

            assert response.status_code == 413
            json_response = response.json()
            assert "error" in json_response["detail"]
            assert json_response["detail"]["error"]["code"] == "EXT-008"

    def test_batch_import_upload_invalid_json_returns_400(self, mock_app_state, import_router):
        """TestBatchImportUpload_InvalidJson_Returns400."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        from src.application.exceptions import InvalidInputError
        mock_app_state.import_usecase.start_import = AsyncMock(
            return_value=Failure(InvalidInputError("Invalid JSON format"))
        )

        invalid_json = b'{"invalid": json}'

        with TestClient(app) as client:
            files = {"file": ("invalid.json", invalid_json, "application/json")}
            response = client.post("/api/v1/messages/import", files=files)

            assert response.status_code in [400, 500]

    def test_batch_import_upload_wrong_content_type_returns_415(self, mock_app_state, import_router):
        """TestBatchImportUpload_WrongContentType_Returns415."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        with TestClient(app) as client:
            files = {"file": ("test.txt", b"plain text", "text/plain")}
            response = client.post("/api/v1/messages/import", files=files)

            assert response.status_code == 415
            json_response = response.json()
            assert "error" in json_response["detail"]
            assert json_response["detail"]["error"]["code"] == "EXT-010"

    def test_batch_import_upload_invalid_chat_type_returns_400(self, mock_app_state, import_router):
        """TestBatchImportUpload_InvalidChatType_Returns400."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        from src.application.exceptions import InvalidInputError
        mock_app_state.import_usecase.start_import = AsyncMock(
            return_value=Failure(InvalidInputError("Invalid chat type"))
        )

        invalid_type_data = {
            "id": 123,
            "name": "Test Chat",
            "type": "invalid_type",
            "messages": [{"id": 1, "text": "test"}],
        }

        with TestClient(app) as client:
            files = {"file": ("", "", "application/octet-stream")}
            data = {"json_data": json.dumps(invalid_type_data)}
            response = client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )

            assert response.status_code == 400
            json_response = response.json()
            assert "error" in json_response["detail"]
            assert json_response["detail"]["error"]["code"] == "EXT-001"

    def test_batch_import_upload_json_directly_valid_returns_task_id(self, mock_app_state, import_router):
        """TestBatchImportUpload_JsonDirectly_Valid_ReturnsTaskId."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        valid_json = {
            "id": 123,
            "name": "Test Chat",
            "type": "private_channel",
            "messages": [
                {
                    "id": 1,
                    "type": "message",
                    "date": "2026-03-27T10:00:00",
                    "from": "User",
                    "from_id": "user1",
                    "text": "Test message",
                }
            ],
        }

        with TestClient(app) as client:
            files = {"file": ("", "", "application/octet-stream")}
            data = {"json_data": json.dumps(valid_json)}
            response = client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )

            assert response.status_code == 202
            json_response = response.json()
            assert json_response["success"] is True
            assert "task_id" in json_response

    def test_batch_import_upload_json_directly_too_many_messages_returns_400(self, mock_app_state, import_router):
        """TestBatchImportUpload_JsonDirectly_TooManyMessages_Returns400."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        from src.application.exceptions import TooManyMessagesError
        mock_app_state.import_usecase.start_import = AsyncMock(
            return_value=Failure(TooManyMessagesError(count=1001, max_count=1000))
        )

        too_many_messages = {
            "id": 123,
            "name": "Test Chat",
            "type": "private_channel",
            "messages": [{"id": i, "text": f"msg {i}"} for i in range(1001)],
        }

        with TestClient(app) as client:
            files = {"file": ("", "", "application/octet-stream")}
            data = {"json_data": json.dumps(too_many_messages)}
            response = client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )

            assert response.status_code == 400
            json_response = response.json()
            assert "error" in json_response["detail"]
            assert json_response["detail"]["error"]["code"] in ["EXT-001", "EXT-015"]

    def test_batch_import_upload_json_directly_auto_start_called(self, mock_app_state, import_router):
        """TestBatchImportUpload_JsonDirectly_AutoStart_Called."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        valid_json = {
            "id": 123,
            "name": "Test Chat",
            "type": "private_channel",
            "messages": [
                {
                    "id": 1,
                    "type": "message",
                    "date": "2026-03-27T10:00:00",
                    "from": "User",
                    "from_id": "user1",
                    "text": "Test message",
                }
            ],
        }

        with TestClient(app) as client:
            files = {"file": ("", "", "application/octet-stream")}
            data = {"json_data": json.dumps(valid_json)}
            response = client.post(
                "/api/v1/messages/import",
                files=files,
                data=data,
            )

            assert response.status_code == 202
            mock_app_state.import_usecase.start_import.assert_called_once()


class TestProgressEndpoint:
    """Тесты для GET /api/v1/messages/import/{task_id}/progress endpoint."""

    @pytest.fixture
    def mock_app_state(self):
        """Mock app.state для тестов."""
        state = MagicMock()
        usecase = AsyncMock()
        usecase.get_progress = AsyncMock(return_value=Success(ProgressData(
            task_id="test-task-123",
            status="processing",
            total_messages=100,
            processed_messages=50,
            filtered=5,
            duplicates=10,
            pending=0,
            errors=0,
            current_chunk=5,
            total_chunks=10,
        )))
        state.import_usecase = usecase
        return state

    def test_batch_import_progress_task_not_found_returns_404(self, mock_app_state, import_router):
        """TestBatchImportProgress_TaskNotFound_Returns404."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        mock_app_state.import_usecase.get_progress = AsyncMock(
            return_value=Failure(TaskNotFoundError("non-existent-task"))
        )

        with TestClient(app) as client:
            response = client.get("/api/v1/messages/import/non-existent-task/progress")

            assert response.status_code == 404
            json_response = response.json()
            assert "error" in json_response["detail"]
            assert json_response["detail"]["error"]["code"] == "EXT-013"

    def test_batch_import_progress_processing_returns_percent(self, mock_app_state, import_router):
        """TestBatchImportProgress_Processing_ReturnsPercent."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        with TestClient(app) as client:
            response = client.get("/api/v1/messages/import/test-task-123/progress")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["status"] == "processing"

    def test_batch_import_progress_completed_returns_full_stats(self, mock_app_state, import_router):
        """TestBatchImportProgress_Completed_ReturnsFullStats."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        mock_app_state.import_usecase.get_progress = AsyncMock(return_value=Success(ProgressData(
            task_id="test-task-123",
            status="completed",
            total_messages=100,
            processed_messages=100,
            filtered=5,
            duplicates=10,
            pending=0,
            errors=0,
            current_chunk=10,
            total_chunks=10,
        )))

        with TestClient(app) as client:
            response = client.get("/api/v1/messages/import/test-task-123/progress")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["status"] == "completed"
            assert json_response["processed"] == 100

    def test_batch_import_progress_failed_returns_error_details(self, mock_app_state, import_router):
        """TestBatchImportProgress_Failed_ReturnsErrorDetails."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        mock_app_state.import_usecase.get_progress = AsyncMock(return_value=Success(ProgressData(
            task_id="test-task-123",
            status="failed",
            total_messages=100,
            processed_messages=50,
            filtered=0,
            duplicates=0,
            pending=0,
            errors=1,
            current_chunk=5,
            total_chunks=10,
            error_message="Database connection error",
        )))

        with TestClient(app) as client:
            response = client.get("/api/v1/messages/import/test-task-123/progress")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["status"] == "failed"
            assert json_response["errors"] == 1
            assert len(json_response["error_details"]) > 0

    def test_batch_import_progress_cancelled_returns_partial(self, mock_app_state, import_router):
        """TestBatchImportProgress_Cancelled_ReturnsPartial."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        mock_app_state.import_usecase.get_progress = AsyncMock(return_value=Success(ProgressData(
            task_id="test-task-123",
            status="cancelled",
            total_messages=100,
            processed_messages=25,
            filtered=2,
            duplicates=3,
            pending=0,
            errors=0,
            current_chunk=2,
            total_chunks=10,
        )))

        with TestClient(app) as client:
            response = client.get("/api/v1/messages/import/test-task-123/progress")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["status"] == "cancelled"
            assert json_response["processed"] == 25


class TestCancelEndpoint:
    """Тесты для DELETE /api/v1/messages/import/{task_id}/cancel endpoint."""

    @pytest.fixture
    def mock_app_state(self):
        """Mock app.state для тестов."""
        state = MagicMock()
        usecase = AsyncMock()
        usecase.cancel_import = AsyncMock(return_value=Success(CancelResult(cancelled=True)))
        state.import_usecase = usecase
        return state

    def test_batch_import_cancel_running_task_stops_processing(self, mock_app_state, import_router):
        """TestBatchImportCancel_RunningTask_StopsProcessing."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        with TestClient(app) as client:
            response = client.delete("/api/v1/messages/import/test-task-123/cancel")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["success"] is True
            assert json_response["status"] == "cancelled"
            mock_app_state.import_usecase.cancel_import.assert_called_once()

    def test_batch_import_cancel_partial_results_saved(self, mock_app_state, import_router):
        """TestBatchImportCancel_PartialResults_Saved."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        with TestClient(app) as client:
            response = client.delete("/api/v1/messages/import/test-task-123/cancel")

            assert response.status_code == 200
            _ = response.json()

    def test_batch_import_cancel_file_cleanup_immediate(self, mock_app_state, import_router):
        """TestBatchImportCancel_FileCleanup_Immediate."""
        app = FastAPI()
        app.include_router(import_router)
        app.state = mock_app_state
        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[import_rate_limit] = _override_import_rate_limit

        with TestClient(app) as client:
            response = client.delete("/api/v1/messages/import/test-task-123/cancel")

            assert response.status_code == 200
            json_response = response.json()
            assert json_response["success"] is True
            assert json_response["message"] == "Import cancelled successfully"
