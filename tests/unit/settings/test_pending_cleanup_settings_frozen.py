"""Тесты immutable PendingCleanupSettings."""
import dataclasses
import pytest
from src.settings.domain import PendingCleanupSettings
from src.settings.domain.pending_cleanup_settings import Minutes


def test_pending_cleanup_settings_default_values():
    """Значения по умолчанию."""
    settings = PendingCleanupSettings(
        ttl_minutes=Minutes(240),
        cleanup_interval_minutes=Minutes(60),
    )
    assert settings.ttl_minutes == Minutes(240)
    assert settings.cleanup_interval_minutes == Minutes(60)


def test_pending_cleanup_settings_custom_values():
    """Кастомные значения."""
    settings = PendingCleanupSettings(
        ttl_minutes=Minutes(120),
        cleanup_interval_minutes=Minutes(30),
    )
    assert settings.ttl_minutes == Minutes(120)
    assert settings.cleanup_interval_minutes == Minutes(30)


def test_pending_cleanup_settings_immutable():
    """Dataclass заморожен."""
    settings = PendingCleanupSettings(
        ttl_minutes=Minutes(240),
        cleanup_interval_minutes=Minutes(60),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.ttl_minutes = Minutes(100)


def test_pending_cleanup_settings_equality():
    """Проверка равенства."""
    s1 = PendingCleanupSettings(
        ttl_minutes=Minutes(240),
        cleanup_interval_minutes=Minutes(60),
    )
    s2 = PendingCleanupSettings(
        ttl_minutes=Minutes(240),
        cleanup_interval_minutes=Minutes(60),
    )
    assert s1 == s2


def test_pending_cleanup_settings_valid_ttl():
    """Минимальное TTL значение."""
    settings = PendingCleanupSettings(
        ttl_minutes=Minutes(1),
        cleanup_interval_minutes=Minutes(60),
    )
    assert settings.ttl_minutes == Minutes(1)


def test_pending_cleanup_settings_valid_interval():
    """Минимальное значение интервала."""
    settings = PendingCleanupSettings(
        ttl_minutes=Minutes(240),
        cleanup_interval_minutes=Minutes(1),
    )
    assert settings.cleanup_interval_minutes == Minutes(1)


def test_minutes_value_object_positive():
    """Minutes VO принимает только положительные значения."""
    m = Minutes(60)
    assert m.value == 60
    assert int(m) == 60


def test_minutes_value_object_zero_rejected():
    """Minutes VO отклоняет ноль."""
    with pytest.raises(ValueError):
        Minutes(0)


def test_minutes_value_object_negative_rejected():
    """Minutes VO отклоняет отрицательные значения."""
    with pytest.raises(ValueError):
        Minutes(-10)


def test_minutes_value_object_immutability():
    """Minutes VO заморожен."""
    m = Minutes(60)
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.value = 100
