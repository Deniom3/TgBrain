from datetime import datetime

from src.importers import ExportMessage, IngestionMessage, ExportChat, TelegramExportParser
from src.domain.value_objects import ChatId


def _make_export_message(
    msg_id: int,
    msg_type: str,
    date: str,
    from_value: str,
    from_id: str,
    text: str,
    date_unixtime: str,
) -> ExportMessage:
    """Создать ExportMessage с правильным маппингом поля 'from'."""
    data = {
        "id": msg_id,
        "type": msg_type,
        "date": date,
        "from": from_value,
        "from_id": from_id,
        "text": text,
        "text_entities": [],
        "edited": None,
        "edited_unixtime": None,
        "reactions": None,
        "date_unixtime": date_unixtime,
    }
    return ExportMessage.from_dict(data)


def test_export_message_model():
    """Тестирование модели ExportMessage."""
    message_data = {
        "id": 123,
        "type": "message",
        "date": "2023-01-01T12:00:00",
        "from": "John Doe",
        "from_id": "user456",
        "text": "Hello world",
        "text_entities": [],
        "edited": None,
        "edited_unixtime": None,
        "reactions": None,
        "date_unixtime": "1672568400"
    }
    
    message = ExportMessage.from_dict(message_data)
    
    assert message.id == 123
    assert message.type == "message"
    assert message.from_ == "John Doe"
    assert message.text == "Hello world"


def test_export_chat_model():
    """Тестирование модели ExportChat."""
    chat_data = {
        "name": "Test Chat",
        "type": "private",
        "id": 789,
        "messages": [
            {
                "id": 123,
                "type": "message",
                "date": "2023-01-01T12:00:00",
                "from": "John Doe",
                "from_id": "user456",
                "text": "Hello world",
                "text_entities": [],
                "edited": None,
                "edited_unixtime": None,
                "reactions": None,
                "date_unixtime": "1672568400"
            }
        ]
    }
    
    chat = ExportChat.from_dict(chat_data)
    
    assert chat.name == "Test Chat"
    assert chat.type == "private"
    assert chat.id == 789
    assert len(chat.messages) == 1
    assert chat.messages[0].id == 123


def test_extract_text_simple_string():
    """Тестирование извлечения текста из простой строки."""
    parser = TelegramExportParser()
    
    result = parser.extract_text("Simple text")
    
    assert result == "Simple text"


def test_extract_text_from_array():
    """Тестирование извлечения текста из массива элементов."""
    parser = TelegramExportParser()
    
    text_array = [
        {"type": "plain", "text": "Hello "},
        {"type": "mention", "text": "@user"},
        {"type": "plain", "text": " how are you?"}
    ]
    
    result = parser.extract_text(text_array)
    
    assert result == "Hello @user how are you?"


def test_parse_sender_id_user():
    """Тестирование парсинга ID отправителя для обычного пользователя."""
    parser = TelegramExportParser()
    
    sender_id, is_bot = parser.parse_sender_id("user123")
    
    assert sender_id == 123
    assert is_bot is False


def test_parse_sender_id_channel():
    """Тестирование парсинга ID отправителя для канала."""
    parser = TelegramExportParser()
    
    sender_id, is_bot = parser.parse_sender_id("channel456")
    
    assert sender_id == -1000000000456
    assert is_bot is False


def test_parse_sender_id_bot():
    """Тестирование парсинга ID отправителя для бота."""
    parser = TelegramExportParser()
    
    sender_id, is_bot = parser.parse_sender_id("bot789")
    
    assert sender_id == 789
    assert is_bot is True


def test_parse_date():
    """Тестирование парсинга даты."""
    parser = TelegramExportParser()
    
    date_str = "2023-01-01T12:00:00"
    result = parser.parse_date(date_str)
    
    assert result is not None
    assert result.year == 2023
    assert result.month == 1
    assert result.day == 1
    assert result.hour == 12
    assert result.minute == 0


def test_convert_to_ingestion_regular_message():
    """Тестирование конвертации ExportMessage в IngestionMessage для обычного сообщения."""
    parser = TelegramExportParser()
    
    export_msg = _make_export_message(
        msg_id=123,
        msg_type="message",
        date="2023-01-01T12:00:00",
        from_value="John Doe",
        from_id="user456",
        text="Hello world",
        date_unixtime="1672568400",
    )
    
    ingestion_msg = parser.convert_to_ingestion(export_msg, ChatId(789))
    
    assert ingestion_msg.chat_id.value == 789
    assert ingestion_msg.text.value == "Hello world"
    assert ingestion_msg.sender_id is not None
    assert ingestion_msg.sender_id.value == 456
    assert ingestion_msg.sender_name.value == "John Doe"
    assert ingestion_msg.is_bot.value is False
    assert ingestion_msg.is_action.value is False


def test_convert_to_ingestion_service_message():
    """Тестирование конвертации ExportMessage в IngestionMessage для служебного сообщения."""
    parser = TelegramExportParser()
    
    export_msg = _make_export_message(
        msg_id=124,
        msg_type="service",
        date="2023-01-01T12:01:00",
        from_value="Channel Admin",
        from_id="user457",
        text="New member joined",
        date_unixtime="1672568460",
    )
    
    ingestion_msg = parser.convert_to_ingestion(export_msg, ChatId(789))
    
    assert ingestion_msg.chat_id.value == 789
    assert ingestion_msg.text.value == "New member joined"
    assert ingestion_msg.sender_id is not None
    assert ingestion_msg.sender_id.value == 457
    assert ingestion_msg.sender_name.value == "Channel Admin"
    assert ingestion_msg.is_bot.value is False
    assert ingestion_msg.is_action.value is True


def test_convert_to_ingestion_bot_message():
    """Тестирование конвертации ExportMessage в IngestionMessage для сообщения от бота."""
    parser = TelegramExportParser()
    
    export_msg = _make_export_message(
        msg_id=125,
        msg_type="message",
        date="2023-01-01T12:02:00",
        from_value="MyBot",
        from_id="bot789",
        text="Automated response",
        date_unixtime="1672568520",
    )
    
    ingestion_msg = parser.convert_to_ingestion(export_msg, ChatId(789))
    
    assert ingestion_msg.chat_id.value == 789
    assert ingestion_msg.text.value == "Automated response"
    assert ingestion_msg.sender_id is not None
    assert ingestion_msg.sender_id.value == 789
    assert ingestion_msg.sender_name.value == "MyBot"
    assert ingestion_msg.is_bot.value is True
    assert ingestion_msg.is_action.value is False


def test_parse_json():
    """Тестирование парсинга JSON данных."""
    parser = TelegramExportParser()
    
    json_data = {
        "name": "Test Chat",
        "type": "private",
        "id": 12345,
        "messages": [
            {
                "id": 1,
                "type": "message",
                "date": "2023-01-01T10:00:00",
                "from": "User One",
                "from_id": "user123",
                "text": "First message",
                "text_entities": [{"type": "plain", "text": "First message"}],
                "edited": None,
                "edited_unixtime": None,
                "reactions": None,
                "date_unixtime": "1672563600"
            },
            {
                "id": 2,
                "type": "service",
                "date": "2023-01-01T10:01:00",
                "from": "System",
                "from_id": "channel1",
                "text": "User joined",
                "text_entities": [{"type": "plain", "text": "User joined"}],
                "edited": None,
                "edited_unixtime": None,
                "reactions": None,
                "date_unixtime": "1672563660"
            }
        ]
    }
    
    chat = parser.parse_json(json_data)
    
    assert chat.name == "Test Chat"
    assert chat.type == "private"
    assert chat.id == 12345
    assert len(chat.messages) == 2
    
    # Check first message
    first_msg = chat.messages[0]
    assert first_msg.id == 1
    assert first_msg.type == "message"
    assert first_msg.from_ == "User One"
    # Text should be extracted from entities when it's an array
    assert isinstance(first_msg.text, str)
    # The text should have been processed through extract_text method during parsing
    
    # Check second message (service message)
    second_msg = chat.messages[1]
    assert second_msg.id == 2
    assert second_msg.type == "service"
    assert second_msg.from_ == "System"


def test_extract_text_empty_array_returns_empty_string():
    """Тестирование извлечения текста из пустого массива."""
    parser = TelegramExportParser()
    
    result = parser.extract_text([])
    
    assert result == ""


def test_extract_text_with_entities_extracts_text_only():
    """Тестирование извлечения текста из массива с разными типами entities."""
    parser = TelegramExportParser()
    
    text_array = [
        {"type": "plain", "text": "Hello "},
        {"type": "bold", "text": "bold"},
        {"type": "italic", "text": " italic"},
        {"type": "link", "text": " link", "url": "http://example.com"},
    ]
    
    result = parser.extract_text(text_array)
    
    assert result == "Hello bold italic link"


def test_parse_date_invalid_format_returns_none():
    """Тестирование парсинга невалидной даты."""
    parser = TelegramExportParser()
    
    result = parser.parse_date("invalid-date")
    
    assert result is None


def test_parse_date_iso8601_with_timezone():
    """Тестирование парсинга ISO 8601 даты с таймзоной."""
    parser = TelegramExportParser()
    
    date_str = "2023-01-01T12:00:00+03:00"
    result = parser.parse_date(date_str)
    
    assert result is not None
    if result:
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 0


class TestIngestionMessageValueObjects:
    """Тестирование Value Objects в IngestionMessage."""

    def test_all_fields_are_value_objects(self):
        """Все поля IngestionMessage используют Value Objects."""
        from src.domain.value_objects import ChatId, SenderId, MessageText, SenderName, BooleanValue, MessageLink
        
        ingestion_msg = IngestionMessage.from_primitives(
            chat_id=123,
            text="Test message",
            date=datetime(2023, 1, 1, 12, 0, 0),
            sender_id=456,
            sender_name="Test User",
            is_bot=False,
            is_action=False,
            message_link="https://t.me/test/123"
        )
        
        assert isinstance(ingestion_msg.chat_id, ChatId)
        assert isinstance(ingestion_msg.text, MessageText)
        assert isinstance(ingestion_msg.sender_id, SenderId)
        assert isinstance(ingestion_msg.sender_name, SenderName)
        assert isinstance(ingestion_msg.is_bot, BooleanValue)
        assert isinstance(ingestion_msg.is_action, BooleanValue)
        assert isinstance(ingestion_msg.message_link, MessageLink)

    def test_from_primitives_creates_value_objects(self):
        """Фабричный метод from_primitives создает Value Objects."""
        ingestion_msg = IngestionMessage.from_primitives(
            chat_id=-1001234567890,
            text="Hello world",
            date=datetime(2023, 1, 1, 10, 30, 0),
            sender_id=None,
            sender_name="Anonymous",
            is_bot=True,
            is_action=True
        )
        
        assert ingestion_msg.chat_id.value == -1001234567890
        assert ingestion_msg.text.value == "Hello world"
        assert ingestion_msg.sender_id is None
        assert ingestion_msg.sender_name.value == "Anonymous"
        assert ingestion_msg.is_bot.value is True
        assert ingestion_msg.is_action.value is True
        assert ingestion_msg.message_link is None

    def test_value_objects_enforce_types(self):
        """Value Objects обеспечивают типизацию полей."""
        from src.domain.value_objects import ChatId, MessageText
        
        chat_id = ChatId(123)
        assert chat_id.value == 123
        
        text = MessageText("Test")
        assert text.value == "Test"