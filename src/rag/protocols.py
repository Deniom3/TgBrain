"""Protocols для абстрагирования от инфраструктурных реализаций."""

from typing import Protocol


class EmbeddingGeneratorProtocol(Protocol):
    """Протокол для генератора эмбеддингов summary."""

    async def dispatch_embedding(self, task_id: int, digest: str, model_name: str) -> bool:
        """Сгенерировать и сохранить эмбеддинг."""
        ...


class WebhookDispatcherProtocol(Protocol):
    """Протокол для диспетчера webhook."""

    async def dispatch_webhook_on_completion(self, task_id: int, chat_id: int) -> bool:
        """Отправить webhook после генерации summary."""
        ...
