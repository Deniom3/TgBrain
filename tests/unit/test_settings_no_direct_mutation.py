"""
Audit-тест на отсутствие прямых мутаций Settings в production коде.

Сканирует все .py файлы в src/ и проверяет отсутствие паттернов:
- settings.<field> = value
- config.<field> = value
- self.config.<field> = value

Исключения:
- model_config = ... (определение класса Pydantic)
- Присваивания внутри __init__ методов
- object.__setattr__ в валидаторах (разрешённый обход frozen)
- Файлы, где settings/config — это не Settings (ReindexSettings, ContextExpander.config)

AAA: Arrange / Act / Assert
Одна проверка на тест.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# Файлы, где переменная settings/config — это НЕ Settings.
# В этих файлах прямое присваивание допустимо, так как объекты не frozen.
_EXCLUDED_FILES = frozenset({
    "reindex_speed.py",
    "summary_reindex.py",
    "context_expander.py",
})


@dataclass
class Violation:
    """Нарушение: прямая мутация Settings/config."""
    file: str
    line: int
    source: str


class _DirectMutationVisitor(ast.NodeVisitor):
    """AST-visitor для обнаружения прямых мутаций settings/config."""

    def __init__(self, source_lines: list[str], file_path: str) -> None:
        self.violations: list[Violation] = []
        self._source_lines = source_lines
        self._file_path = file_path

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name == "__init__":
            return
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name == "__init__":
            return
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            violation = self._check_target(target)
            if violation:
                self.violations.append(violation)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        violation = self._check_target(node.target)
        if violation:
            self.violations.append(violation)
        self.generic_visit(node)

    def _check_target(self, target: ast.expr) -> Violation | None:
        if not isinstance(target, ast.Attribute):
            return None

        if target.attr == "model_config":
            return None

        if isinstance(target.value, ast.Name):
            if target.value.id in ("settings", "config"):
                source_line = self._source_lines[target.lineno - 1].strip()
                return Violation(
                    file=self._file_path,
                    line=target.lineno,
                    source=source_line,
                )
            return None

        if isinstance(target.value, ast.Attribute):
            if (
                isinstance(target.value.value, ast.Name)
                and target.value.value.id == "self"
                and target.value.attr == "config"
            ):
                source_line = self._source_lines[target.lineno - 1].strip()
                return Violation(
                    file=self._file_path,
                    line=target.lineno,
                    source=source_line,
                )
            return None

        return None


def _scan_file(file_path: Path) -> list[Violation]:
    """Просканировать один файл на forbidden паттерны."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    source_lines = source.splitlines()
    visitor = _DirectMutationVisitor(source_lines, str(file_path))
    visitor.visit(tree)

    return visitor.violations


def _collect_src_files() -> list[Path]:
    """Собрать все .py файлы в src/, исключая файлы с non-Settings config."""
    src_root = Path(__file__).parent.parent.parent / "src"
    all_files = sorted(src_root.rglob("*.py"))
    return [
        f for f in all_files
        if f.name not in _EXCLUDED_FILES
    ]


def test_no_direct_settings_mutation_in_production_code() -> None:
    """В production коде нет прямых мутаций Settings или config."""
    src_files = _collect_src_files()

    all_violations: list[Violation] = []
    for file_path in src_files:
        violations = _scan_file(file_path)
        all_violations.extend(violations)

    assert not all_violations, _format_violations(all_violations)


def _format_violations(violations: list[Violation]) -> str:
    """Форматировать нарушения для сообщения об ошибке."""
    lines = ["Обнаружены прямые мутации Settings/config в production коде:"]
    for v in violations:
        lines.append(f"  {v.file}:{v.line} — {v.source}")
    lines.append("")
    lines.append("Используйте model_copy(update={{...}}) для создания нового экземпляра.")
    return "\n".join(lines)
