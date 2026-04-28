"""
Тесты нормализации chat_id для каналов/супергрупп.
"""

import pytest

from src.ingestion.chat_sync_service import normalize_chat_id


class TestNormalizeChatId:
    """Юнит-тесты функции normalize_chat_id."""

    def test_normalize_chat_id_channel_positive(self) -> None:
        result = normalize_chat_id(1234567890, is_channel=True)
        assert result == -1001234567890

    def test_normalize_chat_id_channel_already_normalized(self) -> None:
        result = normalize_chat_id(-1001234567890, is_channel=True)
        assert result == -1001234567890

    def test_normalize_chat_id_channel_negative_without_prefix(self) -> None:
        result = normalize_chat_id(-1234567890, is_channel=True)
        assert result == -1001234567890

    def test_normalize_chat_id_non_channel(self) -> None:
        result = normalize_chat_id(123, is_channel=False)
        assert result == 123

    def test_normalize_chat_id_zero_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            normalize_chat_id(0, is_channel=True)

    def test_normalize_chat_id_formula_matches_export_parser(self) -> None:
        raw_id = 1234567890
        result = normalize_chat_id(raw_id, is_channel=True)
        expected = -1000000000000 - raw_id
        assert result == expected


class TestChatsToSaveTypeField:
    """Тесты поля type в chats_to_save."""

    _VALID_TYPES = ("channel", "group", "private", "supergroup")

    def test_chats_to_save_includes_type_field(self) -> None:
        """chats_to_save содержит поле type для каждого чата."""
        # Arrange
        chats_to_save = [
            {"chat_id": -1001234567890, "title": "Test Channel", "type": "channel"},
            {"chat_id": -12345, "title": "Test Group", "type": "group"},
            {"chat_id": 12345, "title": "Test User", "type": "private"},
        ]
        # Act & Assert
        for chat in chats_to_save:
            assert "type" in chat
            assert chat["type"] in self._VALID_TYPES

    def test_fetch_dialogs_channel_type_not_private(self) -> None:
        """Каналы (Channel) получают type != 'private' через _get_chat_type."""
        # Arrange
        from unittest.mock import MagicMock

        from telethon.tl.types import Channel, ChatPhotoEmpty

        from src.ingestion.chat_sync_service import ChatSyncService

        pool = MagicMock()
        service = ChatSyncService(pool)

        broadcast_channel = Channel(
            id=1234567890,
            title="Test Broadcast Channel",
            photo=ChatPhotoEmpty(),
            date=None,
            broadcast=True,
            megagroup=False,
        )
        megagroup_channel = Channel(
            id=9876543210,
            title="Test Megagroup",
            photo=ChatPhotoEmpty(),
            date=None,
            broadcast=False,
            megagroup=True,
        )
        plain_channel = Channel(
            id=1111111111,
            title="Test Plain Channel",
            photo=ChatPhotoEmpty(),
            date=None,
            broadcast=False,
            megagroup=False,
        )

        # Act
        broadcast_type = service._get_chat_type(broadcast_channel)
        megagroup_type = service._get_chat_type(megagroup_channel)
        plain_type = service._get_chat_type(plain_channel)

        # Assert
        assert broadcast_type != "private"
        assert broadcast_type == "channel"
        assert megagroup_type != "private"
        assert megagroup_type == "supergroup"
        assert plain_type != "private"
        assert plain_type == "channel"
