"""
Интеграционные тесты для миграции session_data.

Тестируют перенос session_data из файлов сессий в базу данных.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

pytest.importorskip("scripts.migrations.migrate_session_data")
from scripts.migrations.migrate_session_data import run_migration  # noqa: E402

pytestmark = pytest.mark.integration


@pytest.fixture
def mock_session_file():
    """Создаёт временный файл сессии для тестов."""
    temp_dir = tempfile.mkdtemp()
    session_file = os.path.join(temp_dir, "test_session.session")

    mock_session_data = b"mock_session_data_for_migration_testing_1234567890"

    with open(session_file, 'wb') as f:
        f.write(mock_session_data)

    yield session_file, mock_session_data, temp_dir

    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def backup_dir():
    """Создаёт временную директорию для бэкапа."""
    temp_backup = tempfile.mkdtemp()
    yield temp_backup
    if os.path.exists(temp_backup):
        shutil.rmtree(temp_backup)


@pytest.mark.asyncio
async def test_migrate_session_data_success(
    telegram_auth_repo,
    db_pool,
    mock_session_file,
    backup_dir,
):
    """Миграция session_data успешна."""
    session_file, mock_session_data, temp_dir = mock_session_file

    with patch('tempfile.gettempdir', return_value=temp_dir):
        with patch('glob.glob', return_value=[session_file]):
            result = await run_migration(backup_dir)

    assert result is True

    session_data = await telegram_auth_repo.get_session_data()
    assert session_data is not None
    assert len(session_data) > 0


@pytest.mark.asyncio
async def test_migrate_session_file_not_found(
    db_pool,
    backup_dir,
):
    """Миграция не удалась — файл не найден."""
    with patch('tempfile.gettempdir', return_value="/nonexistent/path"):
        with patch('glob.glob', return_value=[]):
            result = await run_migration(backup_dir)

    assert result is True


@pytest.mark.asyncio
async def test_migrate_index_created(
    db_pool,
    mock_session_file,
    backup_dir,
):
    """Миграция создаёт индекс для session_name."""
    session_file, mock_session_data, temp_dir = mock_session_file

    with patch('tempfile.gettempdir', return_value=temp_dir):
        with patch('glob.glob', return_value=[session_file]):
            result = await run_migration(backup_dir)

    assert result is True


@pytest.mark.asyncio
async def test_migrate_with_multiple_session_files(
    db_pool,
    backup_dir,
):
    """Миграция обрабатывает несколько файлов сессий."""
    temp_dir = tempfile.mkdtemp()

    session_files = []
    for i in range(3):
        session_file = os.path.join(temp_dir, f"session_{i}.session")
        with open(session_file, 'wb') as f:
            f.write(f"session_data_{i}".encode())
        session_files.append(session_file)

    try:
        with patch('tempfile.gettempdir', return_value=temp_dir):
            with patch('glob.glob', return_value=session_files):
                result = await run_migration(backup_dir)

        assert result is True
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
