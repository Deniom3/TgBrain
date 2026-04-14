"""
Ре-экспорт из подпакета repositories для обратной совместимости.

Все репозитории перемещены в src/settings/repositories/.
Данный модуль обеспечивает обратную совместимость.
"""

from .repositories.chat_settings import (
    ChatSettingsRepository,
    ChatSettingsRepositoryError,
    WebhookConfigValidationError,
)

__all__ = [
    "ChatSettingsRepository",
    "ChatSettingsRepositoryError",
    "WebhookConfigValidationError",
]
