"""
RAG (Retrieval-Augmented Generation) — суммаризация.

Генерация дайджестов с поддержкой кэширования результатов в БД.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template

from ..config import Settings
from ..llm_client import LLMClient
from .search import RAGSearch

logger = logging.getLogger(__name__)


class RAGSummary:
    """Суммаризация сообщений для RAG."""

    def __init__(
        self,
        config: Settings,
        search: RAGSearch,
        llm_client: LLMClient,
        prompts_dir: str = "promt",
        db_pool=None,
    ):
        self.config = config
        self.search = search
        self.llm = llm_client
        self.prompts_dir = Path(prompts_dir)
        self.db_pool = db_pool
        self.default_prompt_template = self._load_prompt("summary_prompt.txt")
        # ✨ Кэширование удалено — используется только кэширование по params_hash в SummaryTaskService

    def refresh_config(self, new_settings: Settings) -> None:
        """Обновить ссылку на Settings после reload."""
        self.config = new_settings
        logger.debug("RAGSummary обновлён")

    def _load_prompt(self, filename: str) -> Template:
        """Загрузка шаблона промпта."""
        prompt_path = self.prompts_dir / filename
        if not prompt_path.exists():
            logger.error(f"Шаблон промпта не найден: {prompt_path}")
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        return Template(prompt_path.read_text(encoding="utf-8"))

    async def _get_chat_custom_prompt(self, chat_id: int) -> Optional[str]:
        """Получить кастомный промпт для чата."""
        if not self.db_pool:
            return None

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT custom_prompt FROM chat_settings WHERE chat_id = $1",
                    chat_id
                )
                if row and row['custom_prompt']:
                    return row['custom_prompt']
        except Exception as e:
            logger.error(f"Ошибка получения кастомного промпта для чата {chat_id}: {e}")
        return None

    async def _get_chat_summary_settings(self, chat_id: int) -> Optional[Dict[str, Any]]:
        """Получить настройки summary для чата."""
        if not self.db_pool:
            return None

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT summary_enabled, summary_period_minutes, summary_schedule, custom_prompt
                    FROM chat_settings
                    WHERE chat_id = $1
                    """,
                    chat_id
                )
                if row:
                    return dict(row)
        except Exception as e:
            logger.error(f"Ошибка получения настроек summary для чата {chat_id}: {e}")
        return None

    async def summary(
        self,
        period_hours: int,
        max_messages: int,
        chat_id: Optional[int] = None,
        custom_prompt: Optional[str] = None,
        use_cache: bool = False,
        save_to_db: bool = True,
    ) -> str:
        """
        Генерация дайджеста за период.

        Args:
            period_hours: Период в часах.
            max_messages: Максимум сообщений.
            chat_id: ID чата для генерации summary (опционально).
            custom_prompt: Кастомный промпт (переопределяет промпт чата и дефолтный).
            use_cache: Если True, проверить кэш перед генерацией.
            save_to_db: Если True, сохранить результат в БД.

        Returns:
            Текст дайджеста.
        """
        logger.info(f"Генерация summary за {period_hours}ч (макс. {max_messages} сообщений), чат: {chat_id}")

        # Если указан chat_id, пробуем получить кастомный промпт
        if chat_id and not custom_prompt:
            chat_custom_prompt = await self._get_chat_custom_prompt(chat_id)
            if chat_custom_prompt:
                custom_prompt = chat_custom_prompt
                logger.info(f"Использован кастомный промпт для чата {chat_id}")

        # Получаем сообщения
        if chat_id:
            messages = await self.search.get_messages_by_period(
                period_hours, max_messages, chat_id=chat_id
            )
        else:
            messages = await self.search.get_messages_by_period(period_hours, max_messages)

        if not messages:
            return (
                f"❌ За последние {period_hours} ч. не найдено сообщений для анализа.\n"
                "Убедитесь, что сообщения собираются в базу данных."
            )

        # Используем кастомный промпт или дефолтный
        if custom_prompt:
            prompt_template = Template(custom_prompt)
        else:
            prompt_template = self.default_prompt_template

        prompt = prompt_template.render(
            period=f"{period_hours} ч.",
            messages=[
                {
                    "text": str(msg.text)[:500],
                    "date": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
                    "chat_title": str(msg.chat_title),
                    "sender_name": str(msg.sender_name)
                }
                for msg in messages
            ]
        )

        try:
            digest = await self.llm.generate(
                prompt=prompt,
                system_prompt="Ты — аналитик Telegram-чатов. "
                             "Создавай структурированные и информативные дайджесты."
            )
            logger.info("Дайджест сгенерирован")

            # ✨ Сохранение в БД удалено — используется только через SummaryTaskService
            return digest
        except Exception as e:
            logger.error(f"Ошибка генерации дайджеста: {e}")
            return f"❌ Ошибка генерации дайджеста: {e}"

    async def summary_for_chats(
        self,
        chat_ids: Optional[List[int]] = None,
        period_minutes: Optional[int] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        custom_prompt: Optional[str] = None,
        max_messages: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Генерация summary для списка чатов.

        Args:
            chat_ids: Список ID чатов. Если None - все включённые чаты.
            period_minutes: Период сбора в минутах (переопределяет настройку чата).
            period_start: Явное начало периода (переопределяет period_minutes).
            period_end: Явное окончание периода (переопределяет period_minutes).
            custom_prompt: Промпт для генерации (переопределяет промпт чата).
            max_messages: Максимум сообщений на чат.

        Returns:
            Список словарей с результатами: {chat_id, title, summary, messages_count}
        """
        results: list[dict] = []

        # Если chat_ids не указан, получаем все включённые чаты
        if not chat_ids:
            if not self.db_pool:
                logger.error("db_pool не настроен, невозможно получить список чатов")
                return results

            try:
                async with self.db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT chat_id, title FROM chat_settings WHERE summary_enabled = TRUE"
                    )
                    chat_ids = [row['chat_id'] for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения списка чатов: {e}")
                return results

        logger.info(f"Генерация summary для {len(chat_ids)} чатов")

        # Вычисляем период
        if period_start and period_end:
            # Явный диапазон
            period_hours = (period_end - period_start).total_seconds() / 3600
        elif period_minutes is not None:
            # Период в минутах
            period_hours = period_minutes / 60
        else:
            # Период будет определён из настроек чата
            period_hours = None

        for cid in chat_ids:
            try:
                # Получаем настройки чата
                chat_settings = await self._get_chat_summary_settings(cid)

                if not chat_settings:
                    logger.warning(f"Настройки для чата {cid} не найдены, пропускаем")
                    continue

                if not chat_settings.get('summary_enabled', True):
                    logger.info(f"Summary отключено для чата {cid}, пропускаем")
                    continue

                # Определяем период (если не был задан явно)
                if period_hours is None:
                    period_hours = chat_settings.get('summary_period_minutes', 1440) / 60

                # Определяем промпт
                chat_custom_prompt = custom_prompt or chat_settings.get('custom_prompt')

                # Получаем сообщения для чата
                messages = await self.search.get_messages_by_period(
                    int(period_hours), max_messages, chat_id=cid
                )

                if not messages:
                    logger.info(f"Нет сообщений для чата {cid} за последние {period_hours} ч. — summary не сохраняется в БД")
                    results.append({
                        "chat_id": cid,
                        "title": chat_settings.get('title', f'Chat {cid}'),
                        "summary": f"❌ Нет сообщений за последние {period_hours} ч.",
                        "messages_count": 0
                    })
                    continue

                # Формируем промпт
                if chat_custom_prompt:
                    prompt_template = Template(chat_custom_prompt)
                else:
                    prompt_template = self.default_prompt_template

                prompt = prompt_template.render(
                    period=f"{period_hours} ч.",
                    messages=[
                        {
                            "text": str(msg.text)[:500],
                            "date": msg.date.strftime("%Y-%m-%d %H:%M:%S"),
                            "chat_title": str(msg.chat_title),
                            "sender_name": str(msg.sender_name)
                        }
                        for msg in messages
                    ]
                )

                # Генерируем summary
                digest = await self.llm.generate(
                    prompt=prompt,
                    system_prompt="Ты — аналитик Telegram-чатов. "
                                 "Создавай структурированные и информативные дайджесты."
                )

                # ✨ Сохранение в БД удалено — используется только через SummaryTaskService

                results.append({
                    "chat_id": cid,
                    "title": chat_settings.get('title', f'Chat {cid}'),
                    "summary": digest,
                    "messages_count": len(messages)
                })

                logger.info(f"Summary для чата {cid} сгенерировано ({len(messages)} сообщений)")

            except Exception as e:
                logger.error(f"Ошибка генерации summary для чата {cid}: {e}", exc_info=True)
                results.append({
                    "chat_id": cid,
                    "title": f"Chat {cid}",
                    "summary": f"❌ Ошибка генерации: {e}",
                    "messages_count": 0
                })

        return results
