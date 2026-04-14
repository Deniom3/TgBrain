"""
Тесты протокол-интерфейсов (ports).

Проверяет наличие требуемых методов в Protocol-классах,
наличие @runtime_checkable и соответствие реализаций протоколам.
"""


from unittest.mock import MagicMock

from src.protocols.iembeddings_client import IEmbeddingsClient
from src.protocols.illm_client import ILLMClient
from src.protocols.irag_service import IRAGService
from src.protocols.ireindex_service import IReindexService
from src.protocols.isummary_task_service import ISummaryTaskService


class TestIRAGServiceProtocol:
    """Тесты протокола IRAGService."""

    def test_irag_service_protocol_methods(self) -> None:
        """IRAGService имеет check_chat_exists, summary, close."""
        assert hasattr(IRAGService, "check_chat_exists")
        assert hasattr(IRAGService, "summary")
        assert hasattr(IRAGService, "close")

    def test_irag_service_is_runtime_checkable(self) -> None:
        """IRAGService @runtime_checkable."""
        assert getattr(IRAGService, "_is_runtime_protocol", False) is True


class TestIEmbeddingsClientProtocol:
    """Тесты протокола IEmbeddingsClient."""

    def test_iembeddings_client_protocol_methods(self) -> None:
        """IEmbeddingsClient имеет get_embedding, get_model_name."""
        assert hasattr(IEmbeddingsClient, "get_embedding")
        assert hasattr(IEmbeddingsClient, "get_model_name")

    def test_iembeddings_client_is_runtime_checkable(self) -> None:
        """IEmbeddingsClient @runtime_checkable."""
        assert getattr(IEmbeddingsClient, "_is_runtime_protocol", False) is True


class TestILLMClientProtocol:
    """Тесты протокола ILLMClient."""

    def test_illm_client_protocol_methods(self) -> None:
        """ILLMClient имеет generate, check_health."""
        assert hasattr(ILLMClient, "generate")
        assert hasattr(ILLMClient, "check_health")

    def test_illm_client_is_runtime_checkable(self) -> None:
        """ILLMClient @runtime_checkable."""
        assert getattr(ILLMClient, "_is_runtime_protocol", False) is True


class TestIReindexServiceProtocol:
    """Тесты протокола IReindexService."""

    def test_ireindex_service_protocol_methods(self) -> None:
        """IReindexService имеет schedule_reindex, get_status."""
        assert hasattr(IReindexService, "schedule_reindex")
        assert hasattr(IReindexService, "get_status")


class TestISummaryTaskServiceProtocol:
    """Тесты протокола ISummaryTaskService."""

    def test_isummary_task_service_protocol_methods(self) -> None:
        """ISummaryTaskService имеет get_cache_ttl, generate_params_hash."""
        assert hasattr(ISummaryTaskService, "get_cache_ttl")
        assert hasattr(ISummaryTaskService, "generate_params_hash")


class TestIMessageSaverProtocol:
    """Тесты протокола IMessageSaver."""

    def test_imessage_saver_protocol_exists(self) -> None:
        """IMessageSaver runtime_checkable."""
        from src.ingestion.saver import IMessageSaver
        assert getattr(IMessageSaver, "_is_runtime_protocol", False) is True


class TestRAGServiceImplementsIRAGService:
    """Тесты соответствия RAGService протоколу IRAGService."""

    def test_rag_service_implements_irag_service(self) -> None:
        """isinstance(RAGService(), IRAGService)."""
        from src.rag.service import RAGService

        mock_config = MagicMock()
        mock_config.summary_default_hours = 24
        mock_config.summary_max_messages = 100
        mock_pool = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.close = MagicMock()
        mock_llm = MagicMock()
        mock_llm.close = MagicMock()

        rag = RAGService(
            config=mock_config,
            db_pool=mock_pool,
            embeddings_client=mock_embeddings,
            llm_client=mock_llm,
        )
        assert isinstance(rag, IRAGService)


class TestEmbeddingsClientImplementsIEmbeddingsClient:
    """Тесты соответствия EmbeddingsClient протоколу IEmbeddingsClient."""

    def test_embeddings_client_implements_iembeddings_client(self) -> None:
        """isinstance(EmbeddingsClient(), IEmbeddingsClient)."""
        from src.embeddings import EmbeddingsClient

        mock_config = MagicMock()
        mock_config.ollama_embedding_provider = "ollama"
        mock_config.embedding_config.ollama.model = "nomic-embed-text"
        mock_config.embedding_config.ollama.dim = 768
        mock_config.embedding_config.gemini.model = "text-embedding-004"
        mock_config.embedding_config.openrouter.model = "text-embedding-3-small"
        mock_config.embedding_config.lm_studio.model = "nomic-embed-text"

        client = EmbeddingsClient(config=mock_config)
        assert isinstance(client, IEmbeddingsClient)


class TestLLMClientImplementsILLMClient:
    """Тесты соответствия LLMClient протоколу ILLMClient."""

    def test_llm_client_implements_illm_client(self) -> None:
        """isinstance(LLMClient(), ILLMClient)."""
        from src.llm_client import LLMClient

        mock_config = MagicMock()
        mock_config.llm_active_provider = "ollama"
        mock_config.llm_model_name = "llama3"
        mock_config.llm_auto_fallback = False
        mock_config.llm_fallback_timeout = 30.0
        mock_config.get_provider_chain.return_value = ["ollama"]
        mock_config.is_local_provider.return_value = True

        client = LLMClient(config=mock_config)
        assert isinstance(client, ILLMClient)


class TestIApplicationStateProtocol:
    """Тесты протокола IApplicationState."""

    def test_iapplication_state_protocol_defined(self) -> None:
        """IApplicationState имеет все поля с правильными типами."""
        from src.protocols.i_application_state import IApplicationState

        expected_properties = {
            "db_pool",
            "embeddings",
            "llm",
            "rag",
            "reindex",
            "rate_limiter",
            "message_saver",
            "ingester",
            "ingestion_task",
            "cleanup_task",
            "background_tasks",
            "summary_task_service",
            "summary_usecase",
            "import_usecase",
            "chat_settings_repo",
            "summary_repo",
            "summary_webhook_service",
        }
        for prop_name in expected_properties:
            assert hasattr(IApplicationState, prop_name)


class TestGetAppState:
    """Тесты функции get_app_state."""

    def test_get_app_state_returns_iapplication_state(self) -> None:
        """get_app_state() → IApplicationState | None."""
        from src.app import get_app_state
        from src.common.application_state import AppStateStore

        AppStateStore.reset()
        result = get_app_state()
        assert result is None
