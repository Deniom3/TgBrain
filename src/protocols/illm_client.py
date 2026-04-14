"""Protocol интерфейс для LLM клиента."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ILLMClient(Protocol):
    """Интерфейс LLM клиента."""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs,
    ) -> str: ...
    async def check_health(self) -> bool: ...
    async def get_models(self) -> list[str]: ...
    async def close(self) -> None: ...

    @property
    def current_provider(self) -> str: ...
