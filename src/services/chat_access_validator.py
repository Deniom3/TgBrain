import logging

import asyncpg

from src.domain.value_objects import ChatId, ChatTitle, ChatType

logger = logging.getLogger(__name__)

ERROR_USER_NOT_MEMBER = "User not member of chat"

SQL_CHECK_CHAT_EXISTS = """
    SELECT chat_id, is_monitored 
    FROM chat_settings 
    WHERE chat_id = $1
"""

SQL_AUTO_CREATE_CHAT = """
    INSERT INTO chat_settings (chat_id, title, type, is_monitored, summary_enabled)
    VALUES ($1, $2, $3, FALSE, TRUE)
    ON CONFLICT (chat_id) DO UPDATE SET
        title = EXCLUDED.title,
        type = EXCLUDED.type
"""


class ChatAccessValidator:
    def __init__(self, pool: asyncpg.Pool, telegram_client=None):
        self.pool = pool
        self._telegram_client = telegram_client

    async def validate_access(
        self,
        chat_id: ChatId,
        chat_title: ChatTitle,
        chat_type: ChatType,
    ) -> bool:
        async with self.pool.acquire() as conn:
            chat_exists = await self._check_chat_exists(conn, chat_id)
            
            if chat_exists:
                logger.debug("Chat exists: chat_id=%d", chat_id.value)
                return True
            
            is_member = await self._check_telegram_membership(chat_id)
            if not is_member:
                raise PermissionError(ERROR_USER_NOT_MEMBER)
            
            await self._auto_create_chat(conn, chat_id, chat_title, chat_type)
            logger.info("Chat auto-created: chat_id=%d, title=%s", chat_id.value, chat_title.value)
            return True

    async def _check_chat_exists(
        self,
        conn: asyncpg.Connection,
        chat_id: ChatId,
    ) -> bool:
        row = await conn.fetchrow(
            SQL_CHECK_CHAT_EXISTS,
            chat_id.value,
        )
        return row is not None

    async def _check_telegram_membership(self, chat_id: ChatId) -> bool:
        if self._telegram_client is None:
            logger.warning("Telegram client not configured, cannot verify membership")
            return False
        
        try:
            await self._telegram_client.get_chat(chat_id.value)
            return True
        except Exception:
            return False

    async def _auto_create_chat(
        self,
        conn: asyncpg.Connection,
        chat_id: ChatId,
        title: ChatTitle,
        type_: ChatType,
    ) -> None:
        await conn.execute(
            SQL_AUTO_CREATE_CHAT,
            chat_id.value,
            title.value,
            type_.value,
        )
