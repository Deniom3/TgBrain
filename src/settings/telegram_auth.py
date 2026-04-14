"""
Ре-экспорт из подпакета repositories для обратной совместимости.

Все репозитории перемещены в src/settings/repositories/.
Данный модуль обеспечивает обратную совместимость.
"""

from .repositories.telegram_auth import TelegramAuthRepository

__all__ = ["TelegramAuthRepository"]
