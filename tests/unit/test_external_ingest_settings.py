"""
Тесты для настроек очистки pending сообщений с моками.

Все тесты изолированы от реальной БД через моки.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.settings.domain.pending_cleanup_settings import Minutes


@pytest.fixture
def mock_app_settings_repo():
    """Фикстура для мок-AppSettingsRepository."""
    mock_repo = MagicMock()

    stored_values: dict[str, str | None] = {
        "pending.ttl_minutes": "240",
        "pending.cleanup_interval_minutes": "60"
    }

    async def get_value_side_effect(key, default=None):
        return stored_values.get(key, default)

    async def upsert_side_effect(key: str, value: object, *args: object, **kwargs: object) -> None:
        stored_values[key] = str(value) if value is not None else None

    mock_repo.get_value = AsyncMock(side_effect=get_value_side_effect)
    mock_repo.upsert = AsyncMock(side_effect=upsert_side_effect)

    return mock_repo


pytestmark = pytest.mark.asyncio


class TestPendingCleanupSettings:
    """Тесты настроек очистки pending сообщений с моками."""

    async def test_Settings_Get_Defaults(self, mock_app_settings_repo):
        """Значения по умолчанию (240 мин, 60 мин) (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.get()

        assert settings.ttl_minutes == Minutes(240)
        assert settings.cleanup_interval_minutes == Minutes(60)

    async def test_Settings_Update_Success(self, mock_app_settings_repo):
        """Обновление настроек через API (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.update(
            ttl_minutes=120,
            cleanup_interval_minutes=30
        )

        assert settings.ttl_minutes == Minutes(120)
        assert settings.cleanup_interval_minutes == Minutes(30)

        mock_app_settings_repo.upsert.assert_called()

    async def test_Settings_Reset_Defaults(self, mock_app_settings_repo):
        """Сброс к значениям по умолчанию (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.reset()

        assert settings.ttl_minutes == Minutes(240)
        assert settings.cleanup_interval_minutes == Minutes(60)

    async def test_Settings_InvalidValue_Handler(self, mock_app_settings_repo):
        """Обработка невалидных значений (0, пустое) (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        mock_app_settings_repo.get_value = AsyncMock(return_value="0")

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.get()
        assert settings.ttl_minutes == Minutes(240)

        mock_app_settings_repo.get_value = AsyncMock(return_value="")

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.get()
        assert settings.ttl_minutes == Minutes(240)

    async def test_Settings_Partial_Update(self, mock_app_settings_repo):
        """Частичное обновление (только одно поле) (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.update(ttl_minutes=180)

        assert settings.ttl_minutes == Minutes(180)
        assert settings.cleanup_interval_minutes == Minutes(60)

        settings = await repo.update(cleanup_interval_minutes=120)

        assert settings.ttl_minutes == Minutes(180)
        assert settings.cleanup_interval_minutes == Minutes(120)

    async def test_Settings_Missing_Keys_Use_Defaults(self, mock_app_settings_repo):
        """Если ключей нет — используются значения по умолчанию (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        mock_app_settings_repo.get_value = AsyncMock(return_value=None)

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.get()

        assert settings.ttl_minutes == Minutes(240)
        assert settings.cleanup_interval_minutes == Minutes(60)

    async def test_Settings_Update_NegativeValue_UsesDefault(self, mock_app_settings_repo):
        """Отрицательные значения приводят к использованию default (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.update(ttl_minutes=-1)

        assert settings.ttl_minutes == Minutes(240)

    async def test_Settings_Update_ZeroValue_UsesDefault(self, mock_app_settings_repo):
        """Нулевое значение приводит к использованию default (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.update(ttl_minutes=0)

        assert settings.ttl_minutes == Minutes(240)

    async def test_Settings_Update_NegativeInterval_UsesDefault(self, mock_app_settings_repo):
        """Отрицательный interval приводит к использованию default (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.update(cleanup_interval_minutes=-1)

        assert settings.cleanup_interval_minutes == Minutes(60)

    async def test_Settings_Update_NoneValue_PartialUpdate(self, mock_app_settings_repo):
        """None значение не изменяет настройку (partial update) (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        await repo.update(
            ttl_minutes=120,
            cleanup_interval_minutes=30
        )

        settings = await repo.update(
            ttl_minutes=180,
            cleanup_interval_minutes=None
        )

        assert settings.ttl_minutes == Minutes(180)
        assert settings.cleanup_interval_minutes == Minutes(30)

    async def test_Settings_Update_InvalidType_UsesDefault(self, mock_app_settings_repo):
        """Некорректный тип (строка) приводит к использованию default (с моками)."""
        from src.settings.repositories.pending_cleanup_repository import PendingCleanupSettingsRepository

        repo = PendingCleanupSettingsRepository(mock_app_settings_repo)
        settings = await repo.update(ttl_minutes="invalid")  # type: ignore

        assert settings.ttl_minutes == Minutes(240)
