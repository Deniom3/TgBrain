"""
Модуль QR авторизации Telegram.

Использует Telethon для генерации QR кодов авторизации и управления сессиями.

Пример использования:
    from src.auth import QRAuthService, QRAuthSession

    service = QRAuthService(api_id, api_hash, on_auth_complete=callback)

    # Создание сессии
    session = await service.create_session()

    # Проверка статуса
    status = await service.check_session_status(session.session_id)

    # Отмена сессии
    await service.cancel_session(session.session_id)
"""

from src.auth.models import QRAuthSession
from src.auth.qr_generator import create_qr_image, generate_qr_data
from src.auth.service import QRAuthService
from src.auth.session_backup_service import SessionBackupService
from src.auth.session_migration_service import SessionMigrationService, MigrationError
from src.auth.session_monitor import SessionMonitor, cleanup_old_qr_sessions
from src.auth.session_validator import SessionValidator, SessionValidationError

# Константы
DEFAULT_SESSION_PATH = "./sessions"

__all__ = [
    "QRAuthService",
    "QRAuthSession",
    "SessionMonitor",
    "SessionBackupService",
    "SessionMigrationService",
    "SessionValidator",
    "MigrationError",
    "SessionValidationError",
    "create_qr_image",
    "generate_qr_data",
    "cleanup_old_qr_sessions",
    "DEFAULT_SESSION_PATH",
]
