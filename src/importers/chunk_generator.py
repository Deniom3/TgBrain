import ijson
import logging
import os
from pathlib import Path
from typing import Iterator, List, Optional

from .models import IngestionMessage, ExportMessage
from .telegram_export_parser import TelegramExportParser
from src.domain.value_objects import ChatId

logger = logging.getLogger(__name__)


ERROR_FILE_NOT_FOUND = "File not found"
ERROR_PATH_TRAVERSAL = "Invalid file path"
ERROR_UNSUPPORTED_FORMAT = "Unsupported file format"
ERROR_FILE_TOO_LARGE = "File too large"

IJSON_ROOT_ID = "id"
IJSON_MESSAGES_ITEM = "messages.item"

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024
UPLOAD_DIR = Path("./uploads").resolve()
TEMP_UPLOAD_DIR = Path("/tmp/batch_imports").resolve()
SKIP_PATH_VALIDATION = os.getenv("SKIP_PATH_VALIDATION", "false").lower() == "true"


class StreamingChunkGenerator:
    DEFAULT_CHUNK_SIZE = 100

    def __init__(self, file_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE):
        path = Path(file_path).resolve()
        
        if not SKIP_PATH_VALIDATION and not (str(path).startswith(str(UPLOAD_DIR)) or str(path).startswith(str(TEMP_UPLOAD_DIR))):
            raise ValueError(ERROR_PATH_TRAVERSAL)
        
        if not path.exists():
            raise FileNotFoundError(ERROR_FILE_NOT_FOUND)
        
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(ERROR_FILE_TOO_LARGE)
        
        if path.suffix.lower() not in {'.json'}:
            raise ValueError(ERROR_UNSUPPORTED_FORMAT)
        
        self.file_path = path
        self.chunk_size = chunk_size
        self._parser = TelegramExportParser()
        self._total_count: int = 0

    def __iter__(self) -> Iterator[List[IngestionMessage]]:
        buffer: List[IngestionMessage] = []
        
        with open(self.file_path, 'rb') as f:
            for export_msg in self._read_messages(f):
                ingestion_msg = self._parser.convert_to_ingestion(
                    export_msg.message,
                    export_msg.chat_id
                )
                buffer.append(ingestion_msg)
                
                if len(buffer) >= self.chunk_size:
                    yield buffer
                    buffer = []
            
            if buffer:
                yield buffer

    def _buffer_messages(
        self,
        buffer: List[IngestionMessage],
        message: IngestionMessage,
    ) -> List[IngestionMessage]:
        buffer.append(message)
        return buffer

    def _read_messages(self, file_handle) -> Iterator['ExportMessageData']:
        chat_id: Optional[ChatId] = None
        try:
            file_handle.seek(0)
            root_parser = ijson.items(file_handle, IJSON_ROOT_ID)
            id_value = next(root_parser, None)
            if id_value is not None:
                chat_id = ChatId(id_value)
        except Exception:
            pass
        
        file_handle.seek(0)
        parser = ijson.items(file_handle, IJSON_MESSAGES_ITEM)
        
        for msg_data in parser:
            export_msg = ExportMessage.from_dict(msg_data)
            yield ExportMessageData(chat_id=chat_id, message=export_msg)

    def get_total_count(self) -> int:
        if self._total_count == 0:
            self._count_messages()
        return self._total_count

    def _count_messages(self) -> None:
        try:
            with open(self.file_path, 'rb') as f:
                parser = ijson.items(f, 'messages.item')
                count = 0
                for _ in parser:
                    count += 1
                self._total_count = count
        except (ijson.JSONError, IOError) as e:
            logger.warning("Could not count messages: %s", e)
            self._total_count = 0

    def iterate_chunks_as_dicts(
        self,
    ) -> Iterator[List[dict]]:
        """Итерирует по чанкам файла, возвращая каждый чанк как список dict."""
        for chunk in self:
            yield [self._message_to_dict(msg) for msg in chunk]

    @staticmethod
    def _message_to_dict(msg: IngestionMessage) -> dict:
        """Конвертирует IngestionMessage в dict."""
        return {
            "text": msg.text.value,
            "date": msg.date,
            "from_id": msg.sender_id.value if msg.sender_id is not None else None,
            "type": msg.sender_name.value,
        }


class ExportMessageData:
    def __init__(self, chat_id: Optional[ChatId], message: ExportMessage):
        self.chat_id = chat_id
        self.message = message
