import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from system_monitor.workers.memory_monitoring_worker import (
    MemoryMonitoringWorker,
    MemoryWorkerError,
    _WaitResult,
)


def make_worker(
    interval=1.0,
    on_measurement=None,
    on_measurement_failure=None,
    on_worker_failure=None,
    on_started=None,
):
    measurements = []
    failures = []
    worker_failures = []

    worker = MemoryMonitoringWorker(
        session_id=uuid4(),
        sampling_interval=interval,
        on_measurement=on_measurement or measurements.append,
        on_measurement_failure=on_measurement_failure
        or (lambda code, message: failures.append((code, message))),
        on_worker_failure=on_worker_failure
        or (lambda: worker_failures.append(True)),
        on_started=on_started,
    )

    return worker, measurements, failures, worker_failures


def make_virtual_memory(
    total=16000,
    used=8000,
    available=7000,
    free=6000,
    percent=50.0,
):
    return SimpleNamespace(
        total=total,
        used=used,
        available=available,
        free=free,
        percent=percent,
    )


def make_swap_memory(
    total=8000,
    used=2000,
    free=6000,
    percent=25.0,
):
    return SimpleNamespace(
        total=total,
        used=used,
        free=free,
        percent=percent,
    )


def patch_memory(
    monkeypatch,
    virtual_memory=None,
    swap_memory=None,
):
    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.virtual_memory",
        lambda: virtual_memory or make_virtual_memory(),
    )
    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.swap_memory",
        lambda: swap_memory or make_swap_memory(),
    )


@pytest.mark.parametrize(
    "value",
    [0, -1, 0.49, 60.01, True, float("nan"), float("inf"), float("-inf")],
)
def test_worker_rejects_invalid_sampling_interval(value):
    with pytest.raises((TypeError, ValueError)):
        make_worker(interval=value)


def test_worker_accepts_valid_sampling_interval():
    worker, *_ = make_worker(interval=0.5)

    assert worker.sampling_interval == 0.5


def test_worker_accepts_maximum_sampling_interval():
    worker, *_ = make_worker(interval=60.0)

    assert worker.sampling_interval == 60.0


def test_worker_can_update_sampling_interval():
    worker, *_ = make_worker()

    worker.set_sampling_interval(2.0)

    assert worker.sampling_interval == 2.0
    assert worker.reconfigure_event.is_set()


def test_worker_requires_uuid_session_id():
    with pytest.raises(TypeError):
        MemoryMonitoringWorker(
            session_id="not-a-uuid",
            sampling_interval=1.0,
            on_measurement=lambda value: None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
        )


def test_worker_requires_callable_callbacks():
    with pytest.raises(TypeError):
        MemoryMonitoringWorker(
            session_id=uuid4(),
            sampling_interval=1.0,
            on_measurement=None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
        )


def test_worker_rejects_invalid_startup_callback():
    with pytest.raises(TypeError):
        MemoryMonitoringWorker(
            session_id=uuid4(),
            sampling_interval=1.0,
            on_measurement=lambda value: None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
            on_started="not-callable",
        )


def test_worker_collects_ram_and_swap_together(monkeypatch):
    worker, *_ = make_worker()
    calls = []

    def fake_virtual_memory():
        calls.append("ram")
        return make_virtual_memory()

    def fake_swap_memory():
        calls.append("swap")
        return make_swap_memory()

    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.virtual_memory",
        fake_virtual_memory,
    )
    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.swap_memory",
        fake_swap_memory,
    )

    measurement = worker._collect_measurement(1.0)

    assert calls == ["ram", "swap"]
    assert measurement.total_bytes == 16000
    assert measurement.used_bytes == 8000
    assert measurement.available_bytes == 7000
    assert measurement.free_bytes == 6000
    assert measurement.percent == 50.0
    assert measurement.swap_total_bytes == 8000
    assert measurement.swap_used_bytes == 2000
    assert measurement.swap_free_bytes == 6000
    assert measurement.swap_percent == 25.0
    assert measurement.sampling_interval == 1.0


def test_worker_preserves_available_and_free_distinction(monkeypatch):
    worker, *_ = make_worker()
    patch_memory(
        monkeypatch,
        virtual_memory=make_virtual_memory(
            available=9000,
            free=3000,
        ),
    )

    measurement = worker._collect_measurement(1.0)

    assert measurement.available_bytes == 9000
    assert measurement.free_bytes == 3000


def test_worker_accepts_zero_sized_swap(monkeypatch):
    worker, *_ = make_worker()
    patch_memory(
        monkeypatch,
        swap_memory=make_swap_memory(
            total=0,
            used=0,
            free=0,
            percent=0.0,
        ),
    )

    measurement = worker._collect_measurement(1.0)

    assert measurement.swap_total_bytes == 0
    assert measurement.swap_used_bytes == 0
    assert measurement.swap_free_bytes == 0
    assert measurement.swap_percent == 0.0


@pytest.mark.parametrize(
    "swap",
    [
        make_swap_memory(total=0, used=1, free=0, percent=0.0),
        make_swap_memory(total=0, used=0, free=0, percent=1.0),
        make_swap_memory(total=8000, used=9000, free=0, percent=25.0),
        make_swap_memory(total=8000, used=0, free=9000, percent=25.0),
    ],
)
def test_worker_rejects_invalid_swap_readings(monkeypatch, swap):
    worker, *_ = make_worker()
    patch_memory(monkeypatch, swap_memory=swap)

    with pytest.raises(MemoryWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "MEMORY_INVALID_READING"


@pytest.mark.parametrize(
    "ram",
    [
        make_virtual_memory(total=0),
        make_virtual_memory(used=-1),
        make_virtual_memory(available=-1),
        make_virtual_memory(free=-1),
        make_virtual_memory(used=17000),
        make_virtual_memory(available=17000),
        make_virtual_memory(free=17000),
    ],
)
def test_worker_rejects_invalid_ram_byte_readings(monkeypatch, ram):
    worker, *_ = make_worker()
    patch_memory(monkeypatch, virtual_memory=ram)

    with pytest.raises(MemoryWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "MEMORY_INVALID_READING"


@pytest.mark.parametrize(
    "field",
    ["total", "used", "available", "free"],
)
@pytest.mark.parametrize(
    "value",
    [True, 1.5, "100", None],
)
def test_worker_rejects_non_integer_ram_readings(monkeypatch, field, value):
    worker, *_ = make_worker()
    ram = make_virtual_memory()
    setattr(ram, field, value)
    patch_memory(monkeypatch, virtual_memory=ram)

    with pytest.raises(MemoryWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "MEMORY_INVALID_READING"


@pytest.mark.parametrize(
    "field",
    ["total", "used", "free"],
)
@pytest.mark.parametrize(
    "value",
    [True, 1.5, "100", None],
)
def test_worker_rejects_non_integer_swap_readings(monkeypatch, field, value):
    worker, *_ = make_worker()
    swap = make_swap_memory()
    setattr(swap, field, value)
    patch_memory(monkeypatch, swap_memory=swap)

    with pytest.raises(MemoryWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "MEMORY_INVALID_READING"


@pytest.mark.parametrize(
    "field",
    ["percent", "swap_percent"],
)
@pytest.mark.parametrize(
    "value",
    [True, "50", None, -1.0, 101.0, float("nan"), float("inf")],
)
def test_worker_rejects_invalid_percentages(monkeypatch, field, value):
    worker, *_ = make_worker()
    ram = make_virtual_memory()
    swap = make_swap_memory()

    if field == "percent":
        ram.percent = value
    else:
        swap.percent = value

    patch_memory(monkeypatch, ram, swap)

    with pytest.raises(MemoryWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "MEMORY_INVALID_READING"


def test_worker_rejects_ram_collection_failure(monkeypatch):
    worker, *_ = make_worker()

    def fail():
        raise OSError("RAM unavailable")

    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.virtual_memory",
        fail,
    )

    with pytest.raises(MemoryWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "MEMORY_MEASUREMENT_FAILED"


def test_worker_rejects_swap_collection_failure(monkeypatch):
    worker, *_ = make_worker()

    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.virtual_memory",
        make_virtual_memory,
    )

    def fail():
        raise RuntimeError("Swap unavailable")

    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.swap_memory",
        fail,
    )

    with pytest.raises(MemoryWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "MEMORY_MEASUREMENT_FAILED"


def test_worker_does_not_publish_partial_measurement(monkeypatch):
    worker, measurements, *_ = make_worker()

    patch_memory(monkeypatch)

    monkeypatch.setattr(
        "system_monitor.workers.memory_monitoring_worker.psutil.swap_memory",
        lambda: (_ for _ in ()).throw(OSError("Swap unavailable")),
    )

    with pytest.raises(MemoryWorkerError):
        measurement = worker._collect_measurement(1.0)
        measurements.append(measurement)

    assert measurements == []


def test_worker_measurement_timestamps_are_utc(monkeypatch):
    worker, *_ = make_worker()
    patch_memory(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert measurement.started_at.tzinfo == timezone.utc
    assert measurement.completed_at.tzinfo == timezone.utc
    assert measurement.completed_at >= measurement.started_at
    assert isinstance(measurement.started_at, datetime)


def test_worker_measurement_is_immutable(monkeypatch):
    worker, *_ = make_worker()
    patch_memory(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    with pytest.raises(AttributeError):
        measurement.total_bytes = 100


def test_stop_event_interrupts_wait():
    worker, *_ = make_worker()

    worker.stop_event.set()

    assert worker._wait_for_next_window(10.0) == _WaitResult.STOP


def test_reconfiguration_event_interrupts_wait():
    worker, *_ = make_worker()

    worker.reconfigure_event.set()

    assert worker._wait_for_next_window(10.0) == _WaitResult.RECONFIGURE


def test_stop_takes_priority_over_reconfiguration():
    worker, *_ = make_worker()

    worker.stop_event.set()
    worker.reconfigure_event.set()

    assert worker._wait_for_next_window(10.0) == _WaitResult.STOP


def test_measurement_callback_failure_does_not_crash_worker():
    worker, _, _, worker_failures = make_worker(
        on_measurement=lambda measurement: (_ for _ in ()).throw(
            RuntimeError("subscriber failed")
        )
    )

    worker._deliver_measurement(object())

    assert worker_failures == []


def test_measurement_failure_callback_failure_is_isolated():
    worker, *_ = make_worker(
        on_measurement_failure=lambda code, message: (_ for _ in ()).throw(
            RuntimeError("subscriber failed")
        )
    )

    worker._report_measurement_failure(
        "MEMORY_MEASUREMENT_FAILED",
        "Memory measurement failed.",
    )


def test_worker_failure_callback_failure_is_isolated():
    worker, *_ = make_worker(
        on_worker_failure=lambda: (_ for _ in ()).throw(
            RuntimeError("callback failed")
        )
    )

    def fail_worker():
        raise RuntimeError("unexpected worker failure")

    worker._run_loop = fail_worker

    worker.run()


def test_worker_does_not_start_when_already_stopped():
    worker, *_ = make_worker()
    worker.stop_event.set()

    started = []
    worker._on_started = lambda: started.append(True)

    worker._run_loop()

    assert started == []
    assert worker._started is False


def test_worker_startup_callback_runs_once(monkeypatch):
    started = []
    worker, *_ = make_worker(on_started=lambda: started.append(True))

    def stop_after_start(interval):
        worker.stop_event.set()
        return _WaitResult.STOP

    monkeypatch.setattr(worker, "_wait_for_next_window", stop_after_start)

    worker._run_loop()

    assert started == [True]
    assert worker._started is True


def test_reconfiguration_is_consumed():
    worker, *_ = make_worker()
    worker.reconfigure_event.set()

    worker._consume_reconfiguration()

    assert not worker.reconfigure_event.is_set()

def test_worker_recovers_after_failed_measurement(monkeypatch):
    worker, measurements, failures, worker_failures = make_worker()

    wait_results = iter([
        _WaitResult.TIMEOUT,
        _WaitResult.TIMEOUT,
        _WaitResult.STOP,
    ])

    monkeypatch.setattr(
        worker,
        "_wait_for_next_window",
        lambda interval: next(wait_results),
    )

    collection_calls = []

    def collect(interval):
        collection_calls.append(interval)

        if len(collection_calls) == 1:
            raise MemoryWorkerError(
                "MEMORY_MEASUREMENT_FAILED",
                "Temporary collection failure.",
            )

        return object()

    monkeypatch.setattr(worker, "_collect_measurement", collect)

    worker._run_loop()

    assert collection_calls == [1.0, 1.0]
    assert len(failures) == 1
    assert failures[0][0] == "MEMORY_MEASUREMENT_FAILED"
    assert len(measurements) == 1
    assert worker_failures == []


def test_reconfiguration_updates_interval_during_worker_loop(monkeypatch):
    worker, *_ = make_worker()

    wait_intervals = []

    def fake_wait(interval):
        wait_intervals.append(interval)

        if len(wait_intervals) == 1:
            worker.set_sampling_interval(2.0)
            return _WaitResult.RECONFIGURE

        return _WaitResult.STOP

    monkeypatch.setattr(worker, "_wait_for_next_window", fake_wait)

    worker._run_loop()

    assert wait_intervals == [1.0, 2.0]
    assert worker.sampling_interval == 2.0
    assert not worker.reconfigure_event.is_set()


def test_worker_does_not_deliver_measurement_after_stop_during_collection(
    monkeypatch,
):
    worker, measurements, *_ = make_worker()

    monkeypatch.setattr(
        worker,
        "_wait_for_next_window",
        lambda interval: _WaitResult.TIMEOUT,
    )

    def collect(interval):
        worker.stop_event.set()
        return object()

    monkeypatch.setattr(worker, "_collect_measurement", collect)

    worker._run_loop()

    assert measurements == []
    assert worker.stop_event.is_set()
