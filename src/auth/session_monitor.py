"""
Мониторинг сессий QR авторизации и cleanup.

Классы:
- SessionMonitor: Мониторинг статуса авторизации сессии

Функции:
- cleanup_old_qr_sessions: Очистка старых неавторизованных сессий
"""

import asyncio
import os
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Protocol

from telethon import TelegramClient

if TYPE_CHECKING:
    from .service import QRAuthService


class SessionRepositoryProtocol(Protocol):
    """Protocol для репозитория сессий."""

    async def get(self) -> object:
        """Получить данные авторизации."""
        ...


class SessionMonitor:
    """
    Мониторинг статуса авторизации сессии.

    Проверяет авторизацию каждые 20 секунд до тех пор, пока:
    - Пользователь не авторизуется
    - Сессия не истечёт (5 минут)
    - Сессия не будет отменена
    """

    def __init__(
        self,
        service: "QRAuthService",
        session_id: str,
        api_id: int,
        api_hash: str,
        session_path: str,
    ):
        """
        Инициализация монитора.

        Args:
            service: Родительский сервис
            session_id: ID сессии для мониторинга
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session_path: Путь к файлам сессий
        """
        self._service = service
        self._session_id = session_id
        self._api_id = api_id
        self._api_hash = api_hash
        self._session_path = session_path
        self._is_running = False
        self._task: Optional[asyncio.Task] = None

    async def run(self):
        """Запустить мониторинг сессии."""
        import logging
        from datetime import timedelta

        logger = logging.getLogger(__name__)
        logger.info(f"Запуск мониторинга сессии {self._session_id}")

        check_count = 0
        max_checks = 15  # 15 проверок * 20 сек = 5 минут
        delay_seconds = 20  # Задержка между проверками 20 секунд
        
        # Rate limiting: не более 3 проверок в минуту
        checks_in_last_minute = 0
        max_checks_per_minute = 3
        minute_start_time = datetime.now()

        while check_count < max_checks:
            try:
                # Rate limiting: проверка количества проверок в минуту
                if datetime.now() - minute_start_time > timedelta(minutes=1):
                    checks_in_last_minute = 0
                    minute_start_time = datetime.now()
                
                if checks_in_last_minute >= max_checks_per_minute:
                    wait_time = 60 - (datetime.now() - minute_start_time).total_seconds()
                    if wait_time > 0:
                        logger.info(f"Rate limiting: ожидание {wait_time:.0f} секунд")
                        await asyncio.sleep(wait_time)
                        checks_in_last_minute = 0
                        minute_start_time = datetime.now()
                
                checks_in_last_minute += 1
                check_count += 1

                # Проверяем существование сессии
                async with self._service._lock:
                    if self._session_id not in self._service._active_sessions:
                        logger.info(f"Мониторинг остановлен: сессия {self._session_id} не найдена")
                        return

                    session = self._service._active_sessions[self._session_id]

                    # Проверяем истечение срока
                    if datetime.now() > session.expires_at:
                        session.error = "Сессия истекла"
                        logger.warning(f"Сессия {self._session_id} истекла")
                        return

                    # Проверяем завершение
                    if session.is_completed:
                        logger.info(f"Сессия {self._session_id} завершена, остановка мониторинга")
                        return

                # Проверяем авторизацию через переподключение
                session_file = f"{self._session_path}/{session.session_name}"
                logger.info(
                    f"Мониторинг {self._session_id} (попытка {check_count}/{max_checks}): "
                    f"проверка файла {session_file}.session"
                )

                if os.path.exists(f"{session_file}.session"):
                    # Пытаемся подключиться и проверить авторизацию
                    try:
                        # Отключаем старый клиент если есть
                        if self._service._client:
                            try:
                                await self._service._client.disconnect()
                            except Exception:
                                pass

                        # Создаем новый клиент с тем же session_file
                        test_client = TelegramClient(
                            session_file,
                            self._api_id,
                            self._api_hash,
                        )
                        await test_client.connect()

                        is_auth = await test_client.is_user_authorized()
                        logger.info(f"Мониторинг {self._session_id}: is_user_authorized={is_auth}")

                        if is_auth:
                            logger.info(f"Сессия {self._session_id}: пользователь авторизован")
                            # Не отключаем клиент - он понадобится в _on_auth_success
                            self._service._client = test_client
                            await self._service._on_auth_success(self._session_id)
                            return
                        else:
                            await test_client.disconnect()
                    except Exception as e:
                        logger.warning(f"Ошибка проверки авторизации {self._session_id}: {e}")
                else:
                    logger.warning(f"Файл сессии не найден: {session_file}.session")

                # Ждём 20 секунд перед следующей проверкой
                if check_count < max_checks:
                    logger.info(
                        f"Мониторинг {self._session_id}: "
                        f"ожидание {delay_seconds} секунд до следующей проверки..."
                    )
                    await asyncio.sleep(delay_seconds)

            except asyncio.CancelledError:
                logger.info(f"Мониторинг сессии {self._session_id} отменён")
                self._is_running = False
                return
            except Exception as e:
                logger.error(f"Ошибка мониторинга сессии {self._session_id}: {e}")
                await asyncio.sleep(delay_seconds)

        logger.warning(
            f"Мониторинг {self._session_id}: "
            f"превышено максимальное количество проверок ({max_checks}). "
            f"Запросите новый QR код."
        )

        # Удаляем неавторизованную сессию
        async with self._service._lock:
            if self._session_id in self._service._active_sessions:
                session = self._service._active_sessions[self._session_id]
                # Удаляем файл сессии если он существует
                session_file = f"{self._session_path}/{session.session_name}.session"
                if os.path.exists(session_file):
                    try:
                        os.remove(session_file)
                        logger.info(f"Удалён файл сессии: {session_file}")
                    except Exception as e:
                        logger.error(f"Ошибка удаления файла сессии: {e}")

                # Удаляем сессию из памяти
                del self._service._active_sessions[self._session_id]
                logger.info(f"Сессия {self._session_id} удалена из памяти")

        # Отменяем задачу мониторинга из списка
        if self._session_id in self._service._monitor_tasks:
            del self._service._monitor_tasks[self._session_id]
        
        self._is_running = False

    def stop(self):
        """
        Остановить мониторинг сессии.

        Отменяет asyncio задачу мониторинга если она запущена.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if self._task and not self._task.done():
            logger.info(f"Остановка мониторинга сессии {self._session_id}")
            self._task.cancel()
            self._is_running = False
        else:
            logger.debug(f"Мониторинг сессии {self._session_id} не запущен или уже остановлен")


async def cleanup_old_qr_sessions(session_path: str, active_session_name: str | None = None) -> None:
    """
    Очистка старых QR сессий с диска.

    Удаляет все QR сессии которые:
    - Не авторизованы (файл < 30KB)
    - Созданы более 5 минут назад (по времени модификации файла)
    - Отсутствуют в базе данных (не являются активной сессией)

    Args:
        session_path: Путь к файлам сессий
        active_session_name: Имя активной сессии (передаётся из сервисного слоя)
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        if not os.path.exists(session_path):
            return

        current_time = time.time()
        max_age_seconds = 300  # 5 минут

        for filename in os.listdir(session_path):
            if not filename.startswith("qr_auth_") or not filename.endswith(".session"):
                continue

            file_path = os.path.join(session_path, filename)
            session_name = filename[:-8]  # Убираем '.session'

            # НЕ удаляем активную сессию из БД!
            if active_session_name and session_name == active_session_name:
                logger.debug(f"Сохраняем активную сессию из БД: {filename}")
                continue

            # Проверяем размер и возраст файла
            try:
                file_size = os.path.getsize(file_path)
                file_mtime = os.path.getmtime(file_path)
                file_age = current_time - file_mtime

                # Не удаляем файлы > 30KB (авторизованные сессии)
                if file_size >= 30000:
                    logger.debug(f"Сохраняем сессию {filename} (размер: {file_size} байт)")
                    continue

                # Не удаляем файлы < 5 минут
                if file_age < max_age_seconds:
                    logger.debug(f"Сохраняем сессию {filename} (возраст: {file_age:.0f} сек)")
                    continue

                # Удаляем старую неавторизованную сессию
                os.remove(file_path)
                logger.info(f"Удалена старая QR сессия: {filename}")

            except Exception as e:
                logger.error(f"Ошибка обработки файла {filename}: {e}")

    except Exception as e:
        logger.error(f"Ошибка очистки старых сессий: {e}")
