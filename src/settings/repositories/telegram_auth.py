"""
Репозиторий для управления авторизацией Telegram.

Использует Value Objects для всех полей авторизации.
"""

import importlib
import logging
import pickle
from typing import TYPE_CHECKING, Optional

import asyncpg

from ...auth import DEFAULT_SESSION_PATH
from ...domain.models.auth import TelegramAuth as DomainTelegramAuth
from ...infrastructure.persistence.models import TelegramAuthDB
from ...models.sql import (
    SQL_UPSERT_TELEGRAM_AUTH,
    SQL_GET_TELEGRAM_AUTH,
    SQL_CREATE_SESSION_NAME_INDEX,
    SQL_CLEAR_SESSION,
)

if TYPE_CHECKING:
        from ...domain.value_objects import SessionData

logger = logging.getLogger(__name__)


class RestrictedUnpickler(pickle.Unpickler):
    """
    Безопасная десериализация — разрешает только классы Telethon и builtins.
    
    SECURITY: Предотвращает RCE атаки при компрометации БД или ключа шифрования.
    Разрешает только:
    - Классы сессий Telethon из модуля telethon.sessions
    - Builtins типы (dict, list, str, int, bytes, None) для старых форматов сессий
    
    Note: Telethon session может быть сериализована как MemorySession объект
    или как dict с полями (_dc_id, _server_address, _port, и т.д.).
    """

    # Разрешённые builtins типы для поддержки старых форматов сессий
    ALLOWED_BUILTINS = {
        "dict", "list", "tuple", "set", "frozenset",
        "str", "bytes", "int", "float", "bool", "NoneType"
    }

    def find_class(self, module: str, name: str) -> object:
        """
        Разрешить только классы сессий Telethon и безопасные builtins.
        
        Args:
            module: Имя модуля
            name: Имя класса
            
        Returns:
            Класс если разрешён
            
        Raises:
            pickle.UnpicklingError: Если класс запрещён
        """
        # Разрешить классы сессий Telethon
        if module.startswith("telethon.sessions"):
            try:
                mod = importlib.import_module(module)
                return getattr(mod, name)
            except (ImportError, AttributeError) as e:
                raise pickle.UnpicklingError(f"Cannot import '{module}.{name}': {e}")
        
        # Разрешить builtins типы для старых форматов сессий
        if module == "builtins" and name in self.ALLOWED_BUILTINS:
            return getattr(__import__(module), name)
        
        # Запретить все остальные классы
        raise pickle.UnpicklingError(f"Global '{module}.{name}' is forbidden")


class TelegramAuthRepository:
    """Репозиторий для управления авторизации Telegram."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        """
        Инициализировать репозиторий.

        Args:
            pool: Пул подключений к БД.
        """
        self._pool = pool

    async def upsert(
        self,
        api_id: Optional[int] = None,
        api_hash: Optional[str] = None,
        phone_number: Optional[str] = None,
        session_name: Optional[str] = None,
        session_data: Optional[bytes] = None,
    ) -> Optional[DomainTelegramAuth]:
        """
        Сохранить или обновить настройки авторизации Telegram.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone_number: Номер телефона
            session_name: Имя сессии (без хардкода)
            session_data: Данные сессии (bytes)

        Returns:
            Сохранённые настройки или None при ошибке.

        Raises:
            ValueError: Если данные не проходят валидацию.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    SQL_UPSERT_TELEGRAM_AUTH,
                    api_id, api_hash, phone_number, session_name, session_data,
                )
                if row:
                    row_dict = dict(row)
                    logger.debug("Данные Telegram auth сохранены в БД")

                    auth_db = TelegramAuthDB(
                        id=row_dict.get('id', 1),
                        api_id=row_dict.get('api_id'),
                        api_hash=row_dict.get('api_hash'),
                        phone_number=row_dict.get('phone_number'),
                        session_name=row_dict.get('session_name'),
                        session_data=row_dict.get('session_data'),
                        updated_at=row_dict.get('updated_at'),
                    )

                    from ...common.mappers import to_domain
                    return to_domain(auth_db)
                return None
            except ValueError as e:
                logger.error("Invalid TelegramAuth data: %s", e)
                raise
            except Exception as e:
                logger.error("Ошибка сохранения Telegram auth: %s", type(e).__name__)
                return None

    async def get(self) -> Optional[DomainTelegramAuth]:
        """
        Получить настройки авторизации Telegram.

        Returns:
            Настройки авторизации или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(SQL_GET_TELEGRAM_AUTH)
                if row:
                    row_dict = dict(row)
                    logger.debug("Данные Telegram auth получены из БД")

                    auth_db = TelegramAuthDB(
                        id=row_dict.get('id', 1),
                        api_id=row_dict.get('api_id'),
                        api_hash=row_dict.get('api_hash'),
                        phone_number=row_dict.get('phone_number'),
                        session_name=row_dict.get('session_name'),
                        session_data=row_dict.get('session_data'),
                        updated_at=row_dict.get('updated_at'),
                    )

                    from ...common.mappers import to_domain
                    return to_domain(auth_db)
                return None
            except Exception as e:
                logger.error("Ошибка получения Telegram auth: %s", type(e).__name__)
                return None

    async def save_session_data(self, session_name: str, session_data: bytes) -> None:
        """
        Сохранить данные сессии в БД.

        Args:
            session_name: Имя сессии
            session_data: Данные сессии (bytes)

        Raises:
            ValueError: Если session_data не проходит валидацию.
        """
        from ...domain.value_objects import SessionData

        async with self._pool.acquire() as conn:
            try:
                # Обернуть bytes в SessionData VO для валидации
                session_data_vo = SessionData(session_data)

                await conn.execute(
                    """
                    UPDATE telegram_auth
                    SET session_name = $1, session_data = $2, updated_at = NOW()
                    WHERE id = 1
                    """,
                    session_name,
                    session_data_vo.value,  # Извлечь bytes из VO
                )
                logger.debug("Данные сессии сохранены")
            except ValueError as e:
                logger.error("Invalid session_data: %s", e)
                raise
            except Exception as e:
                logger.error("Ошибка сохранения session_data: %s", e)
                raise

    async def save_session_data_vo(self, session_name: str, session_data_vo: "SessionData") -> None:
        """
        Сохранить данные сессии в БД (принимает SessionData VO).

        Args:
            session_name: Имя сессии
            session_data_vo: Данные сессии (SessionData VO)

        Raises:
            ValueError: Если session_data не проходит валидацию.
        """
        session_bytes = session_data_vo.value
        logger.info("Сохранение данных сессии в БД")

        try:
            # Используем acquire напрямую с явным коммитом
            async with self._pool.acquire() as conn:
                # Начинаем транзакцию
                tx = conn.transaction()
                await tx.start()

                try:
                    await conn.execute(
                        """
                        UPDATE telegram_auth
                        SET session_name = $1, session_data = $2, updated_at = NOW()
                        WHERE id = 1
                        """,
                        session_name,
                        session_bytes,
                    )
                    logger.debug("Session data UPDATE выполнен")

                    # Явный коммит
                    await tx.commit()

                except Exception as e:
                    logger.error("Ошибка во время транзакции: %s", type(e).__name__)
                    await tx.rollback()
                    raise

            # Проверка после коммита (новое соединение из пула)
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT session_name, session_data IS NULL as is_null FROM telegram_auth WHERE id = 1"
                )
                if row:
                    if row['is_null']:
                        logger.error("❌ Данные сессии = NULL после COMMIT!")
                        raise RuntimeError("Данные сессии = NULL после COMMIT")
                else:
                    logger.error("❌ Не удалось прочитать данные сессии после сохранения")
                    raise RuntimeError("Не удалось прочитать данные сессии")

        except ValueError as e:
            logger.error("Invalid session_data: %s", e)
            raise
        except asyncpg.PostgresError as e:
            logger.error("Ошибка БД: %s", type(e).__name__)
            raise
        except Exception as e:
            logger.error("Ошибка сохранения session_data: %s", type(e).__name__)
            raise

    async def save_session_data_v2(self, session_data: bytes) -> None:
        """
        Сохранить зашифрованные данные сессии в БД.

        SECURITY: Используется для сохранения зашифрованных session_data.
        Не требует session_name — обновляет существующую запись.

        Args:
            session_data: Зашифрованные данные сессии (bytes)

        Raises:
            asyncpg.PostgresError: Если ошибка БД.
            Exception: Если неожиданная ошибка.
        """
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    UPDATE telegram_auth
                    SET session_data = $1, updated_at = NOW()
                    WHERE id = 1
                    """,
                    session_data,
                )
                logger.debug("Encrypted session data saved")
            except asyncpg.PostgresError as e:
                logger.error("Ошибка БД: %s", type(e).__name__)
                raise
            except Exception as e:
                logger.error("Ошибка сохранения зашифрованных session_data: %s", type(e).__name__)
                raise

    async def get_session_data(self) -> Optional[bytes]:
        """
        Получить данные сессии из БД.

        Returns:
            Данные сессии (bytes) или None.
        """
        async with self._pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    "SELECT session_data FROM telegram_auth WHERE id = 1"
                )
                if row and row["session_data"]:
                    return bytes(row["session_data"])
                return None
            except Exception as e:
                logger.error("Ошибка получения session_data: %s", e)
                return None

    async def has_session_data(self) -> bool:
        """
        Проверить наличие session_data в БД.

        Returns:
            True если session_data существует и не NULL.
        """
        async with self._pool.acquire() as conn:
            try:
                result = await conn.fetchval(
                    "SELECT session_data IS NOT NULL FROM telegram_auth WHERE id = 1"
                )
                return bool(result)
            except Exception as e:
                logger.error("Ошибка проверки session_data: %s", e)
                return False

    async def create_session_name_index(self) -> None:
        """
        Создать индекс для колонки session_name.

        Ускоряет поиск сессии по имени.
        """
        async with self._pool.acquire() as conn:
            try:
                await conn.execute(SQL_CREATE_SESSION_NAME_INDEX)
                logger.info("Индекс idx_telegram_auth_session_name создан")
            except Exception as e:
                logger.error("Ошибка создания индекса: %s", e)
                raise

    async def is_configured(self) -> bool:
        """
        Проверить, настроена ли авторизация Telegram.

        Returns:
            True если api_id и api_hash настроены.
        """
        auth = await self.get()
        return bool(auth and auth.api_id and auth.api_hash)

    async def is_session_active(self) -> bool:
        """
        Проверить наличия активной сессии авторизации.

        Достаточно проверить наличие session_name и session_data в БД.

        Returns:
            True если session_name и session_data есть в БД.

        Note:
            Временный файл сессии НЕ проверяется — он создаётся в системной
            temp-директории через tempfile.mkstemp() только при запуске Ingester
            и удаляется при остановке. Для проверки авторизации достаточно
            наличия session_name и session_data в БД.
        """
        try:
            auth = await self.get()

            # Если session_name есть в БД — проверяем session_data
            if auth and auth.session_name:
                session_data = await self.get_session_data()
                if not session_data:
                    logger.warning("Session data отсутствует в БД")
                    return False

                # Сессия активна если есть session_name и session_data
                raw_name = auth.session_name.value
                masked_name = raw_name[:3] + "***" if len(raw_name) > 3 else "***"
                logger.info("Активная сессия найдена в БД: %s", masked_name)
                return True

            logger.debug("Сессия не активна: session_name отсутствует в БД")
            return False

        except Exception as e:
            logger.error("Ошибка проверки активной сессии: %s", e)
            return False

    async def clear_session(self) -> bool:
        """
        Сбросить активную сессию (logout).

        Сбрасывает session_name и session_data на NULL.
        api_id, api_hash и другие настройки сохраняются.

        Returns:
            True если успешно сброшено.
        """
        try:
            auth = await self.get()

            if not auth:
                logger.warning("Настройки Telegram не найдены в БД")
                return False

            # Используем специальный SQL для сброса сессии
            async with self._pool.acquire() as conn:
                logger.info("Выполнение SQL_CLEAR_SESSION")
                result = await conn.execute(SQL_CLEAR_SESSION)
                logger.info("Результат SQL: %s", result)

                # Проверка что данные сброшены (внутри контекста!)
                check_row = await conn.fetchrow("SELECT session_name, session_data FROM telegram_auth WHERE id = 1")
                if check_row and check_row["session_name"] is None and check_row["session_data"] is None:
                    logger.info("✅ Проверка: данные сессии = NULL")
                else:
                    logger.error("❌ Проверка не прошла")

            # Безопасное удаление файлов сессий через SessionFileService
            if auth.session_name:
                from ...services import SessionFileService

                await SessionFileService.delete_session_files(auth.session_name, DEFAULT_SESSION_PATH)

            logger.info("✅ Сессия сброшена (logout выполнен)")
            return True

        except Exception as e:
            logger.error("Ошибка сброса сессии: %s", type(e).__name__)
            return False

