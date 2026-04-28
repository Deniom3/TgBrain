"""
Тесты для ChatFilterConfig — конфигурации фильтров сообщений чата.
"""

import dataclasses

import pytest

from src.domain.exceptions import ValidationError
from src.domain.models.chat_filter_config import ChatFilterConfig


def test_defaults() -> None:
    config = ChatFilterConfig()
    assert config.filter_bots is True
    assert config.filter_actions is True
    assert config.filter_min_length == 15
    assert config.filter_ads is True


def test_valid_zero_min_length() -> None:
    config = ChatFilterConfig(filter_min_length=0)
    assert config.filter_min_length == 0


def test_negative_min_length_raises() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ChatFilterConfig(filter_min_length=-1)
    assert exc_info.value.field == "filter_min_length"


def test_custom_values() -> None:
    config = ChatFilterConfig(
        filter_bots=False,
        filter_actions=False,
        filter_min_length=100,
        filter_ads=False,
    )
    assert config.filter_bots is False
    assert config.filter_actions is False
    assert config.filter_min_length == 100
    assert config.filter_ads is False


def test_equality_and_hash() -> None:
    config1 = ChatFilterConfig()
    config2 = ChatFilterConfig()
    assert config1 == config2
    assert hash(config1) == hash(config2)

    config3 = ChatFilterConfig(filter_bots=False)
    assert config1 != config3
    assert hash(config1) != hash(config3)


def test_immutability() -> None:
    config = ChatFilterConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.filter_bots = False
