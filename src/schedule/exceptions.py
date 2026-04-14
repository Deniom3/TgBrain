"""Domain exceptions для ScheduleService."""


class ScheduleError(Exception):
    """Базовое исключение для расписаний."""

    def __init__(self, message: str, code: str) -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class ChatNotFoundError(ScheduleError):
    """Чат не найден (SCH-001)."""

    def __init__(self, chat_id: int) -> None:
        self.chat_id = chat_id
        super().__init__(f"Chat {chat_id} not found", code="SCH-001")


class LLMGenerationError(ScheduleError):
    """Ошибка генерации LLM (SCH-002)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="SCH-002")


class NextScheduleUpdateError(ScheduleError):
    """Ошибка обновления next_schedule_run (SCH-003)."""

    def __init__(self, chat_id: int, error: Exception) -> None:
        self.chat_id = chat_id
        super().__init__(
            f"Failed to update next_schedule_run for chat {chat_id}: {error}",
            code="SCH-003",
        )


class InvalidScheduleError(ScheduleError):
    """Неверный формат расписания (SCH-004)."""

    def __init__(self, schedule: str) -> None:
        self.schedule = schedule
        super().__init__(f"Invalid schedule format: {schedule}", code="SCH-004")


class CronParseError(ScheduleError):
    """Ошибка парсинга cron выражения (SCH-005)."""

    def __init__(self, message: str, cron_expression: str | None = None) -> None:
        self.cron_expression = cron_expression
        super().__init__(message, code="SCH-005")


class GetChatsError(ScheduleError):
    """Ошибка получения чатов с расписанием (SCH-006)."""

    def __init__(self, error: Exception) -> None:
        super().__init__(f"Failed to get chats with schedule: {error}", code="SCH-006")
