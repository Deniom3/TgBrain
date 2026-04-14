"""
QRAuthService — сервис для управления QR код авторизацией.

Обеспечивает создание QR кодов для авторизации через Telegram,
проверку статуса сессий и управление жизненным циклом сессий.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable, Dict, Optional

import aiofiles

if TYPE_CHECKING:
    from src.protocols import IApplicationState
    from src.settings.repositories.telegram_auth import TelegramAuthRepository

from typing import Any, Coroutine, Union

from telethon import TelegramClient
from telethon.tl.functions.auth import ExportLoginTokenRequest

from .models import QRAuthSession
from .session_monitor import SessionMonitor, cleanup_old_qr_sessions

logger = logging.getLogger(__name__)


class QRAuthService:
    """
    Сервис для управления QR код авторизацией.

    Обеспечивает создание QR кодов для авторизации через Telegram,
    проверку статуса сессий и управление жизненным циклом сессий.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        session_path: str = "./sessions",
        on_auth_complete: Optional[Callable[[str, Optional["IApplicationState"]], Union[None, Coroutine[Any, Any, None]]]] = None,
        state: Optional["IApplicationState"] = None,
        telegram_auth_repo: Optional["TelegramAuthRepository"] = None,
    ):
        """
        Инициализировать сервис QR авторизации.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session_path: Путь к файлам сессий
            on_auth_complete: Callback вызываемый после успешной авторизации
            state: Состояние приложения
            telegram_auth_repo: Репозиторий для управления авторизацией Telegram
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = session_path
        self._active_sessions: Dict[str, QRAuthSession] = {}
        self._client: Optional[TelegramClient] = None
        self._lock = asyncio.Lock()
        self._monitor_tasks: Dict[str, asyncio.Task] = {}
        self._on_auth_complete = on_auth_complete
        self._state = state
        self._telegram_auth_repo = telegram_auth_repo

    def set_state(self, state: "IApplicationState") -> None:
        """Установить состояние приложения после инициализации."""
        self._state = state

    async def _cleanup_old_qr_sessions(self) -> None:
        """
        Очистка старых QR сессий с диска.

        Удаляет все QR сессии которые:
        - Не авторизованы (файл < 30KB)
        - Созданы более 5 минут назад (по времени модификации файла)
        - Отсутствуют в базе данных (не являются активной сессией)
        """
        # Получаем активную сессию из БД для передачи в cleanup
        auth = await self._telegram_auth_repo.get() if self._telegram_auth_repo else None
        active_session_name = auth.session_name.value if auth and auth.session_name else None
        
        await cleanup_old_qr_sessions(self.session_path, active_session_name)

    async def _ensure_session_directory(self) -> None:
        """Создать директорию сессий если не существует."""
        if not os.path.exists(self.session_path):
            os.makedirs(self.session_path, exist_ok=True)
            logger.info("Создана директория сессий: %s", self.session_path)

    async def _cancel_active_sessions(self) -> None:
        """Отменить все активные сессии перед созданием новой."""
        async with self._lock:
            if not self._active_sessions:
                return

            logger.info(
                f"Отмена {len(self._active_sessions)} активной(ых) сессии(й) перед созданием новой"
            )
            for old_session_id in list(self._active_sessions.keys()):
                old_session = self._active_sessions.get(old_session_id)

                # НЕ удаляем авторизованные сессии!
                if old_session and old_session.is_completed:
                    logger.info("Сессия %s авторизована, не удаляем", old_session_id)
                    continue

                # Отменяем задачу мониторинга
                if old_session_id in self._monitor_tasks:
                    self._monitor_tasks[old_session_id].cancel()
                    del self._monitor_tasks[old_session_id]

                # Получаем данные сессии перед удалением
                session_name_to_delete = self._active_sessions[
                    old_session_id
                ].session_name

                # Удаляем сессию из памяти
                del self._active_sessions[old_session_id]

                logger.info("Сессия %s отменена из памяти", old_session_id)

                # Отключаем клиент если это текущая сессия
                if self._client:
                    try:
                        await self._client.disconnect()
                    except Exception:
                        pass

                # Удаляем файл сессии
                session_file = f"{self.session_path}/{session_name_to_delete}.session"
                if os.path.exists(session_file):
                    try:
                        os.remove(session_file)
                        logger.info("Удалён файл сессии: %s", session_file)
                    except Exception as e:
                        logger.error("Ошибка удаления файла сессии: %s", e)

    async def stop_all_sessions(self) -> None:
        """
        Остановить все активные сессии мониторинга.

        Вызывается при logout для полной остановки всех задач мониторинга.
        """
        async with self._lock:
            # Отменяем все задачи мониторинга
            for session_id, task in list(self._monitor_tasks.items()):
                if not task.done():
                    logger.info("Остановка задачи мониторинга %s", session_id)
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.info("Задача мониторинга %s остановлена", session_id)

            self._monitor_tasks.clear()

            # Отключаем клиент
            if self._client:
                try:
                    await self._client.disconnect()
                    self._client = None
                    logger.info("TelegramClient отключён")
                except Exception as e:
                    logger.error("Ошибка отключения клиента: %s", e)

    async def _create_telegram_client(self, session_file: str) -> TelegramClient:
        """
        Создать TelegramClient с указанной сессией.

        Args:
            session_file: Путь к файлу сессии

        Returns:
            Подключенный TelegramClient.

        Raises:
            Exception: При ошибке создания или подключения клиента.
        """
        logger.info("Создание TelegramClient с сессией: %s", session_file)

        try:
            # Создаем клиент с настройками подключения для Docker
            client = TelegramClient(
                session_file,
                self.api_id,
                self.api_hash,
                connection_retries=5,
                retry_delay=2,
                timeout=30,
            )
        except Exception as client_error:
            logger.error("Ошибка создания TelegramClient: %s", client_error)
            logger.error("session_path=%s, session_file=%s", self.session_path, session_file)
            # Проверяем права доступа к директории
            if os.path.exists(self.session_path):
                logger.info("Директория существует: %s", self.session_path)
                logger.info(
                    "Права доступа: %s", oct(os.stat(self.session_path).st_mode)
                )
            else:
                logger.error("Директория не существует: %s", self.session_path)
            raise

        # Подключаемся с явным указанием сервера
        try:
            await client.connect()
            logger.info("TelegramClient успешно подключен")
        except Exception as connect_error:
            logger.error("Ошибка подключения к Telegram: %s", connect_error)
            # Пробуем альтернативные серверы
            logger.info("Попытка подключения через альтернативные серверы...")
            await client.disconnect()
            await client.connect()
            raise

        return client

    async def _export_login_token(self, client: TelegramClient) -> bytes:
        """
        Экспортировать токен авторизации из клиента.

        Args:
            client: TelegramClient для экспорта токена

        Returns:
            Байты токена авторизации.
        """
        result = await client(
            ExportLoginTokenRequest(
                api_id=self.api_id,
                api_hash=self.api_hash,
                except_ids=[],
            )
        )
        return result.token

    async def _create_qr_session(
        self,
        session_id: str,
        session_name: str,
        token: bytes,
    ) -> QRAuthSession:
        """
        Создать объект QRAuthSession.

        Args:
            session_id: ID сессии
            session_name: Имя файла сессии
            token: Токен авторизации

        Returns:
            Новый объект QRAuthSession.
        """
        from datetime import timedelta

        from .qr_generator import create_qr_image, generate_qr_data

        qr_data = generate_qr_data(token)
        qr_image = create_qr_image(qr_data)

        return QRAuthSession(
            session_id=session_id,
            session_name=session_name,
            qr_code_data=qr_image,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5),
            is_completed=False,
        )

    async def _start_session_monitoring(self, session: QRAuthSession) -> None:
        """
        Запустить фоновую задачу мониторинга авторизации.

        Args:
            session: Сессия для мониторинга
        """
        monitor = SessionMonitor(
            self, session.session_id, self.api_id, self.api_hash, self.session_path
        )
        task = asyncio.create_task(monitor.run())
        monitor._task = task  # Сохраняем ссылку на задачу
        self._monitor_tasks[session.session_id] = task

    async def create_session(self) -> QRAuthSession:
        """
        Создать новую сессию QR авторизации.

        Returns:
            Новая сессия авторизации.

        Raises:
            Exception: При ошибке создания сессии.
        """
        session_id = str(uuid.uuid4())
        session_name = f"qr_auth_{session_id}"

        try:
            # 1. Создаём директорию сессий
            await self._ensure_session_directory()

            # 2. Отменяем все активные сессии
            await self._cancel_active_sessions()

            # 3. Дополнительно проверяем наличие старых QR сессий на диске
            await self._cleanup_old_qr_sessions()

            # 4. Создаем клиент с корректным путём к сессии
            session_file = os.path.join(self.session_path, session_name)
            self._client = await self._create_telegram_client(session_file)

            # 5. Экспортируем токен авторизации
            token = await self._export_login_token(self._client)

            # 6. Создаём объект сессии
            session = await self._create_qr_session(session_id, session_name, token)

            # 7. Сохраняем сессию и запускаем мониторинг
            async with self._lock:
                self._active_sessions[session_id] = session
                await self._start_session_monitoring(session)

            logger.info(
                f"Создана сессия QR авторизации: {session_id}, файл: {session_file}"
            )

            return session

        except Exception as e:
            logger.error("Ошибка создания QR сессии: %s", e)
            raise

    async def _on_auth_success(self, session_id: str) -> None:
        """
        Обработка успешной авторизации.

        Args:
            session_id: ID сессии
        """
        async with self._lock:
            if session_id not in self._active_sessions:
                return

            session = self._active_sessions[session_id]

            try:
                # Получаем информацию о пользователе (проверка self._client)
                if self._client is None:
                    logger.error("TelegramClient не подключен в _on_auth_success")
                    session.error = "Client not connected"
                    return

                me = await self._client.get_me()
                session.is_completed = True
                session.user_id = me.id
                session.user_username = me.username

                logger.info("Авторизация завершена: %s (%s)", me.username, me.id)

                # Отключаем клиент - сессия автоматически сохранится в файл
                await self._client.disconnect()
                self._client = None

                # Читаем файл сессии в bytes и сохраняем в БД
                session_file = f"{self.session_path}/{session.session_name}.session"
                
                # Проверка существования файла
                if not os.path.exists(session_file):
                    logger.warning("Файл сессии не найден: %s", session_file)
                    session.saved_to_db = False
                    return

                # Проверка размера файла перед чтением (защита от DoS + валидация MIN_SIZE)
                MAX_SESSION_SIZE = 10 * 1024 * 1024  # 10MB
                file_size = os.path.getsize(session_file)
                
                # Проверка минимального размера (SessionData.MIN_SIZE = 28KB)
                from ..domain.value_objects import SessionData
                if file_size < SessionData.MIN_SIZE:
                    logger.error("Файл сессии меньше минимального размера: %s bytes (минимум %s bytes)", file_size, SessionData.MIN_SIZE)
                    session.error = "Invalid session file"
                    return
                
                if file_size > MAX_SESSION_SIZE:
                    logger.error("Файл сессии превышает лимит: %s bytes", file_size)
                    session.error = "Invalid session file"
                    return
                
                # Асинхронное чтение файла
                try:
                    async with aiofiles.open(session_file, 'rb') as f:
                        session_data_bytes = await f.read()

                    logger.info("Файл сессии прочитан: %d bytes", len(session_data_bytes))

                    # Валидация через SessionData VO
                    session_data_vo = SessionData(session_data_bytes)

                    # Сохранение в БД через репозиторий (передаём VO)
                    if self._telegram_auth_repo:
                        await self._telegram_auth_repo.save_session_data_vo(
                            session.session_name,
                            session_data_vo
                        )
                        logger.info("Сессия сохранена в БД")
                    else:
                        logger.error("TelegramAuthRepository не инициализирован")

                    session.saved_to_db = True
                    
                except FileNotFoundError:
                    logger.warning("Файл сессии не найден: %s", session_file)
                    session.saved_to_db = False
                except OSError as e:
                    logger.error("Ошибка чтения файла: %s", e, exc_info=True)
                    session.error = "Invalid session file"
                except ValueError as e:
                    logger.error("Валидация session_data не прошла: %s", e)
                    session.error = "Invalid session data"
                except Exception as e:
                    logger.error("Ошибка обработки авторизации: %s", e, exc_info=True)
                    session.error = f"Auth failed: {type(e).__name__}"

                # Вызываем callback для перезапуска Ingester
                if self._on_auth_complete:
                    try:
                        if asyncio.iscoroutinefunction(self._on_auth_complete):
                            task = asyncio.create_task(self._on_auth_complete(session.session_name, self._state))
                            task.add_done_callback(
                                lambda t: logger.error("Ошибка в callback on_auth_complete: %s", t.exception())
                                if t.exception()
                                else None
                            )
                        else:
                            self._on_auth_complete(session.session_name, self._state)
                    except Exception as e:
                        logger.error("Критическая ошибка callback on_auth_complete: %s", e)

            except Exception as e:
                logger.error("Ошибка обработки успешной авторизации: %s", e, exc_info=True)
                session.error = f"Auth failed: {type(e).__name__}"

    async def check_session_status(self, session_id: str) -> dict:
        """
        Проверить статус сессии.

        Args:
            session_id: ID сессии

        Returns:
            Словарь со статусом сессии.
        """
        async with self._lock:
            if session_id not in self._active_sessions:
                return {"exists": False, "error": "Сессия не найдена"}

            session = self._active_sessions[session_id]

            if session.is_completed:
                return {
                    "exists": True,
                    "is_completed": True,
                    "user_id": session.user_id,
                    "user_username": session.user_username,
                    "saved_to_db": session.saved_to_db,
                    "reconnect_attempted": session.reconnect_attempted,
                }

            if datetime.now() > session.expires_at:
                session.error = "Сессия истекла"
                return {"exists": True, "is_expired": True, "error": "Сессия истекла"}

        # Сессия активна, но еще не авторизована
        return {
            "exists": True,
            "is_completed": False,
            "is_expired": False,
            "message": "Ожидание сканирования QR кода",
        }

    async def _cancel_single_session(self, session_id: str) -> bool:
        """
        Отменить отдельную сессию без блокировки.

        Args:
            session_id: ID сессии

        Returns:
            True если успешно отменена.
        """
        if session_id not in self._active_sessions:
            return False

        session = self._active_sessions[session_id]

        # НЕ удаляем авторизованные сессии!
        if session.is_completed:
            logger.info("Сессия %s авторизована, не удаляем", session_id)
            return False

        # Отменяем задачу мониторинга
        if session_id in self._monitor_tasks:
            self._monitor_tasks[session_id].cancel()
            del self._monitor_tasks[session_id]

        # Закрываем клиент
        if self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.error("Ошибка отключения клиента: %s", e)

        # Удаляем файл сессии
        session_file = f"{self.session_path}/{session.session_name}.session"
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info("Удалён файл сессии: %s", session_file)
            except Exception as e:
                logger.error("Ошибка удаления файла сессии: %s", e)

        # Удаляем сессию из памяти
        del self._active_sessions[session_id]
        logger.info("Сессия %s отменена", session_id)
        return True

    async def cancel_session(self, session_id: str) -> bool:
        """
        Отменить сессию авторизации.

        Args:
            session_id: ID сессии

        Returns:
            True если успешно отменена.
        """
        async with self._lock:
            return await self._cancel_single_session(session_id)

    async def _reconnect_after_delay(self, session_name: str, delay: int):
        """
        Выполнить переподключение через заданное время.

        Проверяет авторизацию сессии и выполняет переподключение.
        Если сессия не авторизована, продолжает проверки каждую минуту.

        Args:
            session_name: Имя файла сессии
            delay: Задержка в секундах
        """
        session_file = f"{self.session_path}/{session_name}.session"
        
        # Ограничение максимального времени переподключения
        MAX_RECONNECT_DURATION = timedelta(hours=1)
        start_time = datetime.now()

        while True:
            # Проверка превышения максимального времени
            if datetime.now() - start_time > MAX_RECONNECT_DURATION:
                logger.error("Превышено максимальное время переподключения (1 час)")
                break
            
            logger.info("Ожидание %s секунд перед проверкой сессии...", delay)
            await asyncio.sleep(delay)

            try:
                # Проверяем существование файла сессии
                if not os.path.exists(session_file):
                    logger.warning(
                        "Файл сессии не найден: %s, повторная попытка...", session_file
                    )
                    delay = 60  # Продолжаем проверки каждую минуту
                    continue

                # Создаем новый клиент с сохраненной сессией
                client = TelegramClient(
                    session_file,
                    self.api_id,
                    self.api_hash,
                )

                await client.connect()

                if await client.is_user_authorized():
                    me = await client.get_me()
                    logger.info("Переподключение успешно: %s (%s)", me.username, me.id)

                    # Обновляем статус сессии если она еще существует
                    async with self._lock:
                        for sid, session in self._active_sessions.items():
                            if session.session_name == session_name:
                                session.reconnect_attempted = True
                                break

                    await client.disconnect()

                    # Вызываем callback если есть
                    if self._on_auth_complete:
                        try:
                            # Callback может быть async или sync
                            if asyncio.iscoroutinefunction(self._on_auth_complete):
                                asyncio.create_task(self._on_auth_complete(session_name, self._state))
                            else:
                                self._on_auth_complete(session_name, self._state)
                        except Exception as e:
                            logger.error("Ошибка callback on_auth_complete: %s", e)

                    break  # Успешно - выходим из цикла
                else:
                    logger.warning(
                        "Сессия не авторизована, повторная попытка через 1 минуту..."
                    )
                    await client.disconnect()
                    delay = 60  # Продолжаем проверки каждую минуту

            except Exception as e:
                logger.error("Ошибка переподключения: %s", e)
                delay = 60  # Продолжаем попытки

    async def close(self) -> None:
        """Закрыть все активные сессии."""
        async with self._lock:
            # Отменяем все задачи мониторинга
            for session_id in list(self._monitor_tasks.keys()):
                self._monitor_tasks[session_id].cancel()
            self._monitor_tasks.clear()

            # Отменяем все сессии
            for session_id in list(self._active_sessions.keys()):
                if self._client:
                    try:
                        await self._client.disconnect()
                    except Exception as e:
                        logger.error("Ошибка отключения клиента: %s", e)

            self._active_sessions.clear()

            if self._client:
                try:
                    await self._client.disconnect()
                except Exception as e:
                    logger.error("Ошибка отключения клиента: %s", e)
                self._client = None

    @property
    def active_sessions(self) -> Dict[str, QRAuthSession]:
        """Получить активные сессии."""
        return self._active_sessions.copy()

    @property
    def is_client_connected(self) -> bool:
        """Проверить подключение клиента."""
        return self._client is not None and self._client.is_connected()
