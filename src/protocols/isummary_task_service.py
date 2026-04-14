"""Protocol интерфейс для SummaryTaskService."""

from datetime import datetime
from typing import Optional, Protocol


class ISummaryTaskService(Protocol):
    """Интерфейс SummaryTaskService."""

    def get_cache_ttl(
        self, period_start: datetime, period_end: datetime
    ) -> Optional[int]: ...
    def generate_params_hash(
        self,
        chat_id: int,
        period_start: datetime,
        period_end: datetime,
        prompt_version: str,
        model_name: Optional[str] = None,
    ) -> str: ...
