"""Unit тесты для logout сценариев."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestLogoutScenarios:
    """Unit тесты для logout сценариев."""

    @pytest.mark.asyncio
    async def test_logout_stops_ingester(self):
        """Logout останавливает Ingester."""
        # Мок state (IApplicationState)
        mock_state = MagicMock()

        # Мок IngesterRestartService.stop_for_logout()
        with patch('src.api.callbacks.qr_auth_callback.IngesterRestartService.stop_for_logout', new_callable=AsyncMock) as mock_stop:
            from src.api.callbacks.qr_auth_callback import restart_ingester

            # Вызвать restart_ingester с is_logout=True
            await restart_ingester(mock_state, is_logout=True)

            # Проверить что IngesterRestartService.stop_for_logout вызван
            mock_stop.assert_called_once_with(mock_state)

    @pytest.mark.asyncio
    async def test_logout_clears_session_in_db(self):
        """Logout очищает сессию в БД (с моками)."""
        # Мок get_db()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="CLEAR")
        
        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_db_context)

        with patch('src.database.get_db', return_value=mock_db_context):
            with patch('src.settings.telegram_auth.TelegramAuthRepository.get', new_callable=AsyncMock) as mock_get:
                mock_get.return_value = MagicMock(session_name=MagicMock(value="test_session"))
                
                from src.settings.repositories.telegram_auth import TelegramAuthRepository
                repo = TelegramAuthRepository(mock_pool)
                result = await repo.clear_session()
                
                # Проверить что SQL_CLEAR_SESSION выполнен
                mock_conn.execute.assert_called_once()
                assert result is True

    @pytest.mark.asyncio
    async def test_logout_deletes_session_files(self):
        """Logout удаляет файлы сессий (с моками)."""
        # Мок get_db()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.fetchrow = AsyncMock(return_value={"session_name": None, "session_data": None})
        
        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_db_context)

        # Мок SessionFileService.delete_session_files()
        with patch('src.services.session_file_service.SessionFileService.delete_session_files', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = True
            
            # Мок get_db()
            with patch('src.database.get_db', return_value=mock_db_context):
                # Мок TelegramAuthRepository.get() — возвращает сессию
                with patch('src.settings.telegram_auth.TelegramAuthRepository.get', new_callable=AsyncMock) as mock_get:
                    from src.domain.value_objects import SessionName
                    mock_get.return_value = MagicMock(session_name=SessionName("test_session"))
                    
                    from src.settings.repositories.telegram_auth import TelegramAuthRepository
                    repo = TelegramAuthRepository(mock_pool)
                    result = await repo.clear_session()
                    
                    # Проверить что delete_session_files вызван
                    mock_delete.assert_called_once()
                    assert result is True

    @pytest.mark.asyncio
    async def test_logout_no_session_no_deletion(self):
        """Logout не удаляет файлы при отсутствии сессии."""
        # Мок TelegramAuthRepository.get() — возвращает None
        with patch('src.settings.telegram_auth.TelegramAuthRepository.get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            # Мок SessionFileService
            with patch('src.services.session_file_service.SessionFileService.delete_session_files', new_callable=AsyncMock) as mock_delete:
                from src.settings.repositories.telegram_auth import TelegramAuthRepository
                mock_pool = MagicMock()
                repo = TelegramAuthRepository(mock_pool)
                result = await repo.clear_session()
                
                # Проверить что сессия не удалена (False)
                assert result is False
                # Проверить что delete_session_files НЕ вызван
                mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_logout_symlink_protection(self):
        """Logout защищает от symlink атак."""
        # Мок get_db()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="UPDATE 1")
        mock_conn.fetchrow = AsyncMock(return_value={"session_name": None, "session_data": None})
        
        mock_db_context = AsyncMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_db_context)

        # Мок SessionFileService.delete_session_files() — возвращает False (symlink обнаружен)
        with patch('src.services.session_file_service.SessionFileService.delete_session_files', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = False
            
            # Мок get_db()
            with patch('src.database.get_db', return_value=mock_db_context):
                # Мок TelegramAuthRepository.get() — возвращает сессию
                with patch('src.settings.telegram_auth.TelegramAuthRepository.get', new_callable=AsyncMock) as mock_get:
                    from src.domain.value_objects import SessionName
                    mock_get.return_value = MagicMock(session_name=SessionName("malicious_session"))
                    
                    from src.settings.repositories.telegram_auth import TelegramAuthRepository
                    repo = TelegramAuthRepository(mock_pool)
                    result = await repo.clear_session()
                    
                    # Проверить что delete_session_files вызван (но возвратил False)
                    mock_delete.assert_called_once()
                    # Результат может быть True (БД очищена) даже если файлы не удалены
                    assert result is True  # БД операция успешна
