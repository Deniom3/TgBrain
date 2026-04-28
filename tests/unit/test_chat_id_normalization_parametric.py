"""
Параметрические тесты нормализации chat_id.
"""

import pytest

from src.ingestion.chat_sync_service import normalize_chat_id


@pytest.mark.parametrize(
    "raw_id,expected",
    [
        (123, -1000000000123),
        (456789, -1000000456789),
        (9999999999, -1009999999999),
    ],
)
def test_normalize_positive_channel_ids(raw_id: int, expected: int) -> None:
    result = normalize_chat_id(raw_id, is_channel=True)
    assert result == expected


@pytest.mark.parametrize(
    "raw_id,expected",
    [
        (-1001234567890, -1001234567890),
        (-1009999999999, -1009999999999),
    ],
)
def test_normalize_already_normalized_channel_ids(raw_id: int, expected: int) -> None:
    result = normalize_chat_id(raw_id, is_channel=True)
    assert result == expected


@pytest.mark.parametrize(
    "raw_id,expected",
    [
        (-1, -1000000000001),
        (-999, -1000000000999),
        (-1234567890, -1001234567890),
    ],
)
def test_normalize_negative_without_prefix_channel_ids(
    raw_id: int, expected: int
) -> None:
    result = normalize_chat_id(raw_id, is_channel=True)
    assert result == expected


@pytest.mark.parametrize(
    "raw_id,expected",
    [
        (1, 1),
        (100, 100),
        (-100, -100),
    ],
)
def test_normalize_non_channel_ids(raw_id: int, expected: int) -> None:
    result = normalize_chat_id(raw_id, is_channel=False)
    assert result == expected
