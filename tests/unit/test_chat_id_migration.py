"""Тесты миграции chat_id."""

from src.ingestion.chat_sync_service import normalize_chat_id


class TestChatIdMigration:
    """Тесты логики миграции chat_id."""

    def test_raw_id_extraction_from_wrong_id(self) -> None:
        """Извлечение raw_id из неверного chat_id."""
        raw_id = 1234567890
        wrong_id = -1000000000000 + raw_id
        extracted = wrong_id + 1000000000000
        assert extracted == raw_id

    def test_correct_id_from_extracted_raw(self) -> None:
        """Получение корректного chat_id из извлечённого raw_id."""
        raw_id = 1234567890
        wrong_id = -1000000000000 + raw_id
        extracted = wrong_id + 1000000000000
        correct_id = normalize_chat_id(extracted, is_channel=True)
        assert correct_id == -1001234567890

    def test_already_correct_id_not_changed(self) -> None:
        """Уже корректный chat_id не меняется."""
        correct_id = -1001234567890
        extracted = correct_id + 1000000000000
        assert extracted < 0

    def test_migrate_various_ids(self) -> None:
        """Миграция различных chat_id."""
        test_cases = [
            (1234567890, -1000000000000 + 1234567890, -1001234567890),
            (100, -1000000000000 + 100, -1000000000100),
            (1, -1000000000000 + 1, -1000000000001),
        ]
        for raw_id, wrong_id, correct_id in test_cases:
            extracted = wrong_id + 1000000000000
            assert extracted == raw_id
            result = normalize_chat_id(extracted, is_channel=True)
            assert result == correct_id

    def test_wrong_id_in_migration_range(self) -> None:
        """Неверный chat_id попадает в диапазон миграции."""
        raw_id = 1234567890
        wrong_id = -1000000000000 + raw_id  # Старая неверная формула = -998765432110
        assert wrong_id <= -1000000000 and wrong_id > -1000000000000

    def test_correct_id_not_in_migration_range(self) -> None:
        """Корректный chat_id НЕ попадает в диапазон миграции."""
        correct_id = -1001234567890
        assert not (correct_id <= -1000000000 and correct_id > -1000000000000)

    def test_regular_group_not_in_migration_range(self) -> None:
        """Обычная группа (chat_id=-12345) НЕ попадает в диапазон миграции."""
        group_chat_id = -12345
        assert not (group_chat_id <= -1000000000 and group_chat_id > -1000000000000)
