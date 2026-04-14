"""
Генерация QR кодов для авторизации Telegram.

Функции:
- generate_qr_data: Генерация данных для QR кода из токена
- create_qr_image: Создание QR изображения в base64
"""

import base64
import io
from typing import Union

import qrcode


def generate_qr_data(token_bytes: Union[bytes, bytearray]) -> str:
    """
    Сгенерировать данные для QR кода.

    Args:
        token_bytes: Токен авторизации в виде байтов

    Returns:
        Строка для QR кода в формате tg://login?token=...
    """
    # Формат данных QR кода для Telegram
    # Токен должен быть закодирован в base64, а не в hex
    token_b64 = base64.b64encode(token_bytes).decode('ascii')
    qr_data = f"tg://login?token={token_b64}"
    return qr_data


def create_qr_image(data: str) -> str:
    """
    Создать QR код и вернуть его в формате base64.

    Args:
        data: Данные для QR кода (tg://login?token=...)

    Returns:
        Base64 строка изображения в формате data:image/png;base64,...
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Конвертируем в base64
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_str}"
