"""Тесты для JsonValidator."""

import pytest

from src.batch_import.json_validator import (
    JsonValidationError,
    JsonValidator,
)


class TestJsonValidationError:
    """Тесты для исключения JsonValidationError."""

    def test_error_with_default_code(self) -> None:
        """Создание исключения с message и кодом по умолчанию."""
        error = JsonValidationError("Test error")

        assert error.message == "Test error"
        assert error.code == "JSON-001"

    def test_error_with_custom_code(self) -> None:
        """Создание исключения с message и кастомным кодом."""
        error = JsonValidationError("Test error", "JSON-005")

        assert error.message == "Test error"
        assert error.code == "JSON-005"

    def test_error_is_value_error(self) -> None:
        """JsonValidationError наследует от ValueError."""
        error = JsonValidationError("Test error")

        assert isinstance(error, ValueError)
        assert str(error) == "Test error"


class TestValidateStructure:
    """Тесты для JsonValidator.validate_structure."""

    def test_valid_structure(self) -> None:
        """Валидная структура JSON проходит без ошибок."""
        data = {
            "name": "Test Chat",
            "type": "private",
            "id": 1234567890,
            "messages": [],
        }

        JsonValidator.validate_structure(data)

    def test_none_data(self) -> None:
        """None проходит валидацию (необязательный параметр)."""
        JsonValidator.validate_structure(None)

    def test_not_dict_raises_json001(self) -> None:
        """Не-dict значение вызывает JSON-001."""
        with pytest.raises(JsonValidationError) as exc_info:
            JsonValidator.validate_structure([1, 2, 3])  # type: ignore[arg-type]

        assert exc_info.value.code == "JSON-001"
        assert "Root must be an object" in str(exc_info.value.message)

    def test_missing_required_field_raises_json002(self) -> None:
        """Отсутствующее required поле вызывает JSON-002."""
        data = {"name": "Test Chat"}

        with pytest.raises(JsonValidationError) as exc_info:
            JsonValidator.validate_structure(data)

        assert exc_info.value.code == "JSON-002"
        assert "Missing required field: type" in str(exc_info.value.message)

    def test_messages_not_list_raises_json003(self) -> None:
        """messages не list вызывает JSON-003."""
        data = {
            "name": "Test Chat",
            "type": "private",
            "id": 1234567890,
            "messages": "not a list",
        }

        with pytest.raises(JsonValidationError) as exc_info:
            JsonValidator.validate_structure(data)

        assert exc_info.value.code == "JSON-003"
        assert "messages must be an array" in str(exc_info.value.message)

    def test_empty_messages_allowed(self) -> None:
        """Пустой список messages разрешён."""
        data = {
            "name": "Test Chat",
            "type": "group",
            "id": 999,
            "messages": [],
        }

        JsonValidator.validate_structure(data)


class TestValidateChatType:
    """Тесты для JsonValidator.validate_chat_type."""

    def test_valid_chat_type_private(self) -> None:
        """Валидный тип private проходит."""
        JsonValidator.validate_chat_type("private")

    def test_valid_chat_type_group(self) -> None:
        """Валидный тип group проходит."""
        JsonValidator.validate_chat_type("group")

    def test_valid_chat_type_channel(self) -> None:
        """Валидный тип channel проходит."""
        JsonValidator.validate_chat_type("channel")

    def test_valid_chat_type_supergroup(self) -> None:
        """Валидный тип supergroup проходит."""
        JsonValidator.validate_chat_type("supergroup")

    def test_valid_chat_type_private_channel(self) -> None:
        """Валидный тип private_channel проходит."""
        JsonValidator.validate_chat_type("private_channel")

    def test_valid_chat_type_personal_chat(self) -> None:
        """Валидный тип personal_chat проходит."""
        JsonValidator.validate_chat_type("personal_chat")

    def test_invalid_chat_type_raises_json004(self) -> None:
        """Невалидный тип вызывает JSON-004."""
        with pytest.raises(JsonValidationError) as exc_info:
            JsonValidator.validate_chat_type("unknown_type")

        assert exc_info.value.code == "JSON-004"
        assert "Invalid chat type: unknown_type" in str(exc_info.value.message)


class TestValidateMessageCount:
    """Тесты для JsonValidator.validate_message_count."""

    def test_valid_count(self) -> None:
        """Допустимое количество сообщений проходит."""
        JsonValidator.validate_message_count(100, 1000)

    def test_count_equal_to_max(self) -> None:
        """Количество равное максимуму проходит."""
        JsonValidator.validate_message_count(1000, 1000)

    def test_count_zero(self) -> None:
        """Нулевое количество сообщений проходит."""
        JsonValidator.validate_message_count(0, 1000)

    def test_count_exceeded_raises_json005(self) -> None:
        """Превышение лимита вызывает JSON-005."""
        with pytest.raises(JsonValidationError) as exc_info:
            JsonValidator.validate_message_count(1001, 1000)

        assert exc_info.value.code == "JSON-005"
        assert "Too many messages: 1001 (max 1000)" in str(exc_info.value.message)


class TestValidateFull:
    """Тесты для JsonValidator.validate_full."""

    def test_full_valid(self) -> None:
        """Полная валидация валидных данных проходит."""
        data = {
            "name": "Test Chat",
            "type": "private",
            "id": 1234567890,
            "messages": [{"id": 1, "text": "Hello"}],
        }

        JsonValidator.validate_full(data, max_messages=100)

    def test_full_none_data(self) -> None:
        """Полная валидация None проходит."""
        JsonValidator.validate_full(None, max_messages=100)

    def test_full_valid_with_all_fields(self) -> None:
        """Полная валидация с полями type и messages проходит."""
        data = {
            "name": "Test Chat",
            "type": "private",
            "id": 1234567890,
            "messages": [{"id": 1}],
        }

        JsonValidator.validate_full(data, max_messages=100)

    def test_full_invalid_type_raises_json004(self) -> None:
        """Полная валидация с невалидным типом вызывает JSON-004."""
        data = {
            "name": "Test Chat",
            "type": "invalid_type",
            "id": 1234567890,
            "messages": [],
        }

        with pytest.raises(JsonValidationError) as exc_info:
            JsonValidator.validate_full(data, max_messages=100)

        assert exc_info.value.code == "JSON-004"

    def test_full_count_exceeded_raises_json005(self) -> None:
        """Полная валидация с превышением лимита вызывает JSON-005."""
        data = {
            "name": "Test Chat",
            "type": "private",
            "id": 1234567890,
            "messages": [{"id": i} for i in range(101)],
        }

        with pytest.raises(JsonValidationError) as exc_info:
            JsonValidator.validate_full(data, max_messages=100)

        assert exc_info.value.code == "JSON-005"
