"""
Сервис миграции session_data из файлов в БД.

Назначение:
- Чтение файлов сессии
- Сохранение session_data в БД
- Верификация данных
- Управление транзакциями
"""

import logging
from pathlib import Path
from typing import Any, Protocol

import asyncpg

from .session_backup_service import SessionBackupService, BackupError
from .session_validator import SessionValidator, SessionValidationError

logger = logging.getLogger(__name__)


class DatabaseConnection(Protocol):
    """Протокол для подключения к БД."""

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        """Получить одну строку."""
        ...

    async def fetchval(self, query: str, *args) -> Any:
        """Получить одно значение."""
        ...

    async def execute(self, query: str, *args) -> str:
        """Выполнить запрос."""
        ...

    def transaction(self) -> Any:
        """Контекстный менеджер транзакции."""
        ...


class MigrationError(Exception):
    """Исключение ошибки миграции."""

    def __init__(self, message: str, code: str = "MIGRATION_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class SessionMigrationService:
    """Сервис миграции session_data из файлов в БД."""

    def __init__(
        self,
        db_connection: DatabaseConnection,
        backup_service: SessionBackupService,
        validator: SessionValidator | None = None
    ) -> None:
        """
        Инициализация сервиса миграции.

        Args:
            db_connection: Подключение к БД.
            backup_service: Сервис бэкапа.
            validator: Валидатор сессий.
        """
        self._conn = db_connection
        self._backup_service = backup_service
        self._validator = validator or SessionValidator()

    async def _migrate_auth_tables(self) -> None:
        """
        Выполнить DDL миграцию таблицы telegram_auth.

        Добавляет колонку session_data и удаляет session_path.
        """
        await self.ensure_session_data_column()
        await self.remove_session_path_column()
        logger.info("DDL migration completed")

    async def get_session_info(self) -> tuple[str, str] | None:
        """
        Получить информацию о сессии из БД.

        Returns:
            Кортеж (session_name, session_path) или None.
        """
        row = await self._conn.fetchrow(
            "SELECT session_name, session_path FROM telegram_auth WHERE id = 1"
        )

        if row is None:
            return None

        session_name = row["session_name"] or "qr_auth_session"
        session_path = row["session_path"] or "./sessions"

        logger.info(f"Session info loaded: name={session_name}, path={session_path}")
        return session_name, session_path

    async def ensure_session_data_column(self) -> None:
        """Добавить колонку session_data BYTEA если отсутствует."""
        exists = await self._conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'telegram_auth'
                AND column_name = 'session_data'
            )
            """
        )

        if exists:
            logger.info("Column session_data already exists")
            return

        async with self._conn.transaction():
            await self._conn.execute(
                "ALTER TABLE telegram_auth ADD COLUMN session_data BYTEA DEFAULT NULL"
            )

        logger.info("Column session_data BYTEA DEFAULT NULL added")

    async def remove_session_path_column(self) -> None:
        """Удалить колонку session_path если существует."""
        exists = await self._conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'telegram_auth'
                AND column_name = 'session_path'
            )
            """
        )

        if not exists:
            logger.info("Column session_path does not exist")
            return

        async with self._conn.transaction():
            await self._conn.execute(
                "ALTER TABLE telegram_auth DROP COLUMN session_path"
            )

        logger.info("Column session_path removed")

    def find_session_file(
        self,
        session_name: str,
        session_path: str,
        search_paths: list[Path] | None = None
    ) -> Path | None:
        """
        Найти файл сессии.

        Args:
            session_name: Имя сессии.
            session_path: Путь из БД.
            search_paths: Дополнительные пути для поиска.

        Returns:
            Путь к файлу или None.
        """
        # Убираем дубли: используем set для уникальных путей
        default_paths = [
            Path("./sessions") / f"{session_name}.session",
            Path(session_path) / f"{session_name}.session",
        ]

        if search_paths:
            all_paths = default_paths + search_paths
        else:
            all_paths = default_paths

        for path in all_paths:
            if path.exists():
                logger.info(f"Session file found: {path}")
                return path

        logger.warning(f"Session file not found in paths: {all_paths}")
        return None

    async def save_session_data(self, session_data: bytes) -> None:
        """
        Сохранить session_data в БД.

        Args:
            session_data: Бинарные данные сессии.
        """
        self._validator.validate_session_data(session_data)

        async with self._conn.transaction():
            await self._conn.execute(
                "UPDATE telegram_auth SET session_data = $1 WHERE id = 1",
                session_data
            )

        logger.info(f"Session data saved: {len(session_data)} bytes")

    async def verify_session_data(self) -> int:
        """
        Проверить сохранность данных в БД.

        Returns:
            Размер session_data в байтах.

        Raises:
            MigrationError: Если данные не найдены или пусты.
        """
        data_size = await self._conn.fetchval(
            "SELECT LENGTH(session_data) FROM telegram_auth WHERE id = 1"
        )

        if data_size is None:
            raise MigrationError(
                "Session data not found in database",
                "DATA_NOT_FOUND"
            )

        if data_size == 0:
            raise MigrationError(
                "Session data is empty in database",
                "DATA_EMPTY"
            )

        logger.info(f"Session data verified: {data_size} bytes")
        return data_size

    async def migrate(self) -> dict:
        """
        Выполнить миграцию session_data.

        Returns:
            Статус миграции с метаданными.

        Raises:
            MigrationError: Если миграция не удалась.
        """
        result: dict[str, Any] = {
            "success": False,
            "session_name": None,
            "session_file": None,
            "backup_path": None,
            "data_size": 0,
        }

        try:
            session_info = await self.get_session_info()
            if session_info is None:
                raise MigrationError(
                    "Telegram auth record not found in database",
                    "AUTH_NOT_FOUND"
                )

            session_name, session_path = session_info
            result["session_name"] = session_name

            session_file = self.find_session_file(session_name, session_path)
            if session_file is None:
                raise MigrationError(
                    f"Session file not found: {session_name}.session",
                    "SESSION_FILE_NOT_FOUND"
                )

            result["session_file"] = str(session_file)

            backup_path = self._backup_service.create_backup(session_file)
            result["backup_path"] = str(backup_path)

            session_data = self._read_session_file(session_file)
            await self.save_session_data(session_data)

            data_size = await self.verify_session_data()
            result["data_size"] = data_size
            result["success"] = True

            logger.info("Migration completed successfully")
            return result

        except SessionValidationError as e:
            raise MigrationError(f"Validation error: {e.message}", e.code)
        except BackupError as e:
            raise MigrationError(f"Backup error: {e.message}", e.code)

    def _read_session_file(self, session_file: Path) -> bytes:
        """
        Прочитать файл сессии.

        Args:
            session_file: Путь к файлу.

        Returns:
            Бинарные данные.

        Raises:
            MigrationError: Если файл превышает лимит 10MB.
        """
        # Проверка лимита размера (10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        file_size = session_file.stat().st_size
        
        if file_size > max_size:
            raise MigrationError(
                f"Session file too large: {file_size} bytes (max {max_size} bytes)",
                "FILE_TOO_LARGE"
            )
        
        with open(session_file, "rb") as f:
            data = f.read()

        logger.info(f"Session file read: {len(data)} bytes")
        return data
