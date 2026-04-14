"""Тесты re-export репозиториев из src.settings.repositories."""


def test_settings_init_reexport_repositories():
    """from src.settings import ChatSettingsRepository работает."""
    from src.settings import ChatSettingsRepository
    assert ChatSettingsRepository is not None


def test_settings_init_chat_settings_repo_accessible():
    """Прямой импорт из src.settings.repositories работает."""
    from src.settings.repositories import ChatSettingsRepository
    assert ChatSettingsRepository is not None


def test_settings_repository_files_moved():
    """Файлы находятся в repositories/ подпапке."""
    import pathlib
    repos_dir = pathlib.Path(__file__).parent.parent.parent.parent / "src" / "settings" / "repositories"
    assert repos_dir.exists()
    assert (repos_dir / "__init__.py").exists()
    assert (repos_dir / "chat_settings.py").exists()
    assert (repos_dir / "telegram_auth.py").exists()
    assert (repos_dir / "app_settings.py").exists()
