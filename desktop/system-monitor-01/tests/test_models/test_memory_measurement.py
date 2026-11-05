from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from system_monitor.models.memory_measurement import MemoryMeasurement


def make_measurement(**overrides):
    now = datetime.now(timezone.utc)

    values = {
        "total_bytes": 16_000,
        "used_bytes": 8_000,
        "available_bytes": 7_000,
        "free_bytes": 6_000,
        "percent": 50.0,
        "swap_total_bytes": 4_000,
        "swap_used_bytes": 1_000,
        "swap_free_bytes": 3_000,
        "swap_percent": 25.0,
        "sampling_interval": 1.0,
        "started_at": now,
        "completed_at": now + timedelta(seconds=1),
    }
    values.update(overrides)

    return MemoryMeasurement(**values)


def test_valid_measurement_is_created():
    measurement = make_measurement()

    assert measurement.total_bytes == 16_000
    assert measurement.percent == 50.0
    assert measurement.swap_total_bytes == 4_000
    assert measurement.swap_percent == 25.0


def test_measurement_is_immutable():
    measurement = make_measurement()

    with pytest.raises(FrozenInstanceError):
        measurement.used_bytes = 10_000


@pytest.mark.parametrize(
    "field",
    [
        "total_bytes",
        "used_bytes",
        "available_bytes",
        "free_bytes",
        "swap_total_bytes",
        "swap_used_bytes",
        "swap_free_bytes",
    ],
)
def test_byte_fields_reject_boolean(field):
    with pytest.raises(TypeError):
        make_measurement(**{field: True})


@pytest.mark.parametrize(
    "field",
    [
        "total_bytes",
        "used_bytes",
        "available_bytes",
        "free_bytes",
        "swap_total_bytes",
        "swap_used_bytes",
        "swap_free_bytes",
    ],
)
def test_byte_fields_reject_negative_values(field):
    with pytest.raises(ValueError):
        make_measurement(**{field: -1})


@pytest.mark.parametrize(
    "field",
    ["percent", "swap_percent"],
)
@pytest.mark.parametrize(
    "value",
    [True, -1, 101, float("nan"), float("inf"), float("-inf")],
)
def test_percentages_reject_invalid_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(**{field: value})


def test_zero_sized_swap_is_valid():
    measurement = make_measurement(
        swap_total_bytes=0,
        swap_used_bytes=0,
        swap_free_bytes=0,
        swap_percent=0.0,
    )

    assert measurement.swap_total_bytes == 0
    assert measurement.swap_percent == 0.0


def test_used_memory_cannot_exceed_total():
    with pytest.raises(ValueError):
        make_measurement(used_bytes=16_001)


def test_used_swap_cannot_exceed_total():
    with pytest.raises(ValueError):
        make_measurement(swap_used_bytes=4_001)


def test_completion_cannot_precede_start():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        make_measurement(
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )


def test_timestamps_must_be_utc_aware():
    with pytest.raises(ValueError):
        make_measurement(started_at=datetime.now())


@pytest.mark.parametrize(
    "interval",
    [0, -1, 0.49, 60.01, True, float("nan"), float("inf")],
)
def test_invalid_sampling_interval_is_rejected(interval):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(sampling_interval=interval)


def test_percentages_are_rounded_to_two_decimal_places():
    measurement = make_measurement(percent=50.126, swap_percent=25.126)

    assert measurement.percent == 50.13
    assert measurement.swap_percent == 25.13
