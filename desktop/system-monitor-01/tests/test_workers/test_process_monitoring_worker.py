from datetime import datetime, timezone
from types import SimpleNamespace
import threading

import psutil
import pytest

from system_monitor.workers.process_monitoring_worker import (
    ProcessMonitoringWorker,
    ProcessWorkerError,
)


def make_worker():
    measurements = []
    measurement_failures = []
    worker_failures = []

    worker = ProcessMonitoringWorker(
        sampling_interval=2.0,
        on_measurement=measurements.append,
        on_measurement_failure=lambda code, message: (
            measurement_failures.append((code, message))
        ),
        on_worker_failure=lambda: worker_failures.append(True),
    )

    return worker, measurements, measurement_failures, worker_failures


def make_process(
    pid=100,
    name="example.exe",
    rss=1024,
    status="running",
    create_time=1000.0,
    user_time=2.0,
    system_time=1.0,
):
    info = {
        "pid": pid,
        "name": name,
        "memory_info": SimpleNamespace(rss=rss),
        "status": status,
        "create_time": create_time,
        "cpu_times": SimpleNamespace(
            user=user_time,
            system=system_time,
        ),
    }

    return SimpleNamespace(pid=pid, info=info)


def patch_processes(monkeypatch, processes):
    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        lambda **kwargs: iter(processes),
    )


def patch_clock(monkeypatch, values):
    iterator = iter(values)

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.time.monotonic",
        lambda: next(iterator),
    )


def test_first_sample_establishes_cpu_baseline(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_processes(monkeypatch, [make_process()])
    patch_clock(monkeypatch, [10.0])

    snapshot = worker._collect_measurement(2.0)

    assert len(snapshot.processes) == 1

    process = snapshot.processes[0]

    assert process.pid == 100
    assert process.name == "example.exe"
    assert process.cpu_percent is None
    assert process.memory_bytes == 1024
    assert process.status == "running"
    assert snapshot.is_fully_successful


def test_second_sample_calculates_cpu_percentage(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            [make_process(user_time=2.0, system_time=1.0)],
            [make_process(user_time=3.0, system_time=1.5)],
        ]
    )

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        lambda **kwargs: iter(next(samples)),
    )

    patch_clock(monkeypatch, [10.0, 12.0])

    worker._collect_measurement(2.0)
    snapshot = worker._collect_measurement(2.0)

    assert snapshot.processes[0].cpu_percent == 75.0


@pytest.mark.parametrize(
    ("exception", "error_code"),
    [
        (psutil.AccessDenied(pid=200), "PROCESS_ACCESS_DENIED"),
        (psutil.NoSuchProcess(pid=200), "PROCESS_DISAPPEARED"),
        (psutil.ZombieProcess(pid=200), "PROCESS_ZOMBIE"),
    ],
)
def test_individual_process_errors_do_not_abort_scan(
    monkeypatch,
    exception,
    error_code,
):
    worker, _, _, _ = make_worker()

    inaccessible = SimpleNamespace(
        pid=200,
        info=property(lambda self: None),
    )

    class FailingProcess:
        pid = 200

        @property
        def info(self):
            raise exception

    patch_processes(
        monkeypatch,
        [FailingProcess(), make_process(pid=300)],
    )
    patch_clock(monkeypatch, [10.0])

    snapshot = worker._collect_measurement(2.0)

    assert [process.pid for process in snapshot.processes] == [300]
    assert len(snapshot.process_errors) == 1
    assert snapshot.process_errors[0].pid == 200
    assert snapshot.process_errors[0].error_code == error_code
    assert snapshot.is_partial


def test_invalid_process_data_does_not_abort_scan(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_processes(
        monkeypatch,
        [
            make_process(pid=200, rss=-1),
            make_process(pid=300),
        ],
    )
    patch_clock(monkeypatch, [10.0])

    snapshot = worker._collect_measurement(2.0)

    assert [process.pid for process in snapshot.processes] == [300]
    assert snapshot.process_errors[0].error_code == "PROCESS_INVALID_DATA"


def test_empty_process_list_is_successful(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_processes(monkeypatch, [])
    patch_clock(monkeypatch, [10.0])

    snapshot = worker._collect_measurement(2.0)

    assert snapshot.is_empty
    assert snapshot.is_fully_successful


def test_collection_provider_failure_raises_worker_error(monkeypatch):
    worker, _, _, _ = make_worker()

    def fail(**kwargs):
        raise psutil.AccessDenied()

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        fail,
    )

    with pytest.raises(ProcessWorkerError) as error:
        worker._collect_measurement(2.0)

    assert error.value.error_code == "PROCESS_PROVIDER_FAILED"


def test_process_creation_time_change_resets_cpu_baseline(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            [make_process(create_time=1000.0)],
            [make_process(create_time=2000.0)],
        ]
    )

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        lambda **kwargs: iter(next(samples)),
    )

    patch_clock(monkeypatch, [10.0, 12.0])

    worker._collect_measurement(2.0)
    snapshot = worker._collect_measurement(2.0)

    assert snapshot.processes[0].cpu_percent is None


def test_missing_cpu_times_produces_unavailable_cpu(monkeypatch):
    worker, _, _, _ = make_worker()

    process = make_process()
    process.info["cpu_times"] = None

    patch_processes(monkeypatch, [process])
    patch_clock(monkeypatch, [10.0])

    snapshot = worker._collect_measurement(2.0)

    assert snapshot.processes[0].cpu_percent is None


@pytest.mark.parametrize("interval", [0.0, 0.49, 60.01, float("nan"), float("inf")])
def test_invalid_sampling_interval_is_rejected(interval):
    worker, _, _, _ = make_worker()

    with pytest.raises(ValueError):
        worker.set_sampling_interval(interval)


def test_boolean_sampling_interval_is_rejected():
    worker, _, _, _ = make_worker()

    with pytest.raises(TypeError):
        worker.set_sampling_interval(True)


def test_valid_sampling_interval_is_accepted():
    worker, _, _, _ = make_worker()

    worker.set_sampling_interval(5.0)

    assert worker.sampling_interval == 5.0
    assert worker._reconfigure_event.is_set()


def test_stop_sets_stop_event():
    worker, _, _, _ = make_worker()

    worker.stop()

    assert worker._stop_event.is_set()


def test_worker_stops_without_collecting_after_stop(monkeypatch):
    worker, measurements, _, _ = make_worker()

    worker.stop()

    monkeypatch.setattr(
        worker,
        "_collect_measurement",
        lambda interval: pytest.fail("Collection should not run."),
    )

    worker.run()

    assert measurements == []


def test_measurement_callback_exception_does_not_escape():
    worker, _, _, _ = make_worker()

    worker._on_measurement = lambda snapshot: (
        (_ for _ in ()).throw(RuntimeError("callback failure"))
    )

    worker._deliver_measurement(None)


def test_failure_callback_exception_does_not_escape():
    worker, _, _, _ = make_worker()

    worker._on_measurement_failure = lambda code, message: (
        (_ for _ in ()).throw(RuntimeError("callback failure"))
    )

    worker._report_measurement_failure("TEST", "Test failure")


def test_worker_failure_callback_exception_does_not_escape():
    worker, _, _, _ = make_worker()

    worker._on_worker_failure = lambda: (
        (_ for _ in ()).throw(RuntimeError("callback failure"))
    )

    worker._safe_callback(worker._on_worker_failure)


def test_cpu_baseline_is_removed_when_process_disappears(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_processes(monkeypatch, [make_process()])
    patch_clock(monkeypatch, [10.0])

    worker._collect_measurement(2.0)

    assert len(worker._cpu_baselines) == 1

    patch_processes(monkeypatch, [])
    patch_clock(monkeypatch, [12.0])

    worker._collect_measurement(2.0)

    assert worker._cpu_baselines == {}


def test_worker_constructor_rejects_non_callable_callbacks():
    with pytest.raises(TypeError):
        ProcessMonitoringWorker(
            sampling_interval=2.0,
            on_measurement=None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
        )


def test_access_denied_sentinel_does_not_abort_scan(monkeypatch):
    worker, _, _, _ = make_worker()

    class FakeProcess:
        def __init__(self, pid, info):
            self.pid = pid
            self.info = info

    def fake_process_iter(**kwargs):
        assert kwargs["ad_value"] is not None

        inaccessible_info = make_process(pid=200).info.copy()
        inaccessible_info["memory_info"] = kwargs["ad_value"]

        return iter([
            FakeProcess(200, inaccessible_info),
            make_process(pid=300),
        ])

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        fake_process_iter,
    )
    patch_clock(monkeypatch, [10.0])

    snapshot = worker._collect_measurement(2.0)

    assert [process.pid for process in snapshot.processes] == [300]
    assert len(snapshot.process_errors) == 1
    assert snapshot.process_errors[0].pid == 200
    assert snapshot.process_errors[0].error_code == "PROCESS_ACCESS_DENIED"
    assert snapshot.is_partial
