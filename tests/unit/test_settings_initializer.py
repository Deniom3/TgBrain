"""Тесты для SettingsInitializer."""

from unittest.mock import AsyncMock, MagicMock, patch

from src.settings_initializer import SettingsInitializer


def make_settings(**kwargs: object) -> MagicMock:
    """Создаёт мок Settings с дефолтными значениями."""
    settings = MagicMock()
    settings.tg_api_id = 12345678
    settings.tg_api_hash = "abc" * 11 + "d"
    settings.tg_phone_number = None
    settings.tg_chat_enable = ""
    settings.tg_chat_disable = ""
    settings.llm_active_provider = "gemini"
    settings.gemini_api_key = "gemini-key"
    settings.gemini_base_url = "https://gemini.api"
    settings.gemini_model = "gemini-2.5-flash"
    settings.openrouter_api_key = None
    settings.openrouter_base_url = "https://openrouter.api"
    settings.openrouter_model = "auto"
    settings.ollama_llm_enabled = True
    settings.ollama_llm_base_url = "http://localhost:11434"
    settings.ollama_llm_model = "deepseek-coder:6.7b"
    settings.lm_studio_enabled = False
    settings.lm_studio_base_url = "http://localhost:1234"
    settings.lm_studio_model = "qwen/qwen3.5-9b"
    settings.timezone = "Etc/UTC"
    settings.llm_fallback_providers = "openrouter,gemini"
    settings.llm_auto_fallback = True
    settings.llm_fallback_timeout = 10
    settings.log_level = "INFO"
    settings.summary_default_hours = 24
    settings.summary_max_messages = 50
    settings.rag_top_k = 5
    settings.rag_score_threshold = 0.3
    settings.ollama_embedding_provider = "ollama"
    settings.ollama_embedding_url = "http://localhost:11434"
    settings.ollama_embedding_model = "nomic-embed-text"
    settings.ollama_embedding_dim = 768
    settings.ollama_embedding_max_retries = 3
    settings.ollama_embedding_timeout = 30
    settings.ollama_embedding_normalize = False
    settings.gemini_embedding_model = "text-embedding-004"
    settings.gemini_embedding_dim = 768
    settings.gemini_embedding_max_retries = 3
    settings.gemini_embedding_timeout = 30
    settings.gemini_embedding_normalize = False
    settings.openrouter_embedding_model = "openai/text-embedding-3-small"
    settings.openrouter_embedding_dim = 1536
    settings.openrouter_embedding_max_retries = 3
    settings.openrouter_embedding_timeout = 30
    settings.openrouter_embedding_normalize = False
    settings.lm_studio_embedding_api_key = None
    settings.lm_studio_embedding_url = "http://localhost:1234"
    settings.lm_studio_embedding_model = "text-embedding-model"
    settings.lm_studio_embedding_dim = 768
    settings.lm_studio_embedding_max_retries = 3
    settings.lm_studio_embedding_timeout = 30
    settings.lm_studio_embedding_normalize = False
    for key, value in kwargs.items():
        setattr(settings, key, value)
    return settings


def make_auth_db(
    api_id: int | None = 12345678,
    api_hash: str | None = "abc" * 11 + "d",
    phone_number: str | None = None,
    session_name: str | None = None,
) -> MagicMock:
    """Создаёт мок auth_db записи."""
    auth = MagicMock()
    auth.api_id = api_id
    auth.api_hash = api_hash
    auth.phone_number = phone_number
    auth.session_name = session_name
    return auth


class TestInitialize:
    """Тесты SettingsInitializer.initialize."""

    @patch("src.settings_initializer.get_settings")
    @patch.object(SettingsInitializer, "_init_telegram_auth", new_callable=AsyncMock)
    @patch.object(SettingsInitializer, "_init_llm_providers", new_callable=AsyncMock)
    @patch.object(SettingsInitializer, "_init_embedding_providers", new_callable=AsyncMock)
    @patch.object(SettingsInitializer, "_init_app_settings", new_callable=AsyncMock)
    @patch.object(SettingsInitializer, "_init_chat_settings", new_callable=AsyncMock)
    async def test_initialize_success(
        self,
        mock_init_chat: AsyncMock,
        mock_init_app: AsyncMock,
        mock_init_embedding: AsyncMock,
        mock_init_llm: AsyncMock,
        mock_init_telegram: AsyncMock,
        mock_get_settings: MagicMock,
    ) -> None:
        """Успешная инициализация всех настроек."""
        mock_settings = make_settings()
        mock_get_settings.return_value = mock_settings

        result = await SettingsInitializer.initialize()

        assert result is True
        mock_init_telegram.assert_called_once()
        mock_init_llm.assert_called_once()
        mock_init_embedding.assert_called_once()
        mock_init_app.assert_called_once()
        mock_init_chat.assert_called_once()

    @patch("src.settings_initializer.get_settings")
    async def test_initialize_error_returns_false(
        self, mock_get_settings: MagicMock,
    ) -> None:
        """Ошибка инициализации возвращает False."""
        mock_get_settings.side_effect = RuntimeError("DB error")

        result = await SettingsInitializer.initialize()

        assert result is False


class TestInitTelegramAuth:
    """Тесты _init_telegram_auth."""

    async def test_init_telegram_auth_new(self) -> None:
        """Первичная инициализация Telegram auth."""
        settings = make_settings()
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        await SettingsInitializer._init_telegram_auth(settings, mock_repo)

        mock_repo.upsert.assert_called_once()
        call_kwargs = mock_repo.upsert.call_args.kwargs
        assert call_kwargs["api_id"] == 12345678

    async def test_init_telegram_auth_update(self) -> None:
        """Обновление существующих настроек Telegram."""
        settings = make_settings(tg_api_id=99999999)
        existing = make_auth_db(api_id=12345678)
        mock_repo = AsyncMock()
        mock_repo.get.return_value = existing

        await SettingsInitializer._init_telegram_auth(settings, mock_repo)

        mock_repo.upsert.assert_called_once()

    async def test_init_telegram_auth_preserves_session_name(self) -> None:
        """session_name сохраняется из БД при обновлении."""
        settings = make_settings()
        existing = make_auth_db(session_name="my_session")
        mock_repo = AsyncMock()
        mock_repo.get.return_value = existing

        await SettingsInitializer._init_telegram_auth(settings, mock_repo)

        call_kwargs = mock_repo.upsert.call_args.kwargs
        assert call_kwargs["session_name"] == "my_session"

    async def test_init_telegram_auth_no_repo_uses_fallback(self) -> None:
        """Без переданного репозитория создаётся временный."""
        settings = make_settings()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm
        mock_conn.fetchrow.return_value = None

        mock_temp_repo = AsyncMock()
        mock_temp_repo.get.return_value = None

        with patch("src.database.get_pool", return_value=mock_pool):
            with patch("src.settings_initializer.TelegramAuthRepository", return_value=mock_temp_repo):
                await SettingsInitializer._init_telegram_auth(settings, None)

        mock_temp_repo.upsert.assert_called_once()


class TestInitLlmProviders:
    """Тесты _init_llm_providers."""

    async def test_init_llm_providers_new(self) -> None:
        """Первичная инициализация LLM провайдеров."""
        settings = make_settings()
        mock_repo = AsyncMock()
        mock_repo.get.return_value = None

        await SettingsInitializer._init_llm_providers(settings, mock_repo)

        assert mock_repo.upsert.call_count == 4

    async def test_init_llm_providers_existing_skipped(self) -> None:
        """Существующие провайдеры с api_key пропускаются."""
        settings = make_settings()
        mock_repo = AsyncMock()
        existing_provider = MagicMock()
        existing_provider.api_key = "existing-key"
        existing_provider.model = ""
        mock_repo.get.return_value = existing_provider

        await SettingsInitializer._init_llm_providers(settings, mock_repo)

        assert mock_repo.upsert.call_count == 0


class TestInitAppSettings:
    """Тесты _init_app_settings."""

    async def test_init_app_settings(self) -> None:
        """Инициализация app settings."""
        settings = make_settings()
        mock_repo = AsyncMock()

        await SettingsInitializer._init_app_settings(settings, mock_repo)

        assert mock_repo.upsert_if_not_exists.call_count >= 10


class TestInitChatSettings:
    """Тесты _init_chat_settings."""

    @patch("src.database.get_pool")
    @patch("src.settings.ChatSettingsRepository")
    async def test_init_chat_settings_enable(
        self, mock_repo_cls: MagicMock, mock_get_pool: MagicMock,
    ) -> None:
        """Включение чатов из списка."""
        from src.config import Settings

        settings = Settings(
            tg_chat_enable="100,200",
            tg_chat_disable="",
        )
        mock_pool = MagicMock()
        mock_get_pool.return_value = mock_pool

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        await SettingsInitializer._init_chat_settings(settings)

        assert mock_repo.upsert.call_count == 2

    @patch("src.database.get_pool")
    @patch("src.settings.ChatSettingsRepository")
    async def test_init_chat_settings_disable(
        self, mock_repo_cls: MagicMock, mock_get_pool: MagicMock,
    ) -> None:
        """Отключение чатов из списка."""
        from src.config import Settings

        settings = Settings(
            tg_chat_enable="",
            tg_chat_disable="300",
        )
        mock_pool = MagicMock()
        mock_get_pool.return_value = mock_pool

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        await SettingsInitializer._init_chat_settings(settings)

        mock_repo.upsert.assert_called_once()
        call_kwargs = mock_repo.upsert.call_args.kwargs
        assert call_kwargs["is_monitored"] is False

    @patch("src.database.get_pool")
    @patch("src.settings.ChatSettingsRepository")
    async def test_init_chat_settings_empty(
        self, mock_repo_cls: MagicMock, mock_get_pool: MagicMock,
    ) -> None:
        """Пустые списки чатов не вызывают репозиторий."""
        from src.config import Settings

        settings = Settings(
            tg_chat_enable="",
            tg_chat_disable="",
        )
        mock_pool = MagicMock()
        mock_get_pool.return_value = mock_pool

        mock_repo = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        await SettingsInitializer._init_chat_settings(settings)

        mock_repo.upsert.assert_not_called()


class TestGetCurrentConfig:
    """Тесты get_current_config."""

    @patch("src.database.get_pool")
    async def test_get_current_config(
        self, mock_get_pool: MagicMock,
    ) -> None:
        """Получение текущей конфигурации из БД."""
        mock_pool = MagicMock()
        mock_get_pool.return_value = mock_pool

        mock_telegram_repo = AsyncMock()
        mock_telegram_repo.get.return_value = make_auth_db()

        mock_llm_repo = AsyncMock()
        llm_provider = MagicMock()
        llm_provider.name = "gemini"
        llm_provider.is_active = True
        mock_llm_repo.get_all.return_value = [llm_provider]

        mock_embedding_repo = AsyncMock()
        embedding_provider = MagicMock()
        embedding_provider.name = "ollama"
        embedding_provider.is_active = True
        mock_embedding_repo.get_all.return_value = [embedding_provider]

        mock_app_repo = AsyncMock()
        mock_app_repo.get_all.return_value = []

        mock_chat_repo = AsyncMock()
        chat_setting = MagicMock()
        chat_setting.is_monitored = True
        mock_chat_repo.get_all.return_value = [chat_setting]

        result = await SettingsInitializer.get_current_config(
            telegram_auth_repo=mock_telegram_repo,
            llm_providers_repo=mock_llm_repo,
            embedding_providers_repo=mock_embedding_repo,
            app_settings_repo=mock_app_repo,
            chat_settings_repo=mock_chat_repo,
        )

        assert result["telegram"]["configured"] is True
        assert result["llm"]["active_provider"] == "gemini"
        assert result["embedding"]["active_provider"] == "ollama"
        assert result["app"]["settings_count"] == 0
        assert result["chats"]["monitored_count"] == 1
        assert result["chats"]["total_count"] == 1
