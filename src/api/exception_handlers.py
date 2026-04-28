"""
Обработчики исключений для FastAPI приложения.

Модуль содержит все обработчики исключений и функцию для их регистрации.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.error_codes import APP_ERROR_CODES
from src.api.models import ErrorDetail, ErrorResponse
from src.application.exceptions import DuplicateError, ServiceUnavailableError, UseCaseError
from src.domain.exceptions import BusinessRuleError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """
    Регистрирует все обработчики исключений в FastAPI приложении.

    Args:
        app: Экземпляр FastAPI приложения.
    """
    app.add_exception_handler(Exception, global_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(NotFoundError, not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(BusinessRuleError, business_rule_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DuplicateError, duplicate_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ServiceUnavailableError, service_unavailable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(UseCaseError, use_case_error_handler)  # type: ignore[arg-type]


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    ec = APP_ERROR_CODES["APP-101"]
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=ec.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=ec.code, message=ec.message),
        ).model_dump(),
    )


async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    for error in exc.errors():
        loc = error.get("loc", ())
        if any("filter_min_length" in str(part) for part in loc):
            ec = APP_ERROR_CODES["APP-008"]
            logger.info("Filter validation error: %s", error.get("msg", ""))
            return JSONResponse(
                status_code=ec.http_status,
                content=ErrorResponse(
                    error=ErrorDetail(code=ec.code, message=ec.message),
                ).model_dump(),
            )
    logger.info("Request validation error: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    ec = APP_ERROR_CODES["APP-102"]
    logger.info("Validation error: %s", exc.message)
    return JSONResponse(
        status_code=ec.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=ec.code, message=ec.message),
            field=exc.field,
        ).model_dump(),
    )


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    ec = APP_ERROR_CODES["APP-103"]
    logger.info("Not found: %s", exc.entity_type)
    return JSONResponse(
        status_code=ec.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=ec.code, message=ec.message),
        ).model_dump(),
    )


async def business_rule_error_handler(request: Request, exc: BusinessRuleError) -> JSONResponse:
    ec = APP_ERROR_CODES["APP-104"]
    logger.info("Business rule error: %s", exc.message)
    return JSONResponse(
        status_code=ec.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=ec.code, message=ec.message),
            rule_code=exc.rule_code,
        ).model_dump(),
    )


async def duplicate_error_handler(request: Request, exc: DuplicateError) -> JSONResponse:
    ec = APP_ERROR_CODES["APP-105"]
    logger.info("Duplicate error: %s", exc.message)
    return JSONResponse(
        status_code=ec.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=ec.code, message=ec.message),
        ).model_dump(),
    )


async def service_unavailable_handler(request: Request, exc: ServiceUnavailableError) -> JSONResponse:
    ec = APP_ERROR_CODES["APP-106"]
    logger.warning("Service unavailable: %s", exc.service_name or "unknown")
    return JSONResponse(
        status_code=ec.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=ec.code, message=ec.message),
        ).model_dump(),
    )


async def use_case_error_handler(request: Request, exc: UseCaseError) -> JSONResponse:
    ec = APP_ERROR_CODES["APP-107"]
    logger.info("Use case error: %s", exc.message)
    return JSONResponse(
        status_code=ec.http_status,
        content=ErrorResponse(
            error=ErrorDetail(code=ec.code, message=ec.message),
        ).model_dump(),
    )
