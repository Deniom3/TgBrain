"""
Thread-safe хранилище для состояния приложения.

Модуль предоставляет безопасный доступ к app.state в async среде.
"""

import asyncio
import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from fastapi import FastAPI


class AppStateStore:
    """
    Thread-safe хранилище для app.state.
    
    Используется для безопасного доступа к состоянию приложения
    из любого места в коде без создания race conditions.
    
    Example:
        # Инициализация при старте приложения
        AppStateStore.set(app)
        
        # Доступ из любого места
        app = AppStateStore.get_app()
        embeddings = app.state.embeddings
        
        # Сброс для тестов
        AppStateStore.reset()
    """
    
    _app: Optional["FastAPI"] = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def set(cls, app: "FastAPI") -> None:
        """
        Установить app в хранилище.
        
        Args:
            app: FastAPI приложение для хранения.
        """
        async with cls._lock:
            cls._app = app
    
    @classmethod
    def get_app(cls) -> "FastAPI":
        """
        Получить app из хранилища.
        
        Returns:
            FastAPI приложение.
            
        Raises:
            RuntimeError: Если хранилище не инициализировано.
        """
        if cls._app is None:
            raise RuntimeError("AppStateStore не инициализирован")
        return cls._app
    
    @classmethod
    def get_state(cls) -> object:
        """
        Получить app.state из хранилища.
        
        Returns:
            app.state объект.
            
        Raises:
            RuntimeError: Если хранилище не инициализировано.
        """
        return cls.get_app().state
    
    @classmethod
    def reset(cls) -> None:
        """
        Сбросить хранилище (для тестов).
        
        Raises:
            RuntimeError: Если вызов не из тестового окружения.
        """
        if not os.environ.get("ALLOW_STATE_RESET"):
            raise RuntimeError("AppStateStore.reset() запрещён в production")
        cls._app = None
    
    @classmethod
    def is_initialized(cls) -> bool:
        """
        Проверить, инициализировано ли хранилище.
        
        Returns:
            True если хранилище инициализировано.
        """
        return cls._app is not None
