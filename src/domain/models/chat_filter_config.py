"""
Domain модель конфигурации фильтров сообщений чата.

Модуль предоставляет доменную модель для настройки фильтрации
сообщений: боты, действия, минимальная длина, реклама.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class ChatFilterConfig:
    """Конфигурация фильтров сообщений для чата.

    Атрибуты:
        filter_bots: Фильтровать сообщения от ботов.
        filter_actions: Фильтровать служебные действия.
        filter_min_length: Минимальная длина сообщения.
        filter_ads: Фильтровать рекламные сообщения.
    """

    filter_bots: bool = True
    filter_actions: bool = True
    filter_min_length: int = 15
    filter_ads: bool = True

    def __post_init__(self) -> None:
        if self.filter_min_length < 0:
            raise ValidationError(
                "filter_min_length должен быть >= 0",
                field="filter_min_length",
            )
