"""Тесты для session_name_to_str."""

from src.domain.value_objects import SessionName
from src.utils.session_utils import session_name_to_str


class TestSessionNameToStr:
    """Тесты функции session_name_to_str."""

    def test_none_returns_none(self) -> None:
        """None возвращает None."""
        result = session_name_to_str(None)

        assert result is None

    def test_valid_session_name(self) -> None:
        """SessionName VO конвертируется в строку."""
        session_name = SessionName("my_session")

        result = session_name_to_str(session_name)

        assert result == "my_session"

    def test_legacy_object_with_value(self) -> None:
        """Legacy объект с атрибутом .value конвертируется."""
        legacy_obj = type("LegacySession", (), {"value": "legacy_session"})()

        result = session_name_to_str(legacy_obj)

        assert result == "legacy_session"

    def test_plain_string_fallback(self) -> None:
        """Обычная строка возвращается как есть."""
        result = session_name_to_str("plain_string")  # type: ignore[arg-type]

        assert result == "plain_string"
