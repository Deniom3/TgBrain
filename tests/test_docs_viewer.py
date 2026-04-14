"""Тесты для documentation viewer endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.endpoints.docs_viewer import (
    _MAX_FILE_SIZE,
    _resolve_docs_dir,
    _sanitize_path_for_log,
    _SECTION_NAMES,
    _strip_lang_switch,
    invalidate_docs_cache,
    router,
)


@pytest.fixture
def docs_app() -> FastAPI:
    """Создаёт приложение с docs_viewer router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(docs_app: FastAPI) -> TestClient:
    """TestClient для docs viewer."""
    return TestClient(docs_app)


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Очищает кеш сканирования документов перед каждым тестом."""
    invalidate_docs_cache()


# ---------------------------------------------------------------------------
# Тесты GET /docs-app
# ---------------------------------------------------------------------------


class TestDocsViewerPage:
    def test_docs_viewer_returns_html(self, client: TestClient) -> None:
        response = client.get("/docs-app")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_docs_viewer_contains_viewer_elements(self, client: TestClient) -> None:
        response = client.get("/docs-app")

        assert "Documentation" in response.text
        assert "markdown-body" in response.text


# ---------------------------------------------------------------------------
# Тесты GET /docs-api/tree
# ---------------------------------------------------------------------------


class TestDocTree:
    def test_tree_returns_valid_structure(self, client: TestClient) -> None:
        response = client.get("/docs-api/tree")

        assert response.status_code == 200
        data = response.json()
        assert "root_files" in data
        assert "sections" in data
        assert isinstance(data["root_files"], list)
        assert isinstance(data["sections"], list)

    def test_tree_sections_have_required_fields(self, client: TestClient) -> None:
        response = client.get("/docs-api/tree")

        data = response.json()
        for section in data["sections"]:
            assert "key" in section
            assert "title_ru" in section
            assert "title_en" in section
            assert "files" in section


# ---------------------------------------------------------------------------
# Тесты GET /docs-api/files/{path}
# ---------------------------------------------------------------------------


class TestDocFile:
    def test_readme_returns_content(self, client: TestClient) -> None:
        response = client.get("/docs-api/files/README.md")

        assert response.status_code == 200
        data = response.json()
        assert "content" in data
        assert "filename" in data
        assert data["filename"] == "README.md"

    def test_nonexistent_file_returns_404(self, client: TestClient) -> None:
        response = client.get("/docs-api/files/nonexistent.md")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_path_traversal_blocked(self, client: TestClient) -> None:
        response = client.get("/docs-api/files/%2E%2E%2F%2E%2E%2Fetc%2Fpasswd")

        assert response.status_code in (403, 404)

    def test_absolute_path_returns_403(self, client: TestClient) -> None:
        response = client.get("/docs-api/files/%2Fetc%2Fpasswd")

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Тесты _strip_lang_switch
# ---------------------------------------------------------------------------


class TestStripLangSwitch:
    def test_removes_ru_lang_switch(self) -> None:
        content = (
            "Языки: [EN](README.md) | [RU](README_ru.md)\n"
            "# Заголовок\nТекст"
        )

        result = _strip_lang_switch(content)

        assert "Языки" not in result
        assert "# Заголовок" in result

    def test_removes_en_lang_switch(self) -> None:
        content = (
            "Languages: [RU](README_ru.md) | [EN](README.md)\n"
            "# Title\nText"
        )

        result = _strip_lang_switch(content)

        assert "Languages" not in result
        assert "# Title" in result

    def test_preserves_normal_content(self) -> None:
        content = "# Обычный заголовок\nОбычный текст"

        result = _strip_lang_switch(content)

        assert result == content


# ---------------------------------------------------------------------------
# Тесты ограничения размера файла
# ---------------------------------------------------------------------------


class TestFileSizeLimit:
    def test_oversized_file_returns_413(self, client: TestClient) -> None:
        large_content = "x" * (_MAX_FILE_SIZE + 1)
        docs_dir = _resolve_docs_dir()
        test_file = docs_dir / "_test_oversized.md"

        try:
            test_file.write_text(large_content, encoding="utf-8")
            invalidate_docs_cache()

            response = client.get(f"/docs-api/files/{test_file.name}")

            assert response.status_code == 413
        finally:
            if test_file.exists():
                test_file.unlink()
            invalidate_docs_cache()


# ---------------------------------------------------------------------------
# Тесты _resolve_docs_dir
# ---------------------------------------------------------------------------


class TestResolveDocsDir:
    def test_docs_dir_exists(self) -> None:
        docs_dir = _resolve_docs_dir()

        assert docs_dir.exists()
        assert docs_dir.is_dir()


# ---------------------------------------------------------------------------
# Тесты _sanitize_path_for_log
# ---------------------------------------------------------------------------


class TestSanitizePathForLog:
    def test_removes_newlines(self) -> None:
        result = _sanitize_path_for_log("file\nname.md")

        assert "\n" not in result
        assert "\\n" in result

    def test_removes_carriage_returns(self) -> None:
        result = _sanitize_path_for_log("file\rname.md")

        assert "\r" not in result
        assert "\\r" in result

    def test_preserves_normal_path(self) -> None:
        result = _sanitize_path_for_log("docs/README.md")

        assert result == "docs/README.md"


# ---------------------------------------------------------------------------
# Тесты fallback для неизвестных секций
# ---------------------------------------------------------------------------


class TestSectionNameFallback:
    def test_unknown_section_uses_key_as_title(self) -> None:
        names = _SECTION_NAMES.get("99-unknown-section", {"ru": "99-unknown-section", "en": "99-unknown-section"})

        assert names["ru"] == "99-unknown-section"
        assert names["en"] == "99-unknown-section"

    def test_known_section_has_translated_titles(self) -> None:
        names = _SECTION_NAMES.get("01-getting-started", {"ru": "01-getting-started", "en": "01-getting-started"})

        assert names["ru"] == "Начало работы"
        assert names["en"] == "Getting Started"
