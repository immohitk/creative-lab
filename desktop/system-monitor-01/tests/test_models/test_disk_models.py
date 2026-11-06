from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from system_monitor.models.disk_error import DiskError
from system_monitor.models.disk_measurement import DiskMeasurement
from system_monitor.models.disk_operation_result import (
    DiskConfigurationResult,
    DiskStartResult,
    DiskStopResult,
)
from system_monitor.models.disk_state import DiskStateSnapshot
from system_monitor.models.disk_status import (
    DiskMeasurementFreshness,
    DiskMeasurementStatus,
    DiskWorkerState,
)
from system_monitor.models.disk_volume_measurement import DiskVolumeMeasurement


def make_volume(**overrides):
    values = {
        "volume_id": DiskVolumeMeasurement.build_volume_id("C:", "C:\\"),
        "device": "C:",
        "mount_point": "C:\\",
        "filesystem": "NTFS",
        "total_bytes": 10_000,
        "used_bytes": 4_000,
        "free_bytes": 6_000,
        "percent": 40.0,
    }
    values.update(overrides)
    return DiskVolumeMeasurement(**values)


def make_error(**overrides):
    values = {
        "error_code": "VOLUME_ACCESS_FAILED",
        "message": "Volume could not be accessed.",
        "occurred_at": datetime.now(timezone.utc),
        "volume_id": DiskVolumeMeasurement.build_volume_id("D:", "D:\\"),
        "device": "D:",
        "mount_point": "D:\\",
    }
    values.update(overrides)
    return DiskError(**values)


def make_measurement(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "volumes": (make_volume(),),
        "volume_errors": (),
        "sampling_interval": 1.0,
        "started_at": now,
        "completed_at": now + timedelta(milliseconds=100),
    }
    values.update(overrides)
    return DiskMeasurement(**values)


def make_state(**overrides):
    measurement = make_measurement()
    values = {
        "worker_state": DiskWorkerState.RUNNING,
        "measurement_status": DiskMeasurementStatus.AVAILABLE,
        "latest_measurement": measurement,
        "last_successful_measurement": measurement,
        "last_successful_monotonic": 100.0,
        "measurement_error": None,
        "worker_error": None,
        "consecutive_failures": 0,
        "sampling_interval": 1.0,
        "revision": 1,
    }
    values.update(overrides)
    return DiskStateSnapshot(**values)


# DiskVolumeMeasurement

def test_valid_volume_measurement_is_created():
    volume = make_volume()

    assert volume.device == "C:"
    assert volume.mount_point == "C:\\"
    assert volume.filesystem == "NTFS"
    assert volume.total_bytes == 10_000
    assert volume.used_bytes == 4_000
    assert volume.free_bytes == 6_000
    assert volume.percent == 40.0


def test_volume_identity_is_built_from_device_and_mount_point():
    volume = make_volume()

    assert volume.volume_id == "C:::C:\\"


def test_volume_measurement_is_immutable():
    volume = make_volume()

    with pytest.raises(FrozenInstanceError):
        volume.used_bytes = 5_000


@pytest.mark.parametrize("field", ["volume_id", "device", "mount_point"])
@pytest.mark.parametrize("value", ["", " ", None, 123])
def test_volume_identity_fields_reject_invalid_values(field, value):
    with pytest.raises((TypeError, ValueError)):
        make_volume(**{field: value})


def test_volume_identity_must_match_device_and_mount_point():
    with pytest.raises(ValueError):
        make_volume(volume_id="wrong-identity")


def test_filesystem_can_be_none():
    volume = make_volume(filesystem=None)

    assert volume.filesystem is None


@pytest.mark.parametrize("value", ["", " "])
def test_filesystem_rejects_empty_string(value):
    with pytest.raises(ValueError):
        make_volume(filesystem=value)


def test_filesystem_rejects_non_string():
    with pytest.raises(TypeError):
        make_volume(filesystem=123)


@pytest.mark.parametrize("field", ["total_bytes", "used_bytes", "free_bytes"])
def test_byte_fields_reject_boolean(field):
    with pytest.raises(TypeError):
        make_volume(**{field: True})


@pytest.mark.parametrize("field", ["total_bytes", "used_bytes", "free_bytes"])
def test_byte_fields_reject_negative_values(field):
    with pytest.raises(ValueError):
        make_volume(**{field: -1})


def test_total_capacity_must_be_positive():
    with pytest.raises(ValueError):
        make_volume(total_bytes=0, used_bytes=0, free_bytes=0)


def test_used_bytes_cannot_exceed_total():
    with pytest.raises(ValueError):
        make_volume(used_bytes=10_001, free_bytes=0)


def test_free_bytes_cannot_exceed_total():
    with pytest.raises(ValueError):
        make_volume(used_bytes=0, free_bytes=10_001)


def test_used_and_free_must_equal_total():
    with pytest.raises(ValueError):
        make_volume(used_bytes=4_000, free_bytes=5_999)


@pytest.mark.parametrize(
    "value",
    [True, -1, 101, float("nan"), float("inf"), float("-inf")],
)
def test_volume_percentage_rejects_invalid_values(value):
    with pytest.raises((TypeError, ValueError)):
        make_volume(percent=value)


def test_volume_percentage_is_rounded():
    volume = make_volume(percent=40.126)

    assert volume.percent == 40.13


def test_volume_id_builder_rejects_invalid_arguments():
    with pytest.raises(ValueError):
        DiskVolumeMeasurement.build_volume_id("", "C:\\")

    with pytest.raises(ValueError):
        DiskVolumeMeasurement.build_volume_id("C:", "")


# DiskError

def test_valid_disk_error_is_created():
    error = make_error()

    assert error.error_code == "VOLUME_ACCESS_FAILED"
    assert error.volume_id is not None
    assert error.consecutive_failures == 0


def test_disk_error_is_immutable():
    error = make_error()

    with pytest.raises(FrozenInstanceError):
        error.message = "Changed"


@pytest.mark.parametrize("field", ["error_code", "message"])
@pytest.mark.parametrize("value", ["", " "])
def test_disk_error_rejects_empty_required_text(field, value):
    with pytest.raises(ValueError):
        make_error(**{field: value})


def test_disk_error_rejects_non_string_code():
    with pytest.raises(ValueError):
        make_error(error_code=123)


def test_disk_error_requires_utc_timestamp():
    with pytest.raises(ValueError):
        make_error(occurred_at=datetime.now())


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_disk_error_rejects_invalid_consecutive_failures(value):
    with pytest.raises(ValueError):
        make_error(consecutive_failures=value)


def test_collection_error_can_have_no_volume_context():
    error = make_error(
        volume_id=None,
        device=None,
        mount_point=None,
        error_code="PARTITION_ENUMERATION_FAILED",
    )

    assert error.volume_id is None
    assert error.device is None
    assert error.mount_point is None


# DiskMeasurement

def test_valid_disk_measurement_is_created():
    measurement = make_measurement()

    assert len(measurement.volumes) == 1
    assert measurement.volume_errors == ()
    assert measurement.is_fully_successful
    assert not measurement.is_partial
    assert not measurement.is_empty
    assert not measurement.is_unavailable


def test_disk_measurement_converts_collections_to_tuples():
    volumes = [make_volume()]
    errors = []

    measurement = make_measurement(
        volumes=volumes,
        volume_errors=errors,
    )

    assert isinstance(measurement.volumes, tuple)
    assert isinstance(measurement.volume_errors, tuple)


def test_disk_measurement_is_immutable():
    measurement = make_measurement()

    with pytest.raises(FrozenInstanceError):
        measurement.sampling_interval = 2.0


def test_empty_inventory_is_a_successful_measurement():
    measurement = make_measurement(volumes=(), volume_errors=())

    assert measurement.is_empty
    assert measurement.is_fully_successful
    assert not measurement.is_unavailable


def test_partial_measurement_preserves_successful_volumes_and_errors():
    volume = make_volume()
    error = make_error()

    measurement = make_measurement(
        volumes=(volume,),
        volume_errors=(error,),
    )

    assert measurement.is_partial
    assert not measurement.is_fully_successful
    assert len(measurement.volumes) == 1
    assert len(measurement.volume_errors) == 1


def test_all_volume_failures_are_unavailable():
    measurement = make_measurement(
        volumes=(),
        volume_errors=(make_error(),),
    )

    assert measurement.is_unavailable
    assert not measurement.is_partial
    assert not measurement.is_fully_successful


def test_measurement_rejects_duplicate_volume_identities():
    volume = make_volume()

    with pytest.raises(ValueError):
        make_measurement(volumes=(volume, volume))


def test_measurement_rejects_duplicate_volume_errors():
    error = make_error()

    with pytest.raises(ValueError):
        make_measurement(volume_errors=(error, error))


def test_measurement_rejects_volume_and_error_identity_collision():
    volume = make_volume()
    error = make_error(
        volume_id=volume.volume_id,
        device=volume.device,
        mount_point=volume.mount_point,
    )

    with pytest.raises(ValueError):
        make_measurement(volumes=(volume,), volume_errors=(error,))


def test_measurement_rejects_invalid_volume_collection():
    with pytest.raises(TypeError):
        make_measurement(volumes=("invalid",))


def test_measurement_rejects_invalid_error_collection():
    with pytest.raises(TypeError):
        make_measurement(volume_errors=("invalid",))


@pytest.mark.parametrize(
    "interval",
    [0, -1, 0.49, 60.01, True, float("nan"), float("inf")],
)
def test_measurement_rejects_invalid_sampling_interval(interval):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(sampling_interval=interval)


def test_measurement_rejects_non_utc_timestamps():
    with pytest.raises(ValueError):
        make_measurement(started_at=datetime.now())


def test_measurement_rejects_completion_before_start():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        make_measurement(
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )


# DiskStateSnapshot

def test_valid_disk_state_snapshot_is_created():
    state = make_state()

    assert state.worker_state == DiskWorkerState.RUNNING
    assert state.measurement_status == DiskMeasurementStatus.AVAILABLE
    assert state.freshness == DiskMeasurementFreshness.FRESH
    assert state.revision == 1


def test_disk_state_snapshot_is_immutable():
    state = make_state()

    with pytest.raises(FrozenInstanceError):
        state.revision = 2


def test_initial_state_has_no_data_freshness():
    state = make_state(
        measurement_status=DiskMeasurementStatus.INITIALIZING,
        latest_measurement=None,
        last_successful_measurement=None,
        last_successful_monotonic=None,
    )

    assert state.freshness == DiskMeasurementFreshness.NO_DATA


def test_partial_state_is_stale_against_last_full_success():
    partial = make_measurement(
        volume_errors=(make_error(),),
    )
    full = make_measurement()

    state = make_state(
        measurement_status=DiskMeasurementStatus.PARTIAL,
        latest_measurement=partial,
        last_successful_measurement=full,
        last_successful_monotonic=100.0,
    )

    assert state.freshness == DiskMeasurementFreshness.STALE


def test_unavailable_state_preserves_last_full_success():
    unavailable = make_measurement(
        volumes=(),
        volume_errors=(make_error(volume_id=None),),
    )
    full = make_measurement()

    state = make_state(
        measurement_status=DiskMeasurementStatus.UNAVAILABLE,
        latest_measurement=unavailable,
        last_successful_measurement=full,
        last_successful_monotonic=100.0,
    )

    assert state.latest_measurement.is_unavailable
    assert state.last_successful_measurement is full
    assert state.freshness == DiskMeasurementFreshness.STALE


def test_empty_inventory_can_be_available_and_fresh():
    empty = make_measurement(volumes=(), volume_errors=())

    state = make_state(
        measurement_status=DiskMeasurementStatus.AVAILABLE,
        latest_measurement=empty,
        last_successful_measurement=empty,
        last_successful_monotonic=100.0,
    )

    assert state.freshness == DiskMeasurementFreshness.FRESH
    assert state.last_successful_measurement.is_empty


def test_available_state_rejects_partial_measurement():
    partial = make_measurement(volume_errors=(make_error(),))

    with pytest.raises(ValueError):
        make_state(
            measurement_status=DiskMeasurementStatus.AVAILABLE,
            latest_measurement=partial,
        )


def test_partial_state_rejects_full_measurement():
    with pytest.raises(ValueError):
        make_state(
            measurement_status=DiskMeasurementStatus.PARTIAL,
            latest_measurement=make_measurement(),
        )


def test_unavailable_state_rejects_partial_measurement():
    partial = make_measurement(volume_errors=(make_error(),))

    with pytest.raises(ValueError):
        make_state(
            measurement_status=DiskMeasurementStatus.UNAVAILABLE,
            latest_measurement=partial,
        )


def test_initializing_state_rejects_latest_measurement():
    with pytest.raises(ValueError):
        make_state(measurement_status=DiskMeasurementStatus.INITIALIZING)


def test_last_successful_measurement_must_be_fully_successful():
    partial = make_measurement(volume_errors=(make_error(),))

    with pytest.raises(ValueError):
        make_state(
            last_successful_measurement=partial,
        )


def test_successful_measurement_and_monotonic_reference_must_match():
    with pytest.raises(ValueError):
        make_state(last_successful_monotonic=None)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_state_rejects_invalid_monotonic_reference(value):
    with pytest.raises((TypeError, ValueError)):
        make_state(last_successful_monotonic=value)


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_state_rejects_invalid_consecutive_failures(value):
    with pytest.raises(ValueError):
        make_state(consecutive_failures=value)


@pytest.mark.parametrize("value", [-1, True, float("nan"), float("inf"), 60.01])
def test_state_rejects_invalid_sampling_interval(value):
    with pytest.raises((TypeError, ValueError)):
        make_state(sampling_interval=value)


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_state_rejects_invalid_revision(value):
    with pytest.raises(ValueError):
        make_state(revision=value)


def test_last_successful_age_uses_monotonic_time():
    state = make_state(last_successful_monotonic=100.0)

    assert state.last_successful_age(105.5) == 5.5
    assert state.last_successful_age(99.0) == 0.0


def test_last_successful_age_returns_none_without_measurement():
    state = make_state(
        latest_measurement=None,
        measurement_status=DiskMeasurementStatus.INITIALIZING,
        last_successful_measurement=None,
        last_successful_monotonic=None,
    )

    assert state.last_successful_age(105.0) is None


def test_last_successful_age_rejects_invalid_current_time():
    state = make_state()

    with pytest.raises((TypeError, ValueError)):
        state.last_successful_age(float("nan"))


# Disk operation results

def test_disk_start_result_is_created():
    result = DiskStartResult(
        accepted=True,
        worker_state=DiskWorkerState.STARTING,
    )

    assert result.accepted
    assert result.worker_state == DiskWorkerState.STARTING


def test_disk_stop_result_is_created():
    result = DiskStopResult(
        success=True,
        worker_state=DiskWorkerState.STOPPED,
    )

    assert result.success
    assert result.worker_state == DiskWorkerState.STOPPED


def test_disk_configuration_result_is_created():
    result = DiskConfigurationResult(
        accepted=True,
        sampling_interval=1,
        worker_state=DiskWorkerState.RUNNING,
    )

    assert result.accepted
    assert result.sampling_interval == 1.0


def test_operation_results_accept_structured_errors():
    error = make_error()

    start = DiskStartResult(
        accepted=False,
        worker_state=DiskWorkerState.FAILED,
        error=error,
    )

    assert start.error is error


def test_configuration_result_rejects_invalid_interval():
    with pytest.raises(ValueError):
        DiskConfigurationResult(
            accepted=True,
            sampling_interval=60.1,
            worker_state=DiskWorkerState.RUNNING,
        )


def test_operation_results_reject_invalid_worker_state():
    with pytest.raises(TypeError):
        DiskStartResult(
            accepted=True,
            worker_state="RUNNING",
        )

