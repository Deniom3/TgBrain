"""
Helper functions для batch import endpoints.

Вынесенные функции для получения UseCase из app.state.
"""

from fastapi import HTTPException, Request

from src.api.error_codes import APP_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse

from src.application.usecases.import_messages import ImportMessagesUseCase

ERROR_FILE_TOO_LARGE = "File too large (max 500MB)"
ERROR_TASK_NOT_FOUND = "Task not found"


def get_import_usecase(request: Request) -> ImportMessagesUseCase:
    """Получение ImportMessagesUseCase из app.state."""
    usecase = getattr(request.app.state, "import_usecase", None)
    if usecase is None:
        ec = APP_ERROR_CODES["APP-106"]
        raise HTTPException(
            status_code=ec.http_status,
            detail=ErrorResponse(
                error=ErrorDetail(code=ec.code, message=ec.message)
            ).model_dump(),
        )
    return usecase
