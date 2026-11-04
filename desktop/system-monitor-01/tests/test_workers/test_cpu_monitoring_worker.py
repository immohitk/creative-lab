
import threading
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from system_monitor.workers.cpu_monitoring_worker import (
    CpuMonitoringWorker,
    CpuWorkerError,
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

    worker = CpuMonitoringWorker(
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


def test_worker_can_update_sampling_interval():
    worker, *_ = make_worker()

    worker.set_sampling_interval(2.0)

    assert worker.sampling_interval == 2.0
    assert worker.reconfigure_event.is_set()


def test_worker_requires_uuid_session_id():
    with pytest.raises(TypeError):
        CpuMonitoringWorker(
            session_id="not-a-uuid",
            sampling_interval=1.0,
            on_measurement=lambda value: None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
        )


def test_worker_primes_only_per_core_counters(monkeypatch):
    worker, *_ = make_worker()
    worker._logical_cpu_count = 2

    calls = []

    def fake_cpu_percent(interval=None, percpu=False):
        calls.append((interval, percpu))
        return [0.0, 0.0]

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_percent",
        fake_cpu_percent,
    )

    worker._prime_counters()

    assert calls == [(None, True)]


def test_worker_rejects_missing_per_core_counters(monkeypatch):
    worker, *_ = make_worker()
    worker._logical_cpu_count = 2

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_percent",
        lambda interval=None, percpu=False: [],
    )

    with pytest.raises(CpuWorkerError) as error:
        worker._prime_counters()

    assert error.value.error_code == "CPU_PER_CORE_UNAVAILABLE"


def test_worker_rejects_logical_cpu_count_mismatch(monkeypatch):
    worker, *_ = make_worker()
    worker._logical_cpu_count = 2

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_percent",
        lambda interval=None, percpu=False: [0.0],
    )

    with pytest.raises(CpuWorkerError) as error:
        worker._prime_counters()

    assert error.value.error_code == "CPU_PER_CORE_UNAVAILABLE"


def test_worker_collects_immutable_cpu_measurement(monkeypatch):
    worker, *_ = make_worker()
    worker._logical_cpu_count = 2

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_count",
        lambda logical=True: 2,
    )

    calls = []

    def fake_cpu_percent(interval=None, percpu=False):
        calls.append((interval, percpu))
        return [40.0, 60.0]

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_percent",
        fake_cpu_percent,
    )

    measurement = worker._collect_measurement(1.0)

    assert calls == [(None, True)]
    assert measurement.overall_percent == 50.0
    assert measurement.per_cpu_percent == (40.0, 60.0)
    assert measurement.logical_cpu_count == 2
    assert measurement.sampling_interval == 1.0
    assert isinstance(measurement.per_cpu_percent, tuple)

    with pytest.raises(AttributeError):
        measurement.overall_percent = 90.0


@pytest.mark.parametrize(
    "readings",
    [
        [True, 50.0],
        ["50", 50.0],
        [None, 50.0],
        [complex(1, 2), 50.0],
        [float("nan"), 50.0],
        [float("inf"), 50.0],
        [-1.0, 50.0],
        [101.0, 50.0],
        [50.0],
    ],
)
def test_worker_rejects_invalid_per_core_readings(monkeypatch, readings):
    worker, *_ = make_worker()
    worker._logical_cpu_count = 2

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_count",
        lambda logical=True: 2,
    )

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_percent",
        lambda interval=None, percpu=False: readings,
    )

    with pytest.raises(CpuWorkerError):
        worker._collect_measurement(1.0)


def test_worker_detects_topology_change(monkeypatch):
    worker, *_ = make_worker()
    worker._logical_cpu_count = 2

    counts = iter([2, 4])

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_count",
        lambda logical=True: next(counts),
    )

    with pytest.raises(CpuWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "CPU_TOPOLOGY_CHANGED"
    assert worker._logical_cpu_count == 4


@pytest.mark.parametrize("count", [None, 0, -1, True, 2.5])
def test_worker_rejects_unavailable_logical_cpu_count(monkeypatch, count):
    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_count",
        lambda logical=True: count,
    )

    with pytest.raises(CpuWorkerError) as error:
        CpuMonitoringWorker._get_logical_cpu_count()

    assert error.value.error_code == "CPU_PER_CORE_UNAVAILABLE"


def test_stop_event_interrupts_wait():
    worker, *_ = make_worker()

    worker.stop_event.set()

    assert worker._wait_for_next_window(10.0) == _WaitResult.STOP


def test_reconfiguration_event_interrupts_wait():
    worker, *_ = make_worker()

    worker.reconfigure_event.set()

    assert (
        worker._wait_for_next_window(10.0)
        == _WaitResult.RECONFIGURE
    )


def test_stop_takes_priority_over_reconfiguration():
    worker, *_ = make_worker()

    worker.stop_event.set()
    worker.reconfigure_event.set()

    assert worker._wait_for_next_window(10.0) == _WaitResult.STOP


def test_worker_measurement_timestamps_are_utc(monkeypatch):
    worker, *_ = make_worker()
    worker._logical_cpu_count = 2

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_count",
        lambda logical=True: 2,
    )

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_percent",
        lambda interval=None, percpu=False: [40.0, 60.0],
    )

    measurement = worker._collect_measurement(1.0)

    assert measurement.started_at.tzinfo == timezone.utc
    assert measurement.completed_at.tzinfo == timezone.utc
    assert measurement.completed_at >= measurement.started_at
    assert isinstance(measurement.started_at, datetime)


def test_worker_recovers_counter_initialization_after_failure(monkeypatch):
    worker, _, failures, _ = make_worker()
    worker._logical_cpu_count = 2

    calls = iter([
        RuntimeError("temporary failure"),
        [0.0, 0.0],
    ])

    def fake_cpu_percent(interval=None, percpu=False):
        value = next(calls)

        if isinstance(value, Exception):
            raise value

        return value

    monkeypatch.setattr(
        "system_monitor.workers.cpu_monitoring_worker.psutil.cpu_percent",
        fake_cpu_percent,
    )

    wait_calls = []

    def fake_wait(interval):
        wait_calls.append(interval)
        worker.stop_event.set()
        return _WaitResult.STOP

    monkeypatch.setattr(worker, "_wait_for_next_window", fake_wait)

    worker._recover_counter_initialization()

    assert len(failures) == 1
    assert failures[0][0] == "CPU_MEASUREMENT_FAILED"
    assert wait_calls == [1.0]


def test_worker_measurement_callback_failure_does_not_crash_worker():
    worker, _, _, worker_failures = make_worker(
        on_measurement=lambda measurement: (_ for _ in ()).throw(
            RuntimeError("subscriber failed")
        )
    )

    worker._deliver_measurement(object())

    assert worker_failures == []


def test_worker_failure_callback_failure_is_isolated():
    worker, _, _, _ = make_worker(
        on_worker_failure=lambda: (_ for _ in ()).throw(
            RuntimeError("callback failed")
        )
    )

    def fail_worker():
        raise RuntimeError("unexpected worker failure")

    worker._run_loop = fail_worker

    # run() must isolate exceptions from the failure callback.
    worker.run()


def test_reconfiguration_interrupts_counter_recovery(monkeypatch):
    worker, _, failures, _ = make_worker(interval=1.0)

    monkeypatch.setattr(
        worker,
        "_get_logical_cpu_count",
        lambda: 2,
    )

    prime_calls = []

    def fake_prime_counters():
        prime_calls.append(worker.sampling_interval)

        if len(prime_calls) == 1:
            raise RuntimeError("temporary initialization failure")

    monkeypatch.setattr(
        worker,
        "_prime_counters",
        fake_prime_counters,
    )

    wait_calls = []

    def fake_wait(interval):
        wait_calls.append(interval)
        worker.set_sampling_interval(2.0)
        return _WaitResult.RECONFIGURE

    monkeypatch.setattr(
        worker,
        "_wait_for_next_window",
        fake_wait,
    )

    worker._recover_counter_initialization()

    assert len(failures) == 1
    assert failures[0][0] == "CPU_MEASUREMENT_FAILED"
    assert wait_calls == [1.0]
    assert prime_calls == [1.0, 2.0]
    assert worker.sampling_interval == 2.0
    assert not worker.reconfigure_event.is_set()
