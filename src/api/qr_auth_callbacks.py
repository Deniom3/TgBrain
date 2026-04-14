"""
QR auth callback registration.

Вынесено из main.py для соблюдения целевого размера (90-95 строк).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.api import _on_qr_auth_complete_handler
from src.settings_api import set_logout_complete_callback, set_qr_auth_complete_callback

if TYPE_CHECKING:
    from fastapi import FastAPI

    from src.protocols import IApplicationState


def register_qr_auth_callbacks(app: FastAPI) -> None:
    """
    Зарегистрировать QR auth и logout callbacks.

    QR auth — всегда is_logout=False.
    Logout — всегда is_logout=True.
    """

    async def qr_auth_callback(
        session_name: str,
        state: Optional["IApplicationState"],
    ) -> None:
        await _on_qr_auth_complete_handler(session_name, app.state, is_logout=False)

    async def logout_callback(
        session_name: str,
        state: Optional["IApplicationState"],
    ) -> None:
        await _on_qr_auth_complete_handler(session_name, app.state, is_logout=True)

    set_qr_auth_complete_callback(qr_auth_callback)
    set_logout_complete_callback(logout_callback)
