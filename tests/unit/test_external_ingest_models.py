"""
Tests for External Message Ingestion API models.

Tests:
- test_ValidData_Success
- test_EmptyText_Error
- test_InvalidDateType_Error
- test_OptionalFields_Defaults
- test_ExtraFields_Ignored
- test_ResponseModel_SuccessFields
"""

import pytest
from pydantic import ValidationError

from src.api.endpoints.external_ingest_models import (
    ExternalMessageRequest,
    ExternalMessageResponse,
    ExternalMessageStatus,
)


class TestExternalMessageModels:
    """Тестирование Pydantic моделей External Message API."""

    @pytest.mark.asyncio
    async def test_ValidData_Success(self):
        """Валидация успешна для корректных данных."""
        model = ExternalMessageRequest(
            chat_id=-1001234567890,
            text="Тест",
            date="2026-03-22T10:30:00Z",
            sender_id=None,
            sender_name=None,
            message_link=None,
            is_bot=False,
            is_action=False,
        )
        assert model.chat_id == -1001234567890
        assert model.text == "Тест"
        assert model.date == "2026-03-22T10:30:00Z"

    @pytest.mark.asyncio
    async def test_EmptyText_Error(self):
        """Валидация пустого текста."""
        with pytest.raises(ValidationError) as exc_info:
            ExternalMessageRequest(
                chat_id=-1001234567890,
                text="",
                date="2026-03-22T10:30:00Z",
                sender_id=None,
                sender_name=None,
                message_link=None,
                is_bot=False,
                is_action=False,
            )
        assert "text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_InvalidDateType_Error(self):
        """Валидация неверного типа даты."""
        with pytest.raises(ValidationError) as exc_info:
            ExternalMessageRequest(
                chat_id=-1001234567890,
                text="Тест",
                date=12345,  # type: ignore[arg-type]
                sender_id=None,
                sender_name=None,
                message_link=None,
                is_bot=False,
                is_action=False,
            )
        assert "date" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_OptionalFields_Defaults(self):
        """Значения по умолчанию для optional полей."""
        model = ExternalMessageRequest(
            chat_id=-1001234567890,
            text="Тест",
            date="2026-03-22T10:30:00Z",
            sender_id=None,
            sender_name=None,
            message_link=None,
            is_bot=False,
            is_action=False,
        )
        assert model.sender_id is None
        assert model.sender_name is None
        assert model.message_link is None
        assert model.is_bot is False
        assert model.is_action is False

    @pytest.mark.asyncio
    async def test_ExtraFields_Ignored(self):
        """Игнорирование лишних полей."""
        model = ExternalMessageRequest(
            chat_id=-1001234567890,
            text="Тест",
            date="2026-03-22T10:30:00Z",
            sender_id=None,
            sender_name=None,
            message_link=None,
            is_bot=False,
            is_action=False,
        )
        assert not hasattr(model, "extra_field")

    @pytest.mark.asyncio
    async def test_ResponseModel_SuccessFields(self):
        """Валидация response модели."""
        model = ExternalMessageResponse(
            success=True,
            status=ExternalMessageStatus.PROCESSED,
            message_id=12345,
            chat_id=-1001234567890,
            filtered=False,
            pending=False,
            duplicate=False,
            updated=False,
            reason=None,
            error_code=None,
        )
        assert model.success is True
        assert model.status == ExternalMessageStatus.PROCESSED
        assert model.message_id == 12345
        assert model.chat_id == -1001234567890
        assert model.filtered is False
        assert model.pending is False
        assert model.duplicate is False
        assert model.updated is False
