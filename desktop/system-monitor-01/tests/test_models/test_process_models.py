from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from system_monitor.models.process_error import ProcessError
from system_monitor.models.process_measurement import ProcessMeasurement
from system_monitor.models.process_snapshot import ProcessSnapshot


NOW = datetime.now(timezone.utc)


def make_measurement(pid=100, **overrides):
    values = {
        "pid": pid,
        "name": "example.exe",
        "cpu_percent": 12.5,
        "memory_bytes": 1024,
        "status": "running",
        "sampled_at": NOW,
    }
    values.update(overrides)
    return ProcessMeasurement(**values)


def make_error(pid=200, **overrides):
    values = {
        "error_code": "PROCESS_ACCESS_DENIED",
        "message": "Access to this process was denied.",
        "occurred_at": NOW,
        "pid": pid,
    }
    values.update(overrides)
    return ProcessError(**values)


def make_snapshot(**overrides):
    values = {
        "processes": (make_measurement(),),
        "process_errors": (),
        "sampling_interval": 2.0,
        "started_at": NOW,
        "completed_at": NOW + timedelta(milliseconds=10),
    }
    values.update(overrides)
    return ProcessSnapshot(**values)


@pytest.mark.parametrize("pid", [-1, True, 1.5, "100"])
def test_process_measurement_rejects_invalid_pid(pid):
    with pytest.raises(ValueError):
        make_measurement(pid=pid)


@pytest.mark.parametrize("name", ["", " ", None, 123])
def test_process_measurement_rejects_invalid_name(name):
    with pytest.raises(ValueError):
        make_measurement(name=name)


@pytest.mark.parametrize("cpu", [-1, float("nan"), float("inf"), True])
def test_process_measurement_rejects_invalid_cpu_percentage(cpu):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(cpu_percent=cpu)


def test_process_measurement_accepts_unavailable_cpu_percentage():
    measurement = make_measurement(cpu_percent=None)

    assert measurement.cpu_percent is None


def test_process_measurement_normalizes_cpu_percentage():
    measurement = make_measurement(cpu_percent=25)

    assert measurement.cpu_percent == 25.0
    assert isinstance(measurement.cpu_percent, float)


@pytest.mark.parametrize("memory", [-1, True, 1.5, "1024"])
def test_process_measurement_rejects_invalid_memory(memory):
    with pytest.raises((TypeError, ValueError)):
        make_measurement(memory_bytes=memory)


@pytest.mark.parametrize("status", ["", " ", None, 123])
def test_process_measurement_rejects_invalid_status(status):
    with pytest.raises(ValueError):
        make_measurement(status=status)


def test_process_measurement_requires_utc_timestamp():
    with pytest.raises(ValueError):
        make_measurement(
            sampled_at=datetime(2026, 1, 1)
        )


def test_process_measurement_is_immutable():
    measurement = make_measurement()

    with pytest.raises(FrozenInstanceError):
        measurement.pid = 200


@pytest.mark.parametrize("pid", [-1, True, 1.5, "100"])
def test_process_error_rejects_invalid_pid(pid):
    with pytest.raises(ValueError):
        make_error(pid=pid)


def test_process_error_accepts_missing_pid():
    error = make_error(pid=None)

    assert error.pid is None


def test_process_error_rejects_empty_error_code():
    with pytest.raises(ValueError):
        make_error(error_code=" ")


def test_process_error_rejects_empty_message():
    with pytest.raises(ValueError):
        make_error(message="")


def test_process_error_requires_utc_timestamp():
    with pytest.raises(ValueError):
        make_error(occurred_at=datetime(2026, 1, 1))


def test_snapshot_normalizes_lists_to_tuples():
    snapshot = make_snapshot(
        processes=[make_measurement()],
        process_errors=[make_error()],
    )

    assert isinstance(snapshot.processes, tuple)
    assert isinstance(snapshot.process_errors, tuple)


def test_snapshot_rejects_invalid_collection_types():
    with pytest.raises(TypeError):
        make_snapshot(processes="invalid")


def test_snapshot_rejects_invalid_collection_items():
    with pytest.raises(TypeError):
        make_snapshot(processes=(object(),))


def test_snapshot_rejects_duplicate_process_pids():
    with pytest.raises(ValueError):
        make_snapshot(
            processes=(make_measurement(100), make_measurement(100))
        )


def test_snapshot_rejects_duplicate_error_pids():
    with pytest.raises(ValueError):
        make_snapshot(
            processes=(),
            process_errors=(make_error(200), make_error(200)),
        )


def test_snapshot_rejects_pid_present_in_measurement_and_error():
    with pytest.raises(ValueError):
        make_snapshot(
            processes=(make_measurement(100),),
            process_errors=(make_error(100),),
        )


@pytest.mark.parametrize("interval", [0.0, 0.49, 60.01, float("nan"), float("inf")])
def test_snapshot_rejects_invalid_sampling_interval(interval):
    with pytest.raises(ValueError):
        make_snapshot(sampling_interval=interval)


def test_snapshot_rejects_boolean_sampling_interval():
    with pytest.raises(TypeError):
        make_snapshot(sampling_interval=True)


def test_snapshot_rejects_completion_before_start():
    with pytest.raises(ValueError):
        make_snapshot(
            started_at=NOW,
            completed_at=NOW - timedelta(seconds=1),
        )


def test_snapshot_requires_utc_timestamps():
    with pytest.raises(ValueError):
        make_snapshot(
            started_at=datetime(2026, 1, 1),
        )


def test_snapshot_reports_partial_success():
    snapshot = make_snapshot(
        processes=(make_measurement(100),),
        process_errors=(make_error(200),),
    )

    assert snapshot.is_partial
    assert not snapshot.is_fully_successful
    assert not snapshot.is_empty
    assert not snapshot.is_unavailable


def test_snapshot_reports_full_success():
    snapshot = make_snapshot()

    assert snapshot.is_fully_successful
    assert not snapshot.is_partial
    assert not snapshot.is_empty
    assert not snapshot.is_unavailable


def test_snapshot_reports_empty_collection():
    snapshot = make_snapshot(
        processes=(),
        process_errors=(),
    )

    assert snapshot.is_empty
    assert snapshot.is_fully_successful
    assert not snapshot.is_unavailable


def test_snapshot_reports_unavailable_collection():
    snapshot = make_snapshot(
        processes=(),
        process_errors=(make_error(),),
    )

    assert snapshot.is_unavailable
    assert not snapshot.is_fully_successful

# ---------------------------------------------------------------------------
# Process state and operation-result model tests
# ---------------------------------------------------------------------------

from system_monitor.models.process_status import (
    ProcessWorkerState,
    ProcessMeasurementStatus,
    ProcessMeasurementFreshness,
)
from system_monitor.models.process_state import ProcessStateSnapshot
from system_monitor.models.process_operation_result import (
    ProcessStartResult,
    ProcessStopResult,
    ProcessConfigurationResult,
)


def make_state(**overrides):
    values = {
        "worker_state": ProcessWorkerState.STOPPED,
        "measurement_status": ProcessMeasurementStatus.INITIALIZING,
        "latest_measurement": None,
        "last_successful_measurement": None,
        "last_successful_monotonic": None,
        "measurement_error": None,
        "worker_error": None,
        "consecutive_failures": 0,
        "sampling_interval": 2.0,
        "revision": 0,
    }
    values.update(overrides)
    return ProcessStateSnapshot(**values)


def test_process_state_accepts_initial_state():
    state = make_state()

    assert state.worker_state == ProcessWorkerState.STOPPED
    assert state.measurement_status == ProcessMeasurementStatus.INITIALIZING
    assert state.freshness == ProcessMeasurementFreshness.NO_DATA


def test_process_state_accepts_fully_successful_measurement():
    measurement = make_snapshot()

    state = make_state(
        worker_state=ProcessWorkerState.RUNNING,
        measurement_status=ProcessMeasurementStatus.AVAILABLE,
        latest_measurement=measurement,
        last_successful_measurement=measurement,
        last_successful_monotonic=100.0,
    )

    assert state.freshness == ProcessMeasurementFreshness.FRESH


def test_process_state_accepts_empty_successful_measurement():
    measurement = make_snapshot(processes=(), process_errors=())

    state = make_state(
        measurement_status=ProcessMeasurementStatus.AVAILABLE,
        latest_measurement=measurement,
        last_successful_measurement=measurement,
        last_successful_monotonic=100.0,
    )

    assert state.freshness == ProcessMeasurementFreshness.FRESH


def test_process_state_accepts_partial_measurement():
    measurement = make_snapshot(
        processes=(make_measurement(100),),
        process_errors=(make_error(200),),
    )

    state = make_state(
        measurement_status=ProcessMeasurementStatus.PARTIAL,
        latest_measurement=measurement,
        last_successful_measurement=make_snapshot(),
        last_successful_monotonic=100.0,
        consecutive_failures=1,
    )

    assert state.freshness == ProcessMeasurementFreshness.STALE


def test_process_state_accepts_unavailable_measurement():
    measurement = make_snapshot(
        processes=(),
        process_errors=(make_error(),),
    )

    state = make_state(
        measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
        latest_measurement=measurement,
    )

    assert state.freshness == ProcessMeasurementFreshness.NO_DATA


def test_process_state_rejects_available_without_measurement():
    with pytest.raises(ValueError):
        make_state(measurement_status=ProcessMeasurementStatus.AVAILABLE)


def test_process_state_rejects_partial_without_partial_measurement():
    with pytest.raises(ValueError):
        make_state(
            measurement_status=ProcessMeasurementStatus.PARTIAL,
            latest_measurement=make_snapshot(),
        )


def test_process_state_rejects_unavailable_with_successful_measurement():
    with pytest.raises(ValueError):
        make_state(
            measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
            latest_measurement=make_snapshot(),
        )


def test_process_state_rejects_measurement_during_initializing():
    with pytest.raises(ValueError):
        make_state(latest_measurement=make_snapshot())


def test_process_state_rejects_invalid_worker_state():
    with pytest.raises(TypeError):
        make_state(worker_state="RUNNING")


def test_process_state_rejects_invalid_measurement_status():
    with pytest.raises(TypeError):
        make_state(measurement_status="AVAILABLE")


@pytest.mark.parametrize("failures", [-1, True, 1.5])
def test_process_state_rejects_invalid_failure_count(failures):
    with pytest.raises(ValueError):
        make_state(consecutive_failures=failures)


@pytest.mark.parametrize("revision", [-1, True, 1.5])
def test_process_state_rejects_invalid_revision(revision):
    with pytest.raises(ValueError):
        make_state(revision=revision)


@pytest.mark.parametrize("interval", [0.49, 60.01, float("nan"), float("inf")])
def test_process_state_rejects_invalid_sampling_interval(interval):
    with pytest.raises(ValueError):
        make_state(sampling_interval=interval)


def test_process_state_rejects_boolean_sampling_interval():
    with pytest.raises(TypeError):
        make_state(sampling_interval=True)


def test_process_state_rejects_invalid_monotonic_reference():
    with pytest.raises(ValueError):
        make_state(last_successful_monotonic=float("inf"))


def test_process_state_requires_matching_successful_measurement_reference():
    with pytest.raises(ValueError):
        make_state(last_successful_monotonic=100.0)


def test_process_state_rejects_invalid_measurement_error():
    with pytest.raises(TypeError):
        make_state(measurement_error=object())


def test_process_state_rejects_invalid_worker_error():
    with pytest.raises(TypeError):
        make_state(worker_error=object())


def test_process_state_rejects_partial_last_successful_measurement():
    measurement = make_snapshot(
        processes=(make_measurement(100),),
        process_errors=(make_error(200),),
    )

    with pytest.raises(ValueError):
        make_state(
            last_successful_measurement=measurement,
            last_successful_monotonic=100.0,
        )


def test_process_state_calculates_last_successful_age():
    state = make_state(
        last_successful_measurement=make_snapshot(),
        last_successful_monotonic=100.0,
    )

    assert state.last_successful_age(125.0) == 25.0


def test_process_state_age_never_becomes_negative():
    state = make_state(
        last_successful_measurement=make_snapshot(),
        last_successful_monotonic=100.0,
    )

    assert state.last_successful_age(90.0) == 0.0


def test_process_state_without_success_has_no_age():
    assert make_state().last_successful_age(100.0) is None


@pytest.mark.parametrize("now", [True, "100", float("nan"), float("inf")])
def test_process_state_rejects_invalid_current_monotonic_time(now):
    state = make_state(
        last_successful_measurement=make_snapshot(),
        last_successful_monotonic=100.0,
    )

    with pytest.raises((TypeError, ValueError)):
        state.last_successful_age(now)


def test_process_start_result_accepts_valid_result():
    result = ProcessStartResult(
        accepted=True,
        worker_state=ProcessWorkerState.STARTING,
    )

    assert result.accepted
    assert result.worker_state == ProcessWorkerState.STARTING


def test_process_start_result_rejects_invalid_accepted_value():
    with pytest.raises(TypeError):
        ProcessStartResult(
            accepted=1,
            worker_state=ProcessWorkerState.RUNNING,
        )


def test_process_start_result_rejects_invalid_worker_state():
    with pytest.raises(TypeError):
        ProcessStartResult(
            accepted=True,
            worker_state="RUNNING",
        )


def test_process_stop_result_accepts_valid_result():
    result = ProcessStopResult(
        success=True,
        worker_state=ProcessWorkerState.STOPPED,
    )

    assert result.success


def test_process_stop_result_rejects_invalid_success_value():
    with pytest.raises(TypeError):
        ProcessStopResult(
            success=1,
            worker_state=ProcessWorkerState.STOPPED,
        )


def test_process_configuration_result_accepts_valid_interval():
    result = ProcessConfigurationResult(
        accepted=True,
        sampling_interval=2,
        worker_state=ProcessWorkerState.RUNNING,
    )

    assert result.sampling_interval == 2.0


@pytest.mark.parametrize("interval", [0.49, 60.01, float("nan"), float("inf")])
def test_process_configuration_rejects_invalid_interval(interval):
    with pytest.raises(ValueError):
        ProcessConfigurationResult(
            accepted=True,
            sampling_interval=interval,
            worker_state=ProcessWorkerState.RUNNING,
        )


def test_process_configuration_rejects_boolean_interval():
    with pytest.raises(TypeError):
        ProcessConfigurationResult(
            accepted=True,
            sampling_interval=True,
            worker_state=ProcessWorkerState.RUNNING,
        )


def test_process_configuration_rejects_invalid_worker_state():
    with pytest.raises(TypeError):
        ProcessConfigurationResult(
            accepted=True,
            sampling_interval=2.0,
            worker_state="RUNNING",
        )


def test_process_operation_results_reject_invalid_error():
    with pytest.raises(TypeError):
        ProcessStartResult(
            accepted=False,
            worker_state=ProcessWorkerState.FAILED,
            error=object(),
        )

    with pytest.raises(TypeError):
        ProcessStopResult(
            success=False,
            worker_state=ProcessWorkerState.FAILED,
            error=object(),
        )

    with pytest.raises(TypeError):
        ProcessConfigurationResult(
            accepted=False,
            sampling_interval=2.0,
            worker_state=ProcessWorkerState.RUNNING,
            error=object(),
        )
