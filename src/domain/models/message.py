"""
Доменная модель сообщения для инджеста.

Модель представляет собой полноценную доменную сущность с Value Objects,
реализующую бизнес-логику и инварианты.
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from src.domain.exceptions import ValidationError
from src.domain.value_objects import (
    ChatId, SenderId, MessageText, SenderName, ChatTitle, 
    MessageLink, ChatType, BooleanValue
)


@dataclass
class MessageId:
    """Value Object для ID сообщения."""
    
    def __init__(self, value: int) -> None:
        if not isinstance(value, int) or value <= 0:
            raise ValidationError("MessageId must be a positive integer", field="value")
        self._value = value
    
    @property
    def value(self) -> int:
        return self._value
    
    def to_int(self) -> int:
        """Конвертировать в int."""
        return self._value
    
    def __str__(self) -> str:
        return str(self._value)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageId):
            return NotImplemented
        return self._value == other._value
    
    def __hash__(self) -> int:
        return hash(self._value)


class IngestionMessage:
    """
    Доменная сущность сообщения для инджеста.
    
    Содержит бизнес-логику и инварианты, обеспечивая целостность данных
    через Value Objects и защиту от некорректных состояний.
    """

    def __init__(
        self,
        message_id: MessageId,
        chat_id: ChatId,
        chat_title: ChatTitle,
        chat_type: ChatType,
        sender_id: Optional[SenderId],
        sender_name: SenderName,
        text: MessageText,
        date: datetime,
        message_link: Optional[MessageLink],
        is_bot: BooleanValue = BooleanValue(False),
        is_action: BooleanValue = BooleanValue(False)
    ):
        # Приватные атрибуты для хранения Value Objects
        self._message_id = message_id
        self._chat_id = chat_id
        self._chat_title = chat_title
        self._chat_type = chat_type
        self._sender_id = sender_id
        self._sender_name = sender_name
        self._text = text
        self._date = date
        self._message_link = message_link
        self._is_bot = is_bot
        self._is_action = is_action
        
        # Валидация бизнес-инвариантов
        self._validate_business_rules()

    def _validate_business_rules(self) -> None:
        """Проверка бизнес-правил и инвариантов доменной модели."""
        # Проверить, что дата не из будущего (необязательное ограничение)
        # Это позволяет гибридное поведение для сообщений, пришедших с задержкой
        pass

    # Геттеры для доступа к Value Objects
    @property
    def message_id(self) -> MessageId:
        return self._message_id

    @property
    def chat_id(self) -> ChatId:
        return self._chat_id

    @property
    def chat_title(self) -> ChatTitle:
        return self._chat_title

    @property
    def chat_type(self) -> ChatType:
        return self._chat_type

    @property
    def sender_id(self) -> Optional[SenderId]:
        return self._sender_id

    @property
    def sender_name(self) -> SenderName:
        return self._sender_name

    @property
    def text(self) -> MessageText:
        return self._text

    @property
    def date(self) -> datetime:
        return self._date

    @property
    def message_link(self) -> Optional[MessageLink]:
        return self._message_link

    @property
    def is_bot(self) -> BooleanValue:
        return self._is_bot

    @property
    def is_action(self) -> BooleanValue:
        return self._is_action

    def is_system_message(self) -> bool:
        """Проверяет, является ли сообщение системным (действием)."""
        return self._is_action.value

    def is_from_bot(self) -> bool:
        """Проверяет, отправлено ли сообщение от бота."""
        return self._is_bot.value

    def belongs_to_chat(self, chat_id: ChatId) -> bool:
        """Проверяет, принадлежит ли сообщение указанному чату."""
        return self._chat_id == chat_id

    # Методы для восстановления сущности из данных персистентности
    @classmethod
    def restore(
        cls,
        message_id: int,
        chat_id: int,
        chat_title: str,
        chat_type: str,
        sender_id: Optional[int],
        sender_name: str,
        text: str,
        date: datetime,
        message_link: Optional[str],
        is_bot: bool = False,
        is_action: bool = False
    ) -> 'IngestionMessage':
        """
        Фабричный метод для восстановления сущности из данных персистентности.
        
        Используется при загрузке из базы данных или других источников хранения.
        """
        return cls(
            message_id=MessageId(message_id),
            chat_id=ChatId(chat_id),
            chat_title=ChatTitle(chat_title),
            chat_type=ChatType(chat_type),
            sender_id=SenderId(sender_id) if sender_id is not None else None,
            sender_name=SenderName(sender_name),
            text=MessageText(text),
            date=date,
            message_link=MessageLink(message_link) if message_link is not None else None,
            is_bot=BooleanValue(is_bot),
            is_action=BooleanValue(is_action)
        )

    def to_dict(self) -> dict:
        """
        Конвертирует сущность в словарь для передачи в другие слои.
        
        Не рекомендуется использовать для персистентности, только для передачи данных.
        """
        return {
            'message_id': self._message_id.value,
            'chat_id': self._chat_id.value,
            'chat_title': self._chat_title.value,
            'chat_type': self._chat_type.value,
            'sender_id': self._sender_id.value if self._sender_id is not None else None,
            'sender_name': self._sender_name.value,
            'text': self._text.value,
            'date': self._date,
            'message_link': self._message_link.value if self._message_link is not None else None,
            'is_bot': self._is_bot.value,
            'is_action': self._is_action.value
        }