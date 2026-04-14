"""
DTO модели для Settings API.

Модели для сериализации Value Objects в JSON.
"""

from typing import Optional
from pydantic import BaseModel


class TelegramSettingsDTO(BaseModel):
    """DTO для настроек Telegram."""
    api_id: int
    api_hash: Optional[str] = None
    session_name: Optional[str] = None
    
    @classmethod
    def from_config(cls, config: dict) -> "TelegramSettingsDTO":
        """
        Создать DTO из конфига.
        
        Args:
            config: Словарь конфигурации с Value Objects.
            
        Returns:
            DTO модель.
        """
        telegram = config.get("telegram", {})
        
        api_id = telegram.get("api_id")
        if hasattr(api_id, "to_int"):
            api_id = api_id.to_int()
        elif hasattr(api_id, "value"):
            api_id = api_id.value
        
        api_hash = telegram.get("api_hash")
        if hasattr(api_hash, "to_str"):
            api_hash = api_hash.to_str()
        elif hasattr(api_hash, "value"):
            api_hash = api_hash.value
        
        session_name = telegram.get("session_name")
        if hasattr(session_name, "to_str"):
            session_name = session_name.to_str()
        elif hasattr(session_name, "value"):
            session_name = session_name.value
        
        return cls(
            api_id=api_id,
            api_hash=api_hash,
            session_name=session_name,
        )


class LLMProviderSettingsDTO(BaseModel):
    """DTO для настроек LLM провайдера."""
    name: str
    is_active: bool
    config: dict


class LLMSettingsDTO(BaseModel):
    """DTO для настроек LLM."""
    active_provider: str
    providers: list[LLMProviderSettingsDTO]
    
    @classmethod
    def from_config(cls, config: dict) -> "LLMSettingsDTO":
        """
        Создать DTO из конфига.
        
        Args:
            config: Словарь конфигурации.
            
        Returns:
            DTO модель.
        """
        llm = config.get("llm", {})
        raw_providers = llm.get("providers", [])
        
        parsed_providers: list[LLMProviderSettingsDTO] = []
        for p in raw_providers:
            if isinstance(p, dict):
                parsed_providers.append(LLMProviderSettingsDTO(
                    name=p.get("name", ""),
                    is_active=p.get("is_active", False),
                    config={
                        "api_key": p.get("api_key"),
                        "base_url": p.get("base_url", ""),
                        "model": p.get("model", ""),
                        "is_enabled": p.get("is_enabled", True),
                        "priority": p.get("priority", 0),
                        "description": p.get("description"),
                    },
                ))
            elif isinstance(p, str):
                parsed_providers.append(LLMProviderSettingsDTO(
                    name=p,
                    is_active=False,
                    config={},
                ))
        
        return cls(
            active_provider=llm.get("active_provider", ""),
            providers=parsed_providers,
        )


class EmbeddingProviderSettingsDTO(BaseModel):
    """DTO для настроек провайдера эмбеддингов."""
    name: str
    url: str
    model: str


class EmbeddingSettingsDTO(BaseModel):
    """DTO для настроек эмбеддингов."""
    active_provider: str
    providers: list[EmbeddingProviderSettingsDTO]
    
    @classmethod
    def from_config(cls, config: dict) -> "EmbeddingSettingsDTO":
        """
        Создать DTO из конфига.
        
        Args:
            config: Словарь конфигурации.
            
        Returns:
            DTO модель.
        """
        embedding = config.get("embedding", {})
        raw_providers = embedding.get("providers", [])
        
        parsed_providers: list[EmbeddingProviderSettingsDTO] = []
        for p in raw_providers:
            if isinstance(p, dict):
                parsed_providers.append(EmbeddingProviderSettingsDTO(
                    name=p.get("name", ""),
                    url=p.get("base_url") or p.get("url") or "",
                    model=p.get("model", ""),
                ))
            elif isinstance(p, str):
                parsed_providers.append(EmbeddingProviderSettingsDTO(
                    name=p,
                    url="",
                    model="",
                ))
        
        return cls(
            active_provider=embedding.get("active_provider", ""),
            providers=parsed_providers,
        )


class AppSettingsDTO(BaseModel):
    """DTO для настроек приложения."""
    log_level: str
    summary_default_hours: int
    summary_max_messages: int
    rag_top_k: int
    rag_score_threshold: float
    
    @classmethod
    def from_config(cls, config: dict) -> "AppSettingsDTO":
        """
        Создать DTO из конфига.
        
        Args:
            config: Словарь конфигурации.
            
        Returns:
            DTO модель.
        """
        app = config.get("app", {})
        return cls(
            log_level=app.get("log_level", "INFO"),
            summary_default_hours=app.get("summary_default_hours", 24),
            summary_max_messages=app.get("summary_max_messages", 50),
            rag_top_k=app.get("rag_top_k", 5),
            rag_score_threshold=app.get("rag_score_threshold", 0.3),
        )


class ChatSettingsDTO(BaseModel):
    """DTO для настроек чатов."""
    total_chats: int
    monitored_chats: int
    
    @classmethod
    def from_config(cls, config: dict) -> "ChatSettingsDTO":
        """
        Создать DTO из конфига.
        
        Args:
            config: Словарь конфигурации.
            
        Returns:
            DTO модель.
        """
        chats = config.get("chats", {})
        return cls(
            total_chats=chats.get("total_chats", 0),
            monitored_chats=chats.get("monitored_chats", 0),
        )


class SettingsOverviewDTO(BaseModel):
    """DTO для общего обзора настроек."""
    telegram: TelegramSettingsDTO
    llm: LLMSettingsDTO
    app: AppSettingsDTO
    chats: ChatSettingsDTO
    
    @classmethod
    def from_config(cls, config: dict) -> "SettingsOverviewDTO":
        """
        Создать DTO из конфига.
        
        Args:
            config: Словарь конфигурации.
            
        Returns:
            DTO модель.
        """
        return cls(
            telegram=TelegramSettingsDTO.from_config(config),
            llm=LLMSettingsDTO.from_config(config),
            app=AppSettingsDTO.from_config(config),
            chats=ChatSettingsDTO.from_config(config),
        )
