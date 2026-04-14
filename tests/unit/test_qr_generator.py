"""
Модульные тесты для функций генерации QR кодов.

Тестируют:
- generate_qr_data()
- create_qr_image()
"""

import base64

from src.auth.qr_generator import generate_qr_data, create_qr_image


class TestGenerateQrData:
    """Тесты функции generate_qr_data."""

    def test_generate_qr_data_valid(self) -> None:
        """Корректные байты — формат tg://login?token=..."""
        token_bytes = b"test_token_bytes"

        result = generate_qr_data(token_bytes)

        assert result.startswith("tg://login?token=")

    def test_generate_qr_data_base64_encoding(self) -> None:
        """Проверка base64 кодирования."""
        token_bytes = b"hello"
        expected_b64 = base64.b64encode(token_bytes).decode("ascii")

        result = generate_qr_data(token_bytes)

        assert result == f"tg://login?token={expected_b64}"

    def test_generate_qr_data_empty_bytes(self) -> None:
        """Пустые байты — корректный результат с пустым токеном."""
        token_bytes = b""
        expected_b64 = base64.b64encode(token_bytes).decode("ascii")

        result = generate_qr_data(token_bytes)

        assert result == f"tg://login?token={expected_b64}"

    def test_generate_qr_data_bytearray(self) -> None:
        """Поддержка bytearray наряду с bytes."""
        token_bytes = bytearray(b"bytearray_token")
        expected_b64 = base64.b64encode(token_bytes).decode("ascii")

        result = generate_qr_data(token_bytes)

        assert result == f"tg://login?token={expected_b64}"

    def test_generate_qr_data_large_token(self) -> None:
        """Большой токен корректно кодируется."""
        token_bytes = b"x" * 1000
        expected_b64 = base64.b64encode(token_bytes).decode("ascii")

        result = generate_qr_data(token_bytes)

        assert result == f"tg://login?token={expected_b64}"


class TestCreateQrImage:
    """Тесты функции create_qr_image."""

    def test_create_qr_image_returns_base64(self) -> None:
        """Возвращает строку data:image/png;base64,..."""
        result = create_qr_image("tg://login?token=test")

        assert result.startswith("data:image/png;base64,")

    def test_create_qr_image_valid_data(self) -> None:
        """Валидные данные создают изображение."""
        data = "tg://login?token=dGVzdF90b2tlbg=="

        result = create_qr_image(data)

        base64_data = result.split(",", 1)[1]
        decoded = base64.b64decode(base64_data)

        assert len(decoded) > 0
        assert decoded.startswith(b"\x89PNG")

    def test_create_qr_image_different_data(self) -> None:
        """Разные данные — разные изображения."""
        result1 = create_qr_image("tg://login?token=token_a")
        result2 = create_qr_image("tg://login?token=token_b")

        assert result1 != result2
