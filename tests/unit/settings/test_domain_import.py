"""Тесты re-export domain из src.settings.domain."""


def test_settings_init_reexport_domain():
    """from src.settings import PendingCleanupSettings работает."""
    from src.settings import PendingCleanupSettings
    assert PendingCleanupSettings is not None


def test_settings_init_pending_cleanup_settings_accessible():
    """Прямой импорт из src.settings.domain работает."""
    from src.settings.domain import PendingCleanupSettings
    assert PendingCleanupSettings is not None


def test_settings_init_pending_ttl_constant_accessible():
    """Импорт константы PENDING_TTL_MINUTES работает."""
    from src.settings import PENDING_TTL_MINUTES
    from src.settings.domain import PENDING_TTL_MINUTES as P2
    assert PENDING_TTL_MINUTES == "pending.ttl_minutes"
    assert PENDING_TTL_MINUTES == P2
