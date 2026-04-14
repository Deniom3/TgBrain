"""
Интеграционные тесты для TelegramAuthRepository.

Тестируют работу с сессиями и session_data в БД.
"""

import pytest

from src.domain.value_objects import SessionData

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_save_session_data(telegram_auth_repo, db_pool_with_session_data):
    """
    Сохранение session_data в БД.
    
    Проверяет:
    - Сохранение бинарных данных сессии
    - Чтение сохранённых данных
    - Корректность данных после чтения
    """
    session_name = "test_session_data_save"
    session_data = b"test_binary_session_data_" + b"0" * (SessionData.MIN_SIZE - 25)
    
    result = await telegram_auth_repo.save_session_data(
        session_name, session_data
    )
    
    assert result is None
    
    saved_data = await telegram_auth_repo.get_session_data()
    assert saved_data is not None
    assert saved_data == session_data


@pytest.mark.asyncio
async def test_get_session_data_not_found(telegram_auth_repo, db_pool_with_session_data):
    """
    Получение несуществующей session_data.
    
    Проверяет:
    - Возврат None при отсутствии данных
    - Отсутствие ошибок при чтении пустой записи
    """
    async with db_pool_with_session_data.acquire() as conn:
        await conn.execute("UPDATE telegram_auth SET session_data = NULL WHERE id = 1")
    
    result = await telegram_auth_repo.get_session_data()
    assert result is None


@pytest.mark.asyncio
async def test_upsert_with_session_data(telegram_auth_repo, db_pool_with_session_data):
    """
    Upsert с session_data.
    
    Проверяет:
    - Сохранение всех полей авторизации включая session_data
    - Корректное чтение всех полей
    - Целостность session_data после upsert
    """
    test_api_id = 12345
    test_api_hash = "test_hash_abc1234567890123456789"
    test_session_name = "test_upsert_session"
    test_session_data = b"upsert_test_session_data_bytes_" + b"0" * (SessionData.MIN_SIZE - 32)
    
    auth = await telegram_auth_repo.upsert(
        api_id=test_api_id,
        api_hash=test_api_hash,
        session_name=test_session_name,
        session_data=test_session_data,
    )
    
    assert auth is not None
    assert auth.api_id.value == test_api_id
    assert auth.api_hash.value == test_api_hash
    assert auth.session_name.value == test_session_name
    
    saved_data = await telegram_auth_repo.get_session_data()
    assert saved_data is not None
    assert saved_data == test_session_data
    
    retrieved = await telegram_auth_repo.get()
    assert retrieved is not None
    assert retrieved.session_name.value == test_session_name
