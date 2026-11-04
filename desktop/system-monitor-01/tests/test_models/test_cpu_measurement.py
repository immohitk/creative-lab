from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from system_monitor.models.cpu_measurement import CpuMeasurement


def make_measurement(**overrides):
    now = datetime.now(timezone.utc)

    values = {
        "overall_percent": 50.0,
        "per_cpu_percent": (40.0, 60.0),
        "logical_cpu_count": 2,
        "sampling_interval": 1.0,
        "started_at": now,
        "completed_at": now + timedelta(seconds=1),
    }
    values.update(overrides)

    return CpuMeasurement(**values)


def test_valid_measurement_is_created():
    measurement = make_measurement()

    assert measurement.overall_percent == 50.0
    assert measurement.per_cpu_percent == (40.0, 60.0)
    assert measurement.logical_cpu_count == 2


def test_per_cpu_readings_are_immutable():
    readings = [40.0, 60.0]
    measurement = make_measurement(per_cpu_percent=readings)

    readings[0] = 99.0

    assert measurement.per_cpu_percent == (40.0, 60.0)
    assert isinstance(measurement.per_cpu_percent, tuple)


def test_measurement_fields_cannot_be_modified():
    measurement = make_measurement()

    with pytest.raises(FrozenInstanceError):
        measurement.overall_percent = 80.0


@pytest.mark.parametrize(
    "value",
    [True, -1, 101, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_overall_utilization_is_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(overall_percent=value)


@pytest.mark.parametrize(
    "value",
    [True, -1, 101, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_per_cpu_utilization_is_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(per_cpu_percent=(value, 60.0))


def test_logical_cpu_count_must_match_readings():
    with pytest.raises(ValueError):
        make_measurement(logical_cpu_count=4)


@pytest.mark.parametrize(
    "interval",
    [0, -1, 0.49, 60.01, True, float("nan"), float("inf")],
)
def test_invalid_sampling_interval_is_rejected(interval):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(sampling_interval=interval)


def test_completion_cannot_precede_start():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        make_measurement(
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )


def test_timestamps_must_be_timezone_aware():
    now = datetime.now()

    with pytest.raises(ValueError):
        make_measurement(started_at=now)


def test_values_are_rounded_to_two_decimal_places():
    measurement = make_measurement(
        overall_percent=50.126,
        per_cpu_percent=(40.126, 60.126),
    )

    assert measurement.overall_percent == 50.13
    assert measurement.per_cpu_percent == (40.13, 60.13)
