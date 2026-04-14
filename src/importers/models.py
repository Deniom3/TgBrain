from datetime import datetime
from typing import List, Optional, Union, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from dataclasses import dataclass
from src.domain.value_objects import ChatId, SenderId, MessageText, SenderName, MessageLink, BooleanValue


class ExportMessage(BaseModel):
    """Pydantic модель сообщения из экспорта Telegram Desktop с 14 полями."""
    id: int
    type: Literal["message", "service"]
    date: str  # ISO 8601
    from_: Optional[str] = Field(alias="from", default=None)
    from_id: Optional[str] = None
    text: Union[str, List[Union[str, dict]]] = ""  # Allow mixed list or empty string
    text_entities: Optional[List[dict]] = None
    edited: Optional[str] = None
    edited_unixtime: Optional[str] = None
    reactions: Optional[List[dict]] = None
    date_unixtime: Optional[str] = None
    reply_to_message_id: Optional[int] = None
    forwarded_from: Optional[str] = None
    media_type: Optional[str] = None
    
    model_config = ConfigDict(
        # Allow alias mapping
        populate_by_name=True,
        # Allow extra fields for forward compatibility
        extra="ignore"
    )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create instance from dictionary, handling 'from' field alias."""
        return cls.model_validate(data)


@dataclass
class IngestionMessage:
    """Модель сообщения для передачи в ExternalMessageSaver."""
    # Поля, соответствующие требованиям Value Objects архитектуры
    chat_id: ChatId
    text: MessageText
    date: datetime
    sender_id: Optional[SenderId]
    sender_name: SenderName
    is_bot: BooleanValue
    is_action: BooleanValue
    message_link: Optional[MessageLink] = None

    @classmethod
    def from_primitives(
        cls,
        chat_id: int,
        text: str,
        date: datetime,
        sender_id: Optional[int] = None,
        sender_name: str | None = None,
        is_bot: bool = False,
        is_action: bool = False,
        message_link: str | None = None
    ) -> 'IngestionMessage':
        """Фабричный метод для создания из примитивов."""
        return cls(
            chat_id=ChatId(chat_id),
            text=MessageText(text),
            date=date,
            sender_id=SenderId(sender_id) if sender_id is not None else None,
            sender_name=SenderName(sender_name),
            is_bot=BooleanValue(is_bot),
            is_action=BooleanValue(is_action),
            message_link=MessageLink(message_link) if message_link is not None else None
        )

    def to_domain_entity_data(self):
        """Преобразование в данные для создания доменной сущности.
        
        Возвращает словарь данных, которые могут быть переданы в доменный слayer
        для создания доменной сущности. ID генерируется на уровне репозитория.
        """
        return {
            'chat_id': self.chat_id.value,
            'text': self.text.value,
            'date': self.date,
            'sender_id': self.sender_id.value if self.sender_id is not None else None,
            'sender_name': self.sender_name.value,
            'is_bot': self.is_bot.value,
            'is_action': self.is_action.value,
            'message_link': self.message_link.value if self.message_link is not None else None,
        }


@dataclass
class ExportChat:
    """Data class модели чата из экспорта Telegram Desktop."""
    name: str
    type: str
    id: int
    messages: List[ExportMessage]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create instance from dictionary."""
        # Handle messages separately since they need special processing
        messages_data = data.get('messages', [])
        messages = []
        for msg_data in messages_data:
            # Create ExportMessage instance using Pydantic model validation
            export_msg = ExportMessage.from_dict(msg_data)
            messages.append(export_msg)
        
        # Prepare chat data excluding messages to avoid conflicts
        chat_data = {k: v for k, v in data.items() if k != 'messages'}
        chat_data['messages'] = messages
        
        return cls(**chat_data)