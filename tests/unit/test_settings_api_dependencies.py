"""Тесты общего модуля зависимостей settings_api."""


def test_dependencies_exports_get_current_user():
    """get_current_user экспортируется."""
    from src.settings_api.dependencies import get_current_user
    assert callable(get_current_user)


def test_dependencies_exports_get_webhook_settings_service():
    """get_webhook_settings_service экспортируется."""
    from src.settings_api.dependencies import get_webhook_settings_service
    assert callable(get_webhook_settings_service)


def test_dependencies_exports_webhook_config_rate_limit():
    """webhook_config_rate_limit экспортируется."""
    from src.settings_api.dependencies import webhook_config_rate_limit
    assert callable(webhook_config_rate_limit)


def test_dependencies_exports_webhook_test_rate_limit():
    """webhook_test_rate_limit экспортируется."""
    from src.settings_api.dependencies import webhook_test_rate_limit
    assert callable(webhook_test_rate_limit)


def test_app_uses_local_dependencies():
    """app.py импортирует из .dependencies, не из ..api.dependencies."""
    import ast
    path = "src/settings_api/app.py"
    with open(path) as f:
        tree = ast.parse(f.read())
    imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    for imp in imports:
        if isinstance(imp, ast.ImportFrom) and imp.module:
            assert "api.dependencies.auth" not in imp.module, f"{path} должен импортировать из .dependencies, не из ..api.dependencies"
            if "dependencies" in imp.module:
                assert imp.module == "src.settings_api.dependencies" or imp.module == ".dependencies" or imp.level > 0


def test_webhook_endpoints_uses_local_dependencies():
    """webhook_endpoints.py импортирует из локальных зависимостей."""
    import ast
    path = "src/settings_api/webhook_endpoints.py"
    with open(path) as f:
        tree = ast.parse(f.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "api.dependencies.auth" not in node.module
            assert "api.dependencies.services" not in node.module
            assert "api.dependencies.rate_limiter" not in node.module
