"""Сервис управления файлами сессий Telegram."""
import logging
import os

from src.domain.value_objects import SessionName

logger = logging.getLogger(__name__)


class SessionFileService:
    """
    Сервис управления файлами сессий.
    
    Отвечает за безопасное удаление файлов сессий с защитой от:
    - Symlink атак
    - Path traversal атак
    - Выхода за пределы директории сессий
    """

    @staticmethod
    async def delete_session_files(session_name: SessionName, session_path: str) -> bool:
        """
        Удалить файлы сессии.
        
        Args:
            session_name: Имя сессии (SessionName VO)
            session_path: Путь к директории с сессиями
            
        Returns:
            True если успешно удалены
            
        Security:
            - Проверка на symlink ДО операций с файлом
            - Проверка path traversal через basename
            - Проверка выхода за пределы директории через realpath
        """
        # Получаем только имя файла (без пути) для защиты от path traversal
        session_basename = os.path.basename(session_name.value)

        if not session_basename:
            logger.error("Некорректное session_name после санитизации")
            return False

        # Собираем полный путь безопасно
        abs_session_path = os.path.abspath(session_path)
        session_file = os.path.join(abs_session_path, session_basename)

        # Проверяем что путь внутри разрешённой директории
        # Защита от symlink: используем realpath для разрешения всех ссылок
        real_session_path = os.path.realpath(session_file)
        real_abs_session_path = os.path.realpath(abs_session_path)

        if not real_session_path.startswith(real_abs_session_path + os.sep):
            logger.error("Попытка выхода за пределы директории сессий через symlink")
            return False

        # Используем real_session_path для всех операций
        session_file_with_ext = f"{real_session_path}.session"
        journal_file = f"{real_session_path}.session-journal"

        for file_path in [session_file_with_ext, journal_file]:
            try:
                # 1. ПРОВЕРКА SYMLINK (ДО открытия файла!)
                if os.path.islink(file_path):
                    logger.warning(f"Symlink обнаружен: {os.path.basename(file_path)}")
                    continue

                # 2. Проверка что это файл (не директория)
                if not os.path.isfile(file_path):
                    logger.warning(f"Файл не существует: {os.path.basename(file_path)}")
                    continue

                # 3. Удаление файла
                os.remove(file_path)
                logger.info(f"Удалён файл сессии: {os.path.basename(file_path)}")

            except PermissionError:
                logger.error(f"Нет прав на удаление: {os.path.basename(file_path)}")
            except Exception:
                logger.error("Ошибка удаления файла")

        return True
