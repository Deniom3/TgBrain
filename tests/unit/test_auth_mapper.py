"""Тесты для мапперов авторизации."""

from datetime import datetime, timezone

import pytest

from src.common.mappers.auth_mapper import (
    from_data_model,
    from_domain,
    to_data_model,
    to_domain,
)
from src.domain.exceptions import ValidationError
from src.domain.models.auth import TelegramAuth as DomainTelegramAuth
from src.domain.value_objects import ApiHash, ApiId, PhoneNumber, SessionName
from src.infrastructure.persistence.models import TelegramAuthDB
from src.models.data_models import TelegramAuth as DataModelTelegramAuth


class TestToDomain:
    """Тесты конвертации infrastructure -> domain."""

    def test_to_domain_valid(self) -> None:
        """Конвертация с валидными данными."""
        updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        auth_db = TelegramAuthDB(
            id=1,
            api_id=12345678,
            api_hash="abcdef1234567890abcdef1234567890",
            phone_number="+79991234567",
            session_name="test_session",
            updated_at=updated_at,
        )

        result = to_domain(auth_db)

        assert isinstance(result, DomainTelegramAuth)
        assert result.id == 1
        assert result.api_id is not None
        assert result.api_id.value == 12345678
        assert result.api_hash is not None
        assert result.api_hash.value == "abcdef1234567890abcdef1234567890"
        assert result.phone_number is not None
        assert result.phone_number.value == "+79991234567"
        assert result.session_name is not None
        assert result.session_name.value == "test_session"
        assert result.updated_at == updated_at

    def test_to_domain_invalid_api_id_raises(self) -> None:
        """Невалидный api_id (<=0) вызывает ValidationError."""
        auth_db = TelegramAuthDB(id=1, api_id=-1)

        with pytest.raises(ValidationError):
            to_domain(auth_db)

    def test_to_domain_invalid_api_hash_raises(self) -> None:
        """Невалидный api_hash (не 32 символа) вызывает ValidationError."""
        auth_db = TelegramAuthDB(id=1, api_hash="short")

        with pytest.raises(ValidationError):
            to_domain(auth_db)

    def test_to_domain_invalid_phone_raises(self) -> None:
        """Невалидный phone_number (без +) вызывает ValidationError."""
        auth_db = TelegramAuthDB(id=1, phone_number="79991234567")

        with pytest.raises(ValidationError):
            to_domain(auth_db)

    def test_to_domain_invalid_session_name_raises(self) -> None:
        """Невалидный session_name (с запрещёнными символами) вызывает ValidationError."""
        auth_db = TelegramAuthDB(id=1, session_name="../bad")

        with pytest.raises(ValidationError):
            to_domain(auth_db)

    def test_to_domain_all_nulls(self) -> None:
        """Все поля None дают None-значения в domain."""
        auth_db = TelegramAuthDB(id=1)

        result = to_domain(auth_db)

        assert result.id == 1
        assert result.api_id is None
        assert result.api_hash is None
        assert result.phone_number is None
        assert result.session_name is None

    def test_to_domain_preserves_none_for_api_id(self) -> None:
        """api_id=None в БД даёт api_id=None в domain."""
        auth_db = TelegramAuthDB(id=1, api_id=None)

        result = to_domain(auth_db)

        assert result.api_id is None


class TestFromDomain:
    """Тесты конвертации domain -> infrastructure."""

    def test_from_domain_valid(self) -> None:
        """Конвертация domain -> infrastructure с валидными данными."""
        updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        auth = DomainTelegramAuth(
            id=1,
            api_id=ApiId(12345678),
            api_hash=ApiHash("abcdef1234567890abcdef1234567890"),
            phone_number=PhoneNumber("+79991234567"),
            session_name=SessionName("test_session"),
            updated_at=updated_at,
        )

        result = from_domain(auth)

        assert isinstance(result, TelegramAuthDB)
        assert result.id == 1
        assert result.api_id == 12345678
        assert result.api_hash == "abcdef1234567890abcdef1234567890"
        assert result.phone_number == "+79991234567"
        assert result.session_name == "test_session"
        assert result.updated_at == updated_at

    def test_from_domain_with_session_data(self) -> None:
        """session_data передаётся отдельно от domain модели."""
        auth = DomainTelegramAuth(id=1)
        session_data = b"session_bytes_here"

        result = from_domain(auth, session_data=session_data)

        assert result.session_data == session_data

    def test_from_domain_with_null_session_data(self) -> None:
        """session_data=None по умолчанию."""
        auth = DomainTelegramAuth(id=1)

        result = from_domain(auth)

        assert result.session_data is None

    def test_from_domain_nulls(self) -> None:
        """Все None-поля в domain дают None в infrastructure."""
        auth = DomainTelegramAuth(id=1)

        result = from_domain(auth)

        assert result.api_id is None
        assert result.api_hash is None
        assert result.phone_number is None
        assert result.session_name is None


class TestToDataModel:
    """Тесты конвертации infrastructure -> data model."""

    def test_to_data_model_valid(self) -> None:
        """Конвертация infrastructure -> data model с валидными данными."""
        updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        auth_db = TelegramAuthDB(
            id=1,
            api_id=12345678,
            api_hash="abcdef1234567890abcdef1234567890",
            phone_number="+79991234567",
            session_name="test_session",
            updated_at=updated_at,
        )

        result = to_data_model(auth_db)

        assert isinstance(result, DataModelTelegramAuth)
        assert result.id == 1
        assert result.api_id is not None
        assert result.api_id.value == 12345678

    def test_to_data_model_nulls(self) -> None:
        """Все None-поля дают None-значения в data model."""
        auth_db = TelegramAuthDB(id=1)

        result = to_data_model(auth_db)

        assert result.api_id is None
        assert result.api_hash is None
        assert result.phone_number is None
        assert result.session_name is None


class TestFromDataModel:
    """Тесты конвертации data model -> infrastructure."""

    def test_from_data_model_valid(self) -> None:
        """Конвертация data model -> infrastructure с валидными данными."""
        updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        auth = DataModelTelegramAuth(
            id=1,
            api_id=ApiId(12345678),
            api_hash=ApiHash("abcdef1234567890abcdef1234567890"),
            phone_number=PhoneNumber("+79991234567"),
            session_name=SessionName("test_session"),
            updated_at=updated_at,
        )

        result = from_data_model(auth)

        assert isinstance(result, TelegramAuthDB)
        assert result.api_id == 12345678
        assert result.api_hash == "abcdef1234567890abcdef1234567890"

    def test_from_data_model_session_data_always_none(self) -> None:
        """session_data всегда None при конвертации из data model."""
        auth = DataModelTelegramAuth(id=1)

        result = from_data_model(auth)

        assert result.session_data is None

    def test_from_data_model_null_fields(self) -> None:
        """Все None-поля дают None в infrastructure."""
        auth = DataModelTelegramAuth(id=1)

        result = from_data_model(auth)

        assert result.api_id is None
        assert result.api_hash is None
        assert result.phone_number is None
        assert result.session_name is None

    def test_round_trip_domain_to_infrastructure(self) -> None:
        """Круговой тест: domain → infrastructure → domain."""
        domain_auth = DomainTelegramAuth(
            id=1,
            api_id=ApiId(12345),
            api_hash=ApiHash("abcdef1234567890abcdef1234567890"),
            phone_number=PhoneNumber("+1234567890"),
            session_name=SessionName("test_session"),
        )

        infra = from_domain(domain_auth, session_data=b"session_data")

        assert infra.api_id == 12345
        assert infra.api_hash == "abcdef1234567890abcdef1234567890"
        assert infra.phone_number == "+1234567890"
        assert infra.session_name == "test_session"
        assert infra.session_data == b"session_data"
