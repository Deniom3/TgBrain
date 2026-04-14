"""
Documentation viewer endpoint.

Serves interactive documentation viewer at /docs-app.
Dynamically scans docs/ directory for navigation.

Cache behaviour:
    _scan_docs() uses functools.cache with no TTL — results live for the process
    lifetime. This is intentional: docs files are considered static at runtime.
    Call invalidate_docs_cache() to clear the cache (useful for testing or
    development hot-reload).

Security:
    These endpoints are public (no API key required). Rate limiting is NOT
    implemented yet — TODO: add per-IP rate limiting middleware before
    exposing to untrusted networks.
"""

import asyncio
import functools
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse as FastAPIFileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documentation"])

_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB — максимальный размер файла документов

_SKIP_DIRS = {
    ".git",
    "90-paterns",
    "96-research",
    "97-plans",
    "98-reports",
    "99-archive",
    "99-testing",
}

_SKIP_FILES = {
    "API_TESTING_PLAN.md",
    "MANUAL_TESTING_PLAN.md",
    "DOCUMENTATION_RULES.md",
    "DOCUMENTATION_RULES_ru.md",
    "PROJECT_ISSUE.md",
    "V1.0_READINESS_REPORT.md",
}

_SECTION_NAMES: dict[str, dict[str, str]] = {
    "01-getting-started": {"ru": "Начало работы", "en": "Getting Started"},
    "02-core-components": {"ru": "Основные компоненты", "en": "Core Components"},
    "03-api-reference": {"ru": "API Reference", "en": "API Reference"},
    "04-architecture": {"ru": "Архитектура", "en": "Architecture"},
    "05-integrations": {"ru": "Интеграции", "en": "Integrations"},
    "06-frontend": {"ru": "Фронтенд", "en": "Frontend"},
    "07-testing": {"ru": "Тестирование", "en": "Testing"},
}


def _resolve_docs_dir() -> Path:
    """Возвращает абсолютный путь к директории docs/.

    Разрешение происходит относительно данного файла:
    src/api/endpoints/docs_viewer.py -> src -> docs
    """
    return Path(__file__).resolve().parent.parent.parent.parent / "docs"


class DocFileResponse(BaseModel):
    """Response model for documentation file."""

    content: str
    filename: str


class DocFileInfo(BaseModel):
    """Information about a documentation file."""

    name: str
    path: str
    lang: str
    title: str


class DocSection(BaseModel):
    """A documentation section containing files."""

    key: str
    title_ru: str
    title_en: str
    files: list[DocFileInfo]


class DocTreeResponse(BaseModel):
    """Response model for documentation tree."""

    root_files: list[DocFileInfo]
    sections: list[DocSection]


_LANG_SWITCH_RE = re.compile(
    r"^(?:Языки|Languages)\s*:\s*\[.*?\]\([^)]*\)\s*"
    r"\|\s*\[.*?\]\([^)]*\)\s*$",
    re.MULTILINE,
)


def _strip_lang_switch(content: str) -> str:
    """Remove bilingual language-switch links from markdown content."""
    return _LANG_SWITCH_RE.sub("", content).lstrip("\n")


def _extract_title(filepath: str, content: str) -> str:
    """Extract title from first heading or derive from filename."""
    first_line = content.split("\n")[0].strip()
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return (
        Path(filepath)
        .stem.replace("_ru", "")
        .replace("-", " ")
        .title()
    )


def _scan_docs_sync() -> dict[str, Any]:
    """Scan docs directory and build navigation tree (synchronous).

    Results are cached for the lifetime of the process via the wrapper
    _scan_docs(). Call invalidate_docs_cache() to clear.
    """
    docs_dir = _resolve_docs_dir()
    root_files_ru: list[DocFileInfo] = []
    root_files_en: list[DocFileInfo] = []
    sections: dict[str, dict[str, list[DocFileInfo]]] = {}

    for md_file in sorted(docs_dir.rglob("*.md")):
        rel = md_file.relative_to(docs_dir)

        if rel.name in _SKIP_FILES:
            continue

        parts = rel.parts
        if any(p in _SKIP_DIRS for p in parts):
            continue

        is_ru = rel.name.endswith("_ru.md")
        lang = "ru" if is_ru else "en"

        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            title = _extract_title(str(rel), content)
        except OSError:
            title = (
                rel.name.replace("_ru.md", "")
                .replace(".md", "")
                .replace("-", " ")
                .title()
            )

        file_info = DocFileInfo(
            name=rel.name,
            path=str(rel),
            lang=lang,
            title=title,
        )

        if len(parts) == 1:
            if rel.name in ("README.md", "README_ru.md"):
                if is_ru:
                    root_files_ru.append(file_info)
                else:
                    root_files_en.append(file_info)
        else:
            section_key = parts[0]
            if section_key not in sections:
                sections[section_key] = {"ru": [], "en": []}
            if is_ru:
                sections[section_key]["ru"].append(file_info)
            else:
                sections[section_key]["en"].append(file_info)

    return {
        "root_ru": root_files_ru,
        "root_en": root_files_en,
        "sections": sections,
    }


@functools.cache
def _scan_docs() -> dict[str, Any]:
    """Cached wrapper around _scan_docs_sync()."""
    return _scan_docs_sync()


async def _scan_docs_async() -> dict[str, Any]:
    """Async wrapper that runs filesystem I/O in a thread pool."""
    return await asyncio.to_thread(_scan_docs)


def invalidate_docs_cache() -> None:
    """Clear the docs scan cache (useful for testing or hot-reload)."""
    _scan_docs.cache_clear()


@router.get("/docs-app", include_in_schema=False)
async def docs_viewer() -> FastAPIFileResponse:
    """Serve the interactive documentation viewer HTML page."""
    template_path = Path(__file__).resolve().parent / "templates" / "docs_viewer.html"
    return FastAPIFileResponse(str(template_path), media_type="text/html")


@router.get("/docs-api/tree", response_model=DocTreeResponse)
async def get_doc_tree() -> DocTreeResponse:
    """Get documentation tree structure.

    Scans the docs/ directory and returns all available markdown files
    grouped by sections with titles extracted from first heading.
    """
    data = await _scan_docs_async()

    sections: list[DocSection] = []
    for key in sorted(data["sections"].keys()):
        section = data["sections"][key]
        names = _SECTION_NAMES.get(key, {"ru": key, "en": key})
        sections.append(
            DocSection(
                key=key,
                title_ru=names["ru"],
                title_en=names["en"],
                files=section["ru"] + section["en"],
            )
        )

    return DocTreeResponse(
        root_files=data["root_ru"] + data["root_en"],
        sections=sections,
    )


def _sanitize_path_for_log(path: str) -> str:
    """Удаляет управляющие символы из пути для безопасного логирования."""
    return path.replace("\n", "\\n").replace("\r", "\\r")


def _read_doc_file_sync(file_path: str, docs_dir: Path) -> DocFileResponse:
    """Synchronous helper for reading and validating a documentation file.

    All blocking filesystem I/O happens here, called via asyncio.to_thread().
    """
    safe_path = Path(file_path).as_posix()

    if ".." in safe_path or safe_path.startswith("/"):
        raise HTTPException(status_code=403, detail="Access denied")

    full_path = (docs_dir / safe_path).resolve()

    if not full_path.is_relative_to(docs_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if not full_path.is_file():
        raise HTTPException(status_code=400, detail="Path is not a file")

    if full_path.suffix not in (".md", ".txt"):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_size = full_path.stat().st_size
    if file_size > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large")

    log_path = _sanitize_path_for_log(safe_path)
    logger.debug("Reading documentation file: %s (%d bytes)", log_path, file_size)

    try:
        content = full_path.read_text(encoding="utf-8")
        content = _strip_lang_switch(content)
        return DocFileResponse(content=content, filename=full_path.name)
    except OSError:
        logger.exception("Failed to read documentation file: %s", log_path)
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


@router.get(
    "/docs-api/files/{file_path:path}",
    response_model=DocFileResponse,
)
async def get_doc_file(file_path: str) -> DocFileResponse:
    """Get documentation file content.

    Returns markdown content for the specified documentation file.
    All blocking I/O is delegated to a thread pool via asyncio.to_thread().
    """
    docs_dir = _resolve_docs_dir()
    return await asyncio.to_thread(_read_doc_file_sync, file_path, docs_dir)
