"""
Ре-экспорт из подпакета repositories для обратной совместимости.

Все репозитории перемещены в src/settings/repositories/.
Данный модуль обеспечивает обратную совместимость.
"""

from .repositories.app_settings import AppSettingsRepository

__all__ = ["AppSettingsRepository"]
