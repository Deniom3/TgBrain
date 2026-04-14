"""
Тесты для Webhook Value Objects.
"""

import pytest

from src.domain.exceptions import ValidationError
from src.domain.value_objects import WebhookMethod, WebhookUrl


class TestWebhookUrl:
    """Тесты для WebhookUrl Value Object."""

    def test_valid_https_url(self) -> None:
        """Валидный HTTPS URL."""
        url = WebhookUrl("https://example.com/webhook")
        assert url.value == "https://example.com/webhook"

    def test_valid_https_url_with_path(self) -> None:
        """Валидный HTTPS URL с путём."""
        url = WebhookUrl("https://example.com/v1/webhooks/summary")
        assert url.value == "https://example.com/v1/webhooks/summary"

    def test_valid_https_url_with_query(self) -> None:
        """Валидный HTTPS URL с query параметрами."""
        url = WebhookUrl("https://example.com/webhook?chat_id=123")
        assert url.value == "https://example.com/webhook?chat_id=123"

    def test_invalid_http_url(self) -> None:
        """HTTP URL вместо HTTPS вызывает ошибку."""
        with pytest.raises(ValidationError, match="Webhook URL должен быть HTTPS"):
            WebhookUrl("http://example.com/webhook")

    def test_invalid_ftp_url(self) -> None:
        """FTP URL вызывает ошибку."""
        with pytest.raises(ValidationError, match="Webhook URL должен быть HTTPS"):
            WebhookUrl("ftp://example.com/file")

    def test_invalid_ws_url(self) -> None:
        """WebSocket URL вызывает ошибку."""
        with pytest.raises(ValidationError, match="Webhook URL должен быть HTTPS"):
            WebhookUrl("ws://example.com/socket")

    def test_localhost_ip_rejected(self) -> None:
        """Loopback IP адрес отклоняется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://127.0.0.1/webhook")

    def test_localhost_hostname_rejected(self) -> None:
        """Localhost hostname отклоняется."""
        with pytest.raises(ValidationError, match="Localhost запрещён"):
            WebhookUrl("https://localhost/webhook")

    def test_private_ip_192_168_rejected(self) -> None:
        """Private IP 192.168.x.x отклоняется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://192.168.1.1/webhook")

    def test_private_ip_10_x_rejected(self) -> None:
        """Private IP 10.x.x.x отклоняется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://10.0.0.1/webhook")

    def test_private_ip_172_16_rejected(self) -> None:
        """Private IP 172.16.x.x отклоняется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://172.16.0.1/webhook")

    def test_link_local_ip_rejected(self) -> None:
        """Link-local IP адрес отклоняется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://169.254.1.1/webhook")

    def test_domain_name_allowed(self) -> None:
        """Доменное имя разрешено."""
        url = WebhookUrl("https://example.com/webhook")
        assert url.value == "https://example.com/webhook"

    def test_equality(self) -> None:
        """Проверка равенства."""
        url1 = WebhookUrl("https://example.com/webhook")
        url2 = WebhookUrl("https://example.com/webhook")
        assert url1 == url2

    def test_inequality(self) -> None:
        """Проверка неравенства."""
        url1 = WebhookUrl("https://example.com/webhook")
        url2 = WebhookUrl("https://example.com/other")
        assert url1 != url2

    def test_hash(self) -> None:
        """Проверка хэша."""
        url1 = WebhookUrl("https://example.com/webhook")
        url2 = WebhookUrl("https://example.com/webhook")
        assert hash(url1) == hash(url2)

    def test_str_representation(self) -> None:
        """Строковое представление."""
        url = WebhookUrl("https://example.com/webhook")
        assert str(url) == "https://example.com/webhook"


class TestWebhookMethodRobustness:
    """Тесты robustness для WebhookMethod."""

    def test_non_string_method_rejected(self) -> None:
        """Не-string метод отклоняется."""
        with pytest.raises(ValidationError, match="Method must be str"):
            WebhookMethod(123)  # type: ignore

    def test_none_method_rejected(self) -> None:
        """None метод отклоняется."""
        with pytest.raises(ValidationError, match="Method must be str"):
            WebhookMethod(None)  # type: ignore

    def test_bytes_method_rejected(self) -> None:
        """Bytes метод отклоняется."""
        with pytest.raises(ValidationError, match="Method must be str"):
            WebhookMethod(b"POST")  # type: ignore


class TestWebhookMethod:
    """Тесты для WebhookMethod Value Object."""

    def test_valid_post_method(self) -> None:
        """Валидный POST метод."""
        method = WebhookMethod("POST")
        assert method.value == "POST"

    def test_valid_get_method(self) -> None:
        """Валидный GET метод."""
        method = WebhookMethod("GET")
        assert method.value == "GET"

    def test_valid_put_method(self) -> None:
        """Валидный PUT метод."""
        method = WebhookMethod("PUT")
        assert method.value == "PUT"

    def test_valid_patch_method(self) -> None:
        """Валидный PATCH метод."""
        method = WebhookMethod("PATCH")
        assert method.value == "PATCH"

    def test_valid_delete_method(self) -> None:
        """Валидный DELETE метод."""
        method = WebhookMethod("DELETE")
        assert method.value == "DELETE"

    def test_lowercase_post_method(self) -> None:
        """Метод в нижнем регистре приводится к верхнему."""
        method = WebhookMethod("post")
        assert method.value == "POST"

    def test_mixed_case_method(self) -> None:
        """Метод в смешанном регистре приводится к верхнему."""
        method = WebhookMethod("PoSt")
        assert method.value == "POST"

    def test_invalid_method(self) -> None:
        """Невалидный метод вызывает ошибку."""
        with pytest.raises(ValidationError, match="Метод INVALID не разрешён"):
            WebhookMethod("INVALID")

    def test_invalid_options_method(self) -> None:
        """Метод OPTIONS не разрешён."""
        with pytest.raises(ValidationError, match="Метод OPTIONS не разрешён"):
            WebhookMethod("OPTIONS")

    def test_invalid_head_method(self) -> None:
        """Метод HEAD не разрешён."""
        with pytest.raises(ValidationError, match="Метод HEAD не разрешён"):
            WebhookMethod("HEAD")

    def test_empty_method(self) -> None:
        """Пустой метод вызывает ошибку."""
        with pytest.raises(ValidationError):
            WebhookMethod("")

    def test_equality(self) -> None:
        """Проверка равенства."""
        method1 = WebhookMethod("POST")
        method2 = WebhookMethod("POST")
        assert method1 == method2

    def test_inequality(self) -> None:
        """Проверка неравенства."""
        method1 = WebhookMethod("POST")
        method2 = WebhookMethod("GET")
        assert method1 != method2

    def test_hash(self) -> None:
        """Проверка хэша."""
        method1 = WebhookMethod("POST")
        method2 = WebhookMethod("POST")
        assert hash(method1) == hash(method2)

    def test_str_representation(self) -> None:
        """Строковое представление."""
        method = WebhookMethod("POST")
        assert str(method) == "POST"


class TestWebhookUrlIPv6SSRFProtection:
    """Тесты защиты от SSRF через IPv6."""

    def test_localhost_ipv6_blocked(self) -> None:
        """::1 (localhost IPv6) блокируется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://[::1]/webhook")

    def test_private_ipv6_fc00_blocked(self) -> None:
        """fc00::/8 (unique local) блокируется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://[fc00::1]/webhook")

    def test_private_ipv6_fd00_blocked(self) -> None:
        """fd00::/8 (private) блокируется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://[fd00:dead:beef::1]/webhook")

    def test_link_local_ipv6_blocked(self) -> None:
        """fe80::/10 (link-local) блокируется."""
        with pytest.raises(ValidationError, match="Private IP запрещён"):
            WebhookUrl("https://[fe80::1]/webhook")

    def test_global_ipv6_allowed(self) -> None:
        """Глобальный IPv6 адрес разрешён (2001:4860:4860::8888 — Google DNS)."""
        url = WebhookUrl("https://[2001:4860:4860::8888]/webhook")
        assert url.value == "https://[2001:4860:4860::8888]/webhook"
