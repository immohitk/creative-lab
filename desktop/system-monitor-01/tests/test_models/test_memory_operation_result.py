import pytest

from system_monitor.models import (
    MemoryConfigurationResult,
    MemoryError,
    MemoryStartResult,
    MemoryStopResult,
    MemoryWorkerState,
)


def make_error():
    from datetime import datetime, timezone

    return MemoryError(
        error_code="MEMORY_OPERATION_FAILED",
        message="Memory operation failed.",
        occurred_at=datetime.now(timezone.utc),
        consecutive_failures=1,
    )


def test_valid_start_result():
    result = MemoryStartResult(
        accepted=True,
        worker_state=MemoryWorkerState.STARTING,
    )

    assert result.accepted is True
    assert result.worker_state == MemoryWorkerState.STARTING
    assert result.error is None


def test_valid_stop_result():
    result = MemoryStopResult(
        success=True,
        worker_state=MemoryWorkerState.STOPPED,
    )

    assert result.success is True
    assert result.worker_state == MemoryWorkerState.STOPPED


def test_valid_configuration_result():
    result = MemoryConfigurationResult(
        accepted=True,
        sampling_interval=2,
        worker_state=MemoryWorkerState.RUNNING,
    )

    assert result.accepted is True
    assert result.sampling_interval == 2.0


@pytest.mark.parametrize("value", [1, "true", None])
def test_start_result_requires_boolean(value):
    with pytest.raises(TypeError):
        MemoryStartResult(
            accepted=value,
            worker_state=MemoryWorkerState.STOPPED,
        )


@pytest.mark.parametrize("value", [1, "true", None])
def test_stop_result_requires_boolean(value):
    with pytest.raises(TypeError):
        MemoryStopResult(
            success=value,
            worker_state=MemoryWorkerState.STOPPED,
        )


@pytest.mark.parametrize("value", [1, "true", None])
def test_configuration_result_requires_boolean(value):
    with pytest.raises(TypeError):
        MemoryConfigurationResult(
            accepted=value,
            sampling_interval=1.0,
            worker_state=MemoryWorkerState.STOPPED,
        )


def test_operation_results_reject_invalid_worker_state():
    with pytest.raises(TypeError):
        MemoryStartResult(True, "RUNNING")

    with pytest.raises(TypeError):
        MemoryStopResult(True, "STOPPED")

    with pytest.raises(TypeError):
        MemoryConfigurationResult(True, 1.0, "RUNNING")


@pytest.mark.parametrize(
    "interval",
    [0, -1, 0.49, 60.01, True, float("nan"), float("inf"), "1"],
)
def test_configuration_result_rejects_invalid_interval(interval):
    with pytest.raises((TypeError, ValueError)):
        MemoryConfigurationResult(
            accepted=True,
            sampling_interval=interval,
            worker_state=MemoryWorkerState.RUNNING,
        )


def test_configuration_result_normalizes_interval_to_float():
    result = MemoryConfigurationResult(
        accepted=True,
        sampling_interval=2,
        worker_state=MemoryWorkerState.RUNNING,
    )

    assert result.sampling_interval == 2.0
    assert isinstance(result.sampling_interval, float)


def test_operation_results_preserve_memory_error():
    error = make_error()

    start = MemoryStartResult(
        accepted=False,
        worker_state=MemoryWorkerState.FAILED,
        error=error,
    )
    stop = MemoryStopResult(
        success=False,
        worker_state=MemoryWorkerState.FAILED,
        error=error,
    )
    configuration = MemoryConfigurationResult(
        accepted=False,
        sampling_interval=1.0,
        worker_state=MemoryWorkerState.FAILED,
        error=error,
    )

    assert start.error is error
    assert stop.error is error
    assert configuration.error is error


def test_operation_results_reject_invalid_error():
    with pytest.raises(TypeError):
        MemoryStartResult(True, MemoryWorkerState.RUNNING, error="error")

    with pytest.raises(TypeError):
        MemoryStopResult(True, MemoryWorkerState.STOPPED, error="error")

    with pytest.raises(TypeError):
        MemoryConfigurationResult(
            True, 1.0, MemoryWorkerState.RUNNING, error="error"
        )
