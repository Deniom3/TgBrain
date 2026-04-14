"""
Подключение к Telegram.

Управление Telegram клиентом, подключение и отключение.
"""

import logging
from typing import Optional

from telethon import TelegramClient

from ..config import Settings

logger = logging.getLogger(__name__)


class TelegramConnection:
    """
    Менеджер подключения к Telegram.
    
    Отвечает за:
    - Создание Telegram клиента
    - Подключение к Telegram
    - Отключение от Telegram
    - Проверку авторизации
    
    Attributes:
        client: Telegram клиент
        is_connected: Флаг подключения
    """
    
    def __init__(self, config: Settings, session_file_path: str) -> None:
        """
        Инициализировать подключение.
        
        Args:
            config: Настройки приложения.
            session_file_path: Путь к файлу сессии.
        """
        self.config = config
        self.session_file_path = session_file_path
        self.client: Optional[TelegramClient] = None
    
    async def connect(self) -> bool:
        """
        Подключиться к Telegram.
        
        Returns:
            True если успешно подключено.
        """
        try:
            self.client = TelegramClient(
                self.session_file_path,
                self.config.tg_api_id,
                self.config.tg_api_hash
            )
            
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                logger.error("Клиент не авторизован")
                await self.disconnect()
                return False
            
            me = await self.client.get_me()
            logger.info(f"✅ Telegram клиент запущен: @{me.username or me.first_name}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к Telegram: {e}", exc_info=True)
            return False
    
    async def disconnect(self) -> None:
        """
        Отключиться от Telegram.
        """
        if self.client:
            await self.client.disconnect()
            self.client = None
            logger.info("✅ Telegram клиент отключён")
    
    def is_connected(self) -> bool:
        """
        Проверить подключение.
        
        Returns:
            True если клиент подключён.
        """
        return self.client is not None and self.client.is_connected()
    
    async def is_authorized(self) -> bool:
        """
        Проверить авторизацию.
        
        Returns:
            True если клиент авторизован.
        """
        if self.client:
            return await self.client.is_user_authorized()
        return False
    
    async def get_me(self) -> Optional[dict]:
        """
        Получить информацию о пользователе.
        
        Returns:
            Информация о пользователе или None.
        """
        if self.client:
            me = await self.client.get_me()
            return {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "last_name": me.last_name,
            }
        return None
    
    def get_client(self) -> Optional[TelegramClient]:
        """
        Получить Telegram клиент.
        
        Returns:
            Telegram клиент или None.
        """
        return self.client
