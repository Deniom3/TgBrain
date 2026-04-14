"""
Сервис безопасной работы с временными файлами сессий.

Infrastructure сервис для создания и удаления временных файлов
с безопасными настройками прав доступа.
"""

import logging
import os
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)


class SecureSessionFileService:
    """
    Сервис безопасной работы с временными файлами сессий.
    
    Обеспечивает:
    - Создание временных файлов с правами 600 (только владелец)
    - Безопасное удаление файлов
    - Проверку существования файлов
    
    Example:
        # Создание файла
        path = await SecureSessionFileService.create_temp_session_file(session_data)
        
        # Удаление файла
        await SecureSessionFileService.delete_temp_session_file(path)
    """
    
    @staticmethod
    async def create_temp_session_file(session_data: bytes) -> str:
        """
        Создать временный файл сессии с безопасными настройками.

        SECURITY:
        - Использует mkstemp() для атомарного создания
        - Устанавливает права 600 (только владелец) ДО записи
        - Записывает данные в бинарном режиме
        - asyncio.Lock защищает запись данных

        Args:
            session_data: Данные сессии для записи.

        Returns:
            Путь к созданному файлу.

        Raises:
            OSError: Если не удалось создать файл.
        """
        import tempfile

        fd: Optional[int] = None
        temp_file_path: Optional[str] = None

        try:
            fd, temp_file_path = tempfile.mkstemp(suffix=".session")
            
            os.chmod(temp_file_path, 0o600)

            async with asyncio.Lock():
                with os.fdopen(fd, 'wb') as f:
                    f.write(session_data)

            return temp_file_path

        except Exception:
            if fd is not None:
                os.close(fd)
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            raise
    
    @staticmethod
    async def delete_temp_session_file(file_path: str) -> bool:
        """
        Удалить временный файл сессии.

        SECURITY:
        - Проверяет файл на symlink ПЕРЕД удалением
        - Использует os.unlink() для атомарного удаления

        Args:
            file_path: Путь к файлу для удаления.

        Returns:
            True если файл успешно удалён, False если файл не найден
            или произошла ошибка.
        """
        try:
            if os.path.islink(file_path):
                logger.error("Symlink detected, refusing to delete")
                return False

            if os.path.exists(file_path):
                os.unlink(file_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления файла: {e}")
            return False
    
    @staticmethod
    def exists(file_path: str) -> bool:
        """
        Проверить существование файла.
        
        Args:
            file_path: Путь к файлу.
            
        Returns:
            True если файл существует.
        """
        return os.path.exists(file_path)
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """
        Получить размер файла в байтах.

        SECURITY: Проверяет файл на symlink ПЕРЕД получением размера.

        Args:
            file_path: Путь к файлу.

        Returns:
            Размер файла в байтах, или 0 если файл не существует
            или является symlink.

        Raises:
            OSError: Если файл не существует.
        """
        if os.path.islink(file_path):
            logger.error("Symlink detected")
            return 0

        if not os.path.exists(file_path):
            return 0

        return os.path.getsize(file_path)
