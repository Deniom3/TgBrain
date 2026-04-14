"""
Тесты для модуля кодов ошибок API.

Проверяет структуру ErrorCode, полноту словарей, уникальность кодов
и сохранность значений существующих кодов.
"""


from src.api.error_codes import (
    APP_ERROR_CODES,
    AUTH_ERROR_CODES,
    CONF_ERROR_CODES,
    ErrorCode,
    EXTERNAL_INGEST_ERROR_CODES,
    RATE_ERROR_CODES,
    RAG_ERROR_CODES,
    SCH_ERROR_CODES,
    SUMMARY_ERROR_CODES,
    validate_error_codes_unique,
    WHK_ERROR_CODES,
)


class TestErrorCodeDataclass:
    """Тесты структуры dataclass ErrorCode."""

    def test_error_code_dataclass_has_required_fields(self) -> None:
        """ErrorCode имеет code, message, http_status."""
        ec = ErrorCode(code="TEST-001", message="Test error", http_status=500)
        assert ec.code == "TEST-001"
        assert ec.message == "Test error"
        assert ec.http_status == 500


class TestErrorDictsNonEmpty:
    """Тесты что все словари ошибок содержат хотя бы один элемент."""

    def test_all_error_dicts_are_non_empty(self) -> None:
        """Все словари >= 1 элемент."""
        assert len(RAG_ERROR_CODES) >= 1
        assert len(EXTERNAL_INGEST_ERROR_CODES) >= 1
        assert len(SUMMARY_ERROR_CODES) >= 1
        assert len(APP_ERROR_CODES) >= 1
        assert len(WHK_ERROR_CODES) >= 1
        assert len(AUTH_ERROR_CODES) >= 1
        assert len(RATE_ERROR_CODES) >= 1
        assert len(SCH_ERROR_CODES) >= 1
        assert len(CONF_ERROR_CODES) >= 1


class TestUniqueCodes:
    """Тесты уникальности кодов ошибок."""

    def test_no_duplicate_codes_across_all_dicts(self) -> None:
        """ALL_ERROR_CODES уникален."""
        duplicates = validate_error_codes_unique()
        assert duplicates == []


class TestAppErrorCodesPreserved:
    """Тесты что существующие APP коды не изменены."""

    def test_app_001_003_existing_preserved(self) -> None:
        """APP-001..003 значения не изменены."""
        assert APP_ERROR_CODES["APP-001"].code == "APP-001"
        assert APP_ERROR_CODES["APP-001"].message == "Invalid timezone"
        assert APP_ERROR_CODES["APP-001"].http_status == 400

        assert APP_ERROR_CODES["APP-002"].code == "APP-002"
        assert APP_ERROR_CODES["APP-002"].message == "Setting not found"
        assert APP_ERROR_CODES["APP-002"].http_status == 404

        assert APP_ERROR_CODES["APP-003"].code == "APP-003"
        assert APP_ERROR_CODES["APP-003"].message == "Failed to save setting"
        assert APP_ERROR_CODES["APP-003"].http_status == 500

    def test_app_101_107_global_handlers_defined(self) -> None:
        """APP-101..APP-107 определены."""
        for code_suffix in range(101, 108):
            key = f"APP-{code_suffix}"
            assert key in APP_ERROR_CODES
            assert APP_ERROR_CODES[key].code == key


class TestWhkErrorCodes:
    """Тесты кодов ошибок webhook."""

    def test_whk_001_002_existing_preserved(self) -> None:
        """WHK-001..002 значения не изменены."""
        assert WHK_ERROR_CODES["WHK-001"].code == "WHK-001"
        assert WHK_ERROR_CODES["WHK-001"].message == "Chat not found"
        assert WHK_ERROR_CODES["WHK-001"].http_status == 404

        assert WHK_ERROR_CODES["WHK-002"].code == "WHK-002"
        assert WHK_ERROR_CODES["WHK-002"].message == "Invalid webhook configuration"
        assert WHK_ERROR_CODES["WHK-002"].http_status == 400

    def test_whk_003_010_defined(self) -> None:
        """WHK-003..WHK-010 определены."""
        for code_suffix in range(3, 11):
            key = f"WHK-{code_suffix:03d}"
            assert key in WHK_ERROR_CODES
            assert WHK_ERROR_CODES[key].code == key


class TestAuthErrorCodes:
    """Тесты кодов ошибок авторизации."""

    def test_auth_error_codes_defined(self) -> None:
        """AUTH-001..004, AUTH-101..102."""
        for code_suffix in range(1, 5):
            key = f"AUTH-{code_suffix:03d}"
            assert key in AUTH_ERROR_CODES
            assert AUTH_ERROR_CODES[key].code == key

        for code_suffix in range(101, 103):
            key = f"AUTH-{code_suffix}"
            assert key in AUTH_ERROR_CODES
            assert AUTH_ERROR_CODES[key].code == key


class TestRateErrorCodes:
    """Тесты кодов ошибок rate limiting."""

    def test_rate_error_codes_defined(self) -> None:
        """RATE-001, RATE-002."""
        assert "RATE-001" in RATE_ERROR_CODES
        assert RATE_ERROR_CODES["RATE-001"].code == "RATE-001"
        assert RATE_ERROR_CODES["RATE-001"].http_status == 503

        assert "RATE-002" in RATE_ERROR_CODES
        assert RATE_ERROR_CODES["RATE-002"].code == "RATE-002"
        assert RATE_ERROR_CODES["RATE-002"].http_status == 429


class TestSchErrorCodes:
    """Тесты кодов ошибок расписания."""

    def test_schedule_error_codes_defined(self) -> None:
        """SCH-001..SCH-006."""
        for code_suffix in range(1, 7):
            key = f"SCH-{code_suffix:03d}"
            assert key in SCH_ERROR_CODES
            assert SCH_ERROR_CODES[key].code == key


class TestConfErrorCodes:
    """Тесты кодов ошибок конфигурации."""

    def test_config_error_codes_defined(self) -> None:
        """CONF-001..CONF-003."""
        for code_suffix in range(1, 4):
            key = f"CONF-{code_suffix:03d}"
            assert key in CONF_ERROR_CODES
            assert CONF_ERROR_CODES[key].code == key
