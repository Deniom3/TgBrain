"""
Callback для QR авторизации.

Функции:
- _on_qr_auth_complete_handler: Обработчик завершения QR авторизации
- _stop_ingester: Остановить текущий Ingester
- _create_new_ingester: Создать новый Ingester с сессией
- restart_ingester: Перезапуск Telegram Ingester
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.protocols import IApplicationState

from src.services import IngesterRestartService

logger = logging.getLogger(__name__)


async def restart_ingester(state: "IApplicationState", is_logout: bool = False) -> None:
    """
    Управление Telegram Ingester.

    Args:
        state: Состояние приложения через интерфейс IApplicationState
        is_logout: Если True, остановить Ingester
    """
    if is_logout:
        # При logout только останавливаем Ingester
        await IngesterRestartService.stop_for_logout(state)
        return

    # При QR авторизации — запускаем Ingester (не перезапускаем!)
    success = await IngesterRestartService.start_ingester(state)

    if not success:
        logger.error("Критическая ошибка: не удалось запустить Ingester")


async def _on_qr_auth_complete_handler(
    session_name: str,
    state: Optional["IApplicationState"] = None,
    is_logout: bool = False,
) -> None:
    """
    Обработчик завершения QR авторизации или logout.

    При QR авторизации — запускает Ingester.
    При logout — останавливает Ingester и SessionMonitor.

    Args:
        session_name: Имя файла сессии
        state: Состояние приложения через интерфейс IApplicationState
        is_logout: True если это logout (а не QR авторизация)
    """
    session_name_masked = f"{session_name[:4]}..." if len(session_name) > 4 else "***"
    logger.debug("Завершена авторизация/logout, сессия: %s, is_logout=%s", session_name_masked, is_logout)

    # При logout останавливаем Ingester и SessionMonitor
    if is_logout:
        if state:
            # Останавливаем SessionMonitor если есть
            if hasattr(state, 'qr_auth_service'):
                try:
                    await state.qr_auth_service.stop_all_sessions()
                    logger.info("SessionMonitor остановлен")
                except Exception as e:
                    # SessionMonitor остановка может падать при уже закрытом соединении.
                    # Продолжаем logout — это не критично для безопасности,
                    # так как сессия всё равно инвалидируется на стороне Telegram.
                    logger.error("Ошибка остановки SessionMonitor: %s", e)
                    raise
            
            # Останавливаем Ingester
            await IngesterRestartService.stop_for_logout(state)
            logger.info("Logout выполнен, Ingester остановлен")
        else:
            logger.info("Logout выполнен, сессия сброшена на: %s", session_name_masked)
        return

    # Это QR авторизация — запускаем Ingester
    logger.info("QR авторизация завершена, сессия: %s", session_name_masked)

    if state:
        logger.info("Запуск Ingester...")

        # Инициализировать background tasks set если нет
        if not hasattr(state, 'background_tasks'):
            state.background_tasks = set()  # type: ignore

        # Запустить Ingester с отслеживанием задачи
        async def start_task() -> None:
            """Фон задача для запуска Ingester с обработкой ошибок."""
            try:
                success = await IngesterRestartService.start_ingester(state)
                if not success:
                    logger.error("Критическая ошибка: не удалось запустить Ingester")
            except Exception as e:
                logger.error("Критическая ошибка запуска Ingester: %s", e)

        task = asyncio.create_task(start_task())
        state.background_tasks.add(task)
        task.add_done_callback(state.background_tasks.discard)
    else:
        logger.info("Ожидание запуска Ingester...")


__all__ = [
    "_on_qr_auth_complete_handler",
    "restart_ingester",
]
