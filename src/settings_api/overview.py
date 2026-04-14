"""
Settings Overview API endpoint.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from .dto import SettingsOverviewDTO

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Settings"])


class SettingsOverviewResponse(BaseModel):
    """Общий обзор настроек."""
    telegram: dict
    llm: dict
    app: dict
    chats: dict


@router.get("/overview", response_model=SettingsOverviewDTO)
async def get_settings_overview():
    """
    Получить общий обзор всех настроек.

    Возвращает сводную информацию о состоянии конфигурации.
    """
    from ..settings_initializer import SettingsInitializer

    config = await SettingsInitializer.get_current_config()

    # Используем DTO для сериализации Value Objects
    return SettingsOverviewDTO.from_config(config)
