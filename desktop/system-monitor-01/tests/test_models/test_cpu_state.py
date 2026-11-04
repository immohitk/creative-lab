from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from system_monitor.models import (
    CpuError,
    CpuMeasurement,
    CpuMeasurementFreshness,
    CpuMeasurementStatus,
    CpuStateSnapshot,
    CpuWorkerState,
)


def make_measurement():
    now = datetime.now(timezone.utc)

    return CpuMeasurement(
        overall_percent=50.0,
        per_cpu_percent=(40.0, 60.0),
        logical_cpu_count=2,
        sampling_interval=1.0,
        started_at=now,
        completed_at=now + timedelta(seconds=1),
    )


def make_snapshot(**overrides):
    values = {
        "worker_state": CpuWorkerState.RUNNING,
        "measurement_status": CpuMeasurementStatus.INITIALIZING,
        "last_successful_measurement": None,
        "last_successful_monotonic": None,
        "measurement_error": None,
        "worker_error": None,
        "consecutive_failures": 0,
        "sampling_interval": 1.0,
        "revision": 0,
    }
    values.update(overrides)

    return CpuStateSnapshot(**values)


def test_snapshot_without_measurement_has_no_data_freshness():
    snapshot = make_snapshot()

    assert snapshot.freshness == CpuMeasurementFreshness.NO_DATA
    assert snapshot.last_successful_age(100.0) is None


def test_snapshot_with_available_measurement_is_fresh():
    snapshot = make_snapshot(
        measurement_status=CpuMeasurementStatus.AVAILABLE,
        last_successful_measurement=make_measurement(),
        last_successful_monotonic=100.0,
    )

    assert snapshot.freshness == CpuMeasurementFreshness.FRESH


@pytest.mark.parametrize(
    "status",
    [
        CpuMeasurementStatus.INITIALIZING,
        CpuMeasurementStatus.UNAVAILABLE,
    ],
)
def test_snapshot_with_existing_measurement_and_non_available_status_is_stale(
    status,
):
    snapshot = make_snapshot(
        measurement_status=status,
        last_successful_measurement=make_measurement(),
        last_successful_monotonic=100.0,
    )

    assert snapshot.freshness == CpuMeasurementFreshness.STALE


def test_last_successful_age_uses_monotonic_time():
    snapshot = make_snapshot(
        last_successful_measurement=make_measurement(),
        last_successful_monotonic=100.0,
    )

    assert snapshot.last_successful_age(105.5) == 5.5


def test_last_successful_age_never_returns_negative_value():
    snapshot = make_snapshot(
        last_successful_measurement=make_measurement(),
        last_successful_monotonic=100.0,
    )

    assert snapshot.last_successful_age(90.0) == 0.0


def test_measurement_and_monotonic_reference_must_exist_together():
    with pytest.raises(ValueError):
        make_snapshot(
            last_successful_measurement=make_measurement(),
        )

    with pytest.raises(ValueError):
        make_snapshot(
            last_successful_monotonic=100.0,
        )


def test_snapshot_fields_are_immutable():
    snapshot = make_snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.revision = 10


@pytest.mark.parametrize("revision", [-1, True, 1.5])
def test_invalid_revision_is_rejected(revision):
    with pytest.raises(ValueError):
        make_snapshot(revision=revision)


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_invalid_consecutive_failure_count_is_rejected(count):
    with pytest.raises(ValueError):
        make_snapshot(consecutive_failures=count)


def test_invalid_monotonic_reference_is_rejected():
    with pytest.raises(ValueError):
        make_snapshot(
            last_successful_measurement=make_measurement(),
            last_successful_monotonic=float("nan"),
        )


def test_measurement_error_is_preserved_in_snapshot():
    error = CpuError(
        error_code="CPU_MEASUREMENT_FAILED",
        message="CPU measurement is temporarily unavailable.",
        occurred_at=datetime.now(timezone.utc),
        consecutive_failures=1,
    )

    snapshot = make_snapshot(
        measurement_error=error,
        consecutive_failures=1,
    )

    assert snapshot.measurement_error is error
    assert snapshot.consecutive_failures == 1
