"""
Мапперы для конвертации между domain и infrastructure моделями.

Модуль предоставляет функции для преобразования моделей данных
между доменным слоем (с Value Objects) и слоем персистентности
(с примитивными типами).

Разделение ответственности:
- Domain слой (TelegramAuth): Не знает о session_data - это деталь реализации
- Infrastructure слой (TelegramAuthDB): Хранит session_data для персистентности
- Мапперы: Конвертируют между слоями, session_data передаётся отдельно
"""

from __future__ import annotations

import logging
from typing import Optional

from ...domain.models.auth import TelegramAuth as DomainTelegramAuth
from ...domain.value_objects import ApiId, ApiHash, PhoneNumber, SessionName
from ...infrastructure.persistence.models import TelegramAuthDB
from ...models.data_models import TelegramAuth as DataModelTelegramAuth

logger = logging.getLogger(__name__)


def to_domain(auth_db: TelegramAuthDB) -> DomainTelegramAuth:
    """
    Конвертировать infrastructure модель в domain.

    Args:
        auth_db: Infrastructure модель с примитивными типами.

    Returns:
        Domain модель с Value Objects.

    Raises:
        ValueError: Если данные не проходят валидацию Value Objects.

    Примечание:
        session_data игнорируется - Domain модель не должна знать
        о деталях хранения сессии (Clean Architecture).
    """
    try:
        api_id = ApiId(auth_db.api_id) if auth_db.api_id is not None else None
    except ValueError as e:
        logger.warning(f"Invalid api_id: {e}")
        api_id = None

    try:
        api_hash = ApiHash(auth_db.api_hash) if auth_db.api_hash is not None else None
    except ValueError as e:
        logger.warning(f"Invalid api_hash: {e}")
        api_hash = None

    try:
        phone_number = PhoneNumber(auth_db.phone_number) if auth_db.phone_number is not None else None
    except ValueError as e:
        logger.warning(f"Invalid phone_number: {e}")
        phone_number = None

    try:
        session_name = SessionName(auth_db.session_name) if auth_db.session_name is not None else None
    except ValueError as e:
        logger.warning(f"Invalid session_name: {e}")
        session_name = None

    return DomainTelegramAuth(
        id=auth_db.id,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        session_name=session_name,
        updated_at=auth_db.updated_at,
    )


def from_domain(
    auth: DomainTelegramAuth,
    session_data: Optional[bytes] = None,
) -> TelegramAuthDB:
    """
    Конвертировать domain модель в infrastructure.

    Args:
        auth: Domain модель с Value Objects.
        session_data: Данные сессии (передаются отдельно от domain модели).

    Returns:
        Infrastructure модель с примитивными типами.

    Примечание:
        session_data передаётся отдельно - Domain модель не знает
        о деталях хранения сессии (Clean Architecture).
    """
    return TelegramAuthDB(
        id=auth.id,
        api_id=auth.api_id.value if auth.api_id is not None else None,
        api_hash=auth.api_hash.value if auth.api_hash is not None else None,
        phone_number=auth.phone_number.value if auth.phone_number is not None else None,
        session_name=auth.session_name.value if auth.session_name is not None else None,
        session_data=session_data,
        updated_at=auth.updated_at,
    )


def to_data_model(auth_db: TelegramAuthDB) -> DataModelTelegramAuth:
    """
    Конвертировать infrastructure модель в data_models.TelegramAuth.

    Эта функция используется для обратной совместимости с кодом,
    который использует TelegramAuth из src.models.data_models.

    Args:
        auth_db: Infrastructure модель с примитивными типами.

    Returns:
        Data model с Value Objects.

    Raises:
        ValueError: Если данные не проходят валидацию Value Objects.

    Примечание:
        DataModelTelegramAuth НЕ имеет поля session_data (это domain модель),
        поэтому session_data игнорируется при конвертации.
    """
    try:
        api_id = ApiId(auth_db.api_id) if auth_db.api_id is not None else None
    except ValueError as e:
        logger.warning(f"Invalid api_id: {e}")
        api_id = None

    try:
        api_hash = ApiHash(auth_db.api_hash) if auth_db.api_hash is not None else None
    except ValueError as e:
        logger.warning(f"Invalid api_hash: {e}")
        api_hash = None

    try:
        phone_number = PhoneNumber(auth_db.phone_number) if auth_db.phone_number is not None else None
    except ValueError as e:
        logger.warning(f"Invalid phone_number: {e}")
        phone_number = None

    try:
        session_name = SessionName(auth_db.session_name) if auth_db.session_name is not None else None
    except ValueError as e:
        logger.warning(f"Invalid session_name: {e}")
        session_name = None

    return DataModelTelegramAuth(
        id=auth_db.id,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        session_name=session_name,
        # session_data не передаётся - DataModelTelegramAuth это domain модель
        updated_at=auth_db.updated_at,
    )


def from_data_model(auth: DataModelTelegramAuth) -> TelegramAuthDB:
    """
    Конвертировать data_models.TelegramAuth в infrastructure.

    Эта функция используется для обратной совместимости с кодом,
    который использует TelegramAuth из src.models.data_models.

    Args:
        auth: Data model с Value Objects.

    Returns:
        Infrastructure модель с примитивными типами.

    Примечание:
        DataModelTelegramAuth НЕ имеет поля session_data (это domain модель),
        поэтому session_data устанавливается в None.
    """
    return TelegramAuthDB(
        id=auth.id,
        api_id=auth.api_id.value if auth.api_id is not None else None,
        api_hash=auth.api_hash.value if auth.api_hash is not None else None,
        phone_number=auth.phone_number.value if auth.phone_number is not None else None,
        session_name=auth.session_name.value if auth.session_name is not None else None,
        session_data=None,
        updated_at=auth.updated_at,
    )
