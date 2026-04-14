"""
Тесты обработчиков исключений FastAPI.

Использует httpx.AsyncClient с тестовым приложением для проверки
что каждый обработчик возвращает правильный HTTP-статус и код ошибки.
"""

from typing import AsyncGenerator
import json

import pytest
from unittest.mock import AsyncMock
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from src.api.error_codes import APP_ERROR_CODES
from src.api.exception_handlers import (
    global_exception_handler,
    register_exception_handlers,
)
from src.application.exceptions import DuplicateError, ServiceUnavailableError, UseCaseError
from src.domain.exceptions import BusinessRuleError, NotFoundError, ValidationError


def _create_test_app() -> FastAPI:
    """Создаёт тестовое приложение с зарегистрированными обработчиками."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-global")
    async def raise_global() -> None:
        raise RuntimeError("Unexpected error")

    @app.get("/raise-validation")
    async def raise_validation() -> None:
        raise ValidationError(message="Invalid value", field="test_field")

    @app.get("/raise-validation-no-field")
    async def raise_validation_no_field() -> None:
        raise ValidationError(message="Generic validation error")

    @app.get("/raise-not-found")
    async def raise_not_found() -> None:
        raise NotFoundError(entity_type="Chat", identifier="999")

    @app.get("/raise-business-rule")
    async def raise_business_rule() -> None:
        raise BusinessRuleError(message="Rule violated", rule_code="BR-001")

    @app.get("/raise-business-rule-no-code")
    async def raise_business_rule_no_code() -> None:
        raise BusinessRuleError(message="Rule violated")

    @app.get("/raise-duplicate")
    async def raise_duplicate() -> None:
        raise DuplicateError(message="Already exists", entity_type="Chat")

    @app.get("/raise-service-unavailable")
    async def raise_service_unavailable() -> None:
        raise ServiceUnavailableError(message="Down", service_name="LLM")

    @app.get("/raise-use-case")
    async def raise_use_case() -> None:
        raise UseCaseError(message="Use case failed", use_case_name="Ask")

    return app


@pytest.fixture
def test_app() -> FastAPI:
    """Тестовое приложение с обработчиками."""
    return _create_test_app()


@pytest.fixture
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP клиент для тестового приложения."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _make_mock_request() -> Request:
    """Создаёт мок Request для прямого вызова обработчиков."""
    scope = {"type": "http", "method": "GET", "path": "/test"}
    receive = AsyncMock()
    send = AsyncMock()
    return Request(scope, receive=receive, send=send)


class TestGlobalExceptionHandler:
    """Тесты глобального обработчика исключений."""

    @pytest.mark.asyncio
    async def test_global_handler_returns_app101(self) -> None:
        """Exception → 500, code=APP-101."""
        mock_request = _make_mock_request()
        exc = RuntimeError("Unexpected error")
        response = await global_exception_handler(mock_request, exc)
        assert response.status_code == 500
        body = json.loads(response.body)
        assert body["error"]["code"] == "APP-101"
        assert body["error"]["message"] == APP_ERROR_CODES["APP-101"].message


class TestValidationExceptionHandler:
    """Тесты обработчика ValidationError."""

    @pytest.mark.asyncio
    async def test_validation_handler_returns_app102_with_field(self, client: AsyncClient) -> None:
        """ValidationError → 400, APP-102, field."""
        response = await client.get("/raise-validation")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "APP-102"
        assert body["field"] == "test_field"

    @pytest.mark.asyncio
    async def test_validation_handler_without_field(self, client: AsyncClient) -> None:
        """ValidationError без field → без поля."""
        response = await client.get("/raise-validation-no-field")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "APP-102"
        assert body.get("field") is None


class TestNotFoundHandler:
    """Тесты обработчика NotFoundError."""

    @pytest.mark.asyncio
    async def test_not_found_handler_returns_app103(self, client: AsyncClient) -> None:
        """NotFoundError → 404, code=APP-103."""
        response = await client.get("/raise-not-found")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "APP-103"


class TestBusinessRuleErrorHandler:
    """Тесты обработчика BusinessRuleError."""

    @pytest.mark.asyncio
    async def test_business_rule_handler_returns_app104_with_rule_code(self, client: AsyncClient) -> None:
        """BusinessRuleError → 400, APP-104, rule_code."""
        response = await client.get("/raise-business-rule")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "APP-104"
        assert body["rule_code"] == "BR-001"

    @pytest.mark.asyncio
    async def test_business_rule_handler_without_rule_code(self, client: AsyncClient) -> None:
        """BusinessRuleError без rule_code → без поля."""
        response = await client.get("/raise-business-rule-no-code")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "APP-104"
        assert body.get("rule_code") is None


class TestDuplicateErrorHandler:
    """Тесты обработчика DuplicateError."""

    @pytest.mark.asyncio
    async def test_duplicate_handler_returns_app105(self, client: AsyncClient) -> None:
        """DuplicateError → 409, code=APP-105."""
        response = await client.get("/raise-duplicate")
        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "APP-105"


class TestServiceUnavailableHandler:
    """Тесты обработчика ServiceUnavailableError."""

    @pytest.mark.asyncio
    async def test_service_unavailable_handler_returns_app106(self, client: AsyncClient) -> None:
        """ServiceUnavailableError → 503, APP-106."""
        response = await client.get("/raise-service-unavailable")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "APP-106"


class TestUseCaseErrorHandler:
    """Тесты обработчика UseCaseError."""

    @pytest.mark.asyncio
    async def test_use_case_handler_returns_app107(self, client: AsyncClient) -> None:
        """UseCaseError → 422, code=APP-107."""
        response = await client.get("/raise-use-case")
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "APP-107"


class TestRegisterHandlers:
    """Тесты функции регистрации обработчиков."""

    def test_register_handlers_attaches_all_7(self) -> None:
        """register_exception_handlers регистрирует все 7."""
        app = FastAPI()
        register_exception_handlers(app)

        handlers = app.exception_handlers
        assert Exception in handlers
        assert ValidationError in handlers
        assert NotFoundError in handlers
        assert BusinessRuleError in handlers
        assert DuplicateError in handlers
        assert ServiceUnavailableError in handlers
        assert UseCaseError in handlers
