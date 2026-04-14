"""Тесты для BatchImportFileService."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.batch_import.file_service import (
    MAX_FILE_MESSAGES,
    MAX_FILE_SIZE_BYTES,
    BatchImportFileService,
)
from src.batch_import.json_validator import JsonValidationError


@pytest.fixture
def file_service() -> BatchImportFileService:
    """Фикстура сервиса файлов."""
    return BatchImportFileService()


class TestBatchImportFileServiceInit:
    """Тесты инициализации BatchImportFileService."""

    def test_init(self, file_service: BatchImportFileService) -> None:
        """Сервис создаётся без ошибок."""
        assert file_service is not None


class TestSaveFileToTemp:
    """Тесты сохранения файла во временное хранилище."""

    async def test_save_file_to_temp_success(self, file_service: BatchImportFileService, tmp_path: Path) -> None:
        """Успешное сохранение файла."""
        content = b'{"name": "test", "type": "private", "id": 1, "messages": []}'
        file_id = "test-uuid-123"
        file_size = len(content)

        with patch("tempfile.gettempdir", return_value=str(tmp_path)):
            result = await file_service.save_file_to_temp(content, file_id, file_size)

        expected_path = str(tmp_path / "batch_imports" / f"{file_id}.json")
        assert result == expected_path
        assert Path(result).exists()
        assert Path(result).read_bytes() == content

    async def test_save_file_to_temp_too_large(self, file_service: BatchImportFileService) -> None:
        """Файл больше 500MB вызывает ValueError."""
        large_size = MAX_FILE_SIZE_BYTES + 1

        with pytest.raises(ValueError) as exc_info:
            await file_service.save_file_to_temp(b"test", "uuid", large_size)

        assert "File too large" in str(exc_info.value)

    async def test_save_file_to_temp_creates_directory(
        self, file_service: BatchImportFileService, tmp_path: Path,
    ) -> None:
        """Метод создаёт директорию batch_imports если её нет."""
        content = b'{"messages": []}'

        with patch("tempfile.gettempdir", return_value=str(tmp_path)):
            await file_service.save_file_to_temp(content, "uuid", len(content))

        batch_imports_dir = tmp_path / "batch_imports"
        assert batch_imports_dir.exists()


class TestValidateFileContent:
    """Тесты валидации содержимого файла."""

    def test_validate_file_content_valid(self, file_service: BatchImportFileService, tmp_path: Path) -> None:
        """Валидный файл проходит проверку."""
        data = {"name": "Test", "type": "private", "id": 1, "messages": [{"id": 1}]}
        file_path = tmp_path / "valid.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        result = file_service.validate_file_content(str(file_path))

        assert result is True

    def test_validate_file_content_empty(self, file_service: BatchImportFileService, tmp_path: Path) -> None:
        """Пустой файл вызывает ValueError."""
        file_path = tmp_path / "empty.json"
        file_path.write_text("", encoding="utf-8")

        with pytest.raises(ValueError) as exc_info:
            file_service.validate_file_content(str(file_path))

        assert "Empty file" in str(exc_info.value)

    def test_validate_file_content_invalid_json(self, file_service: BatchImportFileService, tmp_path: Path) -> None:
        """Невалидный JSON вызывает ValueError."""
        file_path = tmp_path / "invalid.json"
        file_path.write_text("not json at all {{{", encoding="utf-8")

        with pytest.raises(ValueError) as exc_info:
            file_service.validate_file_content(str(file_path))

        assert "Invalid JSON" in str(exc_info.value)

    def test_validate_file_content_missing_required_field(
        self, file_service: BatchImportFileService, tmp_path: Path,
    ) -> None:
        """Файл без required полей вызывает JsonValidationError."""
        data = {"name": "Test"}
        file_path = tmp_path / "incomplete.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(JsonValidationError):
            file_service.validate_file_content(str(file_path))

    def test_validate_file_content_too_many_messages(
        self, file_service: BatchImportFileService, tmp_path: Path,
    ) -> None:
        """Файл с превышением лимита сообщений вызывает ошибку."""
        data = {
            "name": "Test",
            "type": "private",
            "id": 1,
            "messages": [{"id": i} for i in range(MAX_FILE_MESSAGES + 1)],
        }
        file_path = tmp_path / "large.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        with pytest.raises(JsonValidationError):
            file_service.validate_file_content(str(file_path))


class TestCountMessagesInFile:
    """Тесты подсчёта сообщений в файле."""

    def test_count_messages_success(self, file_service: BatchImportFileService, tmp_path: Path) -> None:
        """Подсчёт сообщений в валидном файле."""
        data = {"name": "Test", "messages": [{"id": 1}, {"id": 2}, {"id": 3}]}
        file_path = tmp_path / "messages.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        result = file_service.count_messages_in_file(str(file_path))

        assert result == 3

    def test_count_messages_empty_list(self, file_service: BatchImportFileService, tmp_path: Path) -> None:
        """Пустой список сообщений возвращает 0."""
        data = {"name": "Test", "messages": []}
        file_path = tmp_path / "empty.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        result = file_service.count_messages_in_file(str(file_path))

        assert result == 0

    def test_count_messages_no_messages_key(self, file_service: BatchImportFileService, tmp_path: Path) -> None:
        """Отсутствие ключа messages возвращает 0."""
        data = {"name": "Test"}
        file_path = tmp_path / "no_msgs.json"
        file_path.write_text(json.dumps(data), encoding="utf-8")

        result = file_service.count_messages_in_file(str(file_path))

        assert result == 0

    def test_count_messages_error_returns_zero(self, file_service: BatchImportFileService) -> None:
        """Ошибка чтения файла возвращает 0."""
        result = file_service.count_messages_in_file("/nonexistent/path.json")

        assert result == 0


class TestExtractChatInfoFromFile:
    """Тесты извлечения информации о чате из файла."""

    def test_extract_chat_info_error_returns_none_tuple(
        self, file_service: BatchImportFileService,
    ) -> None:
        """Ошибка парсинга возвращает (None, None, None)."""
        result = file_service.extract_chat_info_from_file("/nonexistent/file.json")

        assert result == (None, None, None)
