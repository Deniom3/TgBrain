"""
Ре-экспорт из подпакета repositories для обратной совместимости.

Все репозитории перемещены в src/settings/repositories/.
Данный модуль обеспечивает обратную совместимость.
"""

from .repositories.embedding_providers import EmbeddingProvidersRepository

__all__ = ["EmbeddingProvidersRepository"]
