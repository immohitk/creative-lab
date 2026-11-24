from datetime import datetime, timezone
from types import SimpleNamespace
import threading

import psutil
import pytest

from system_monitor.workers.process_monitoring_worker import (
    _WaitResult,
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
    worker._run_loop = lambda: (_ for _ in ()).throw(
        RuntimeError("unexpected worker failure")
    )

    worker.run()


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

def test_unexpected_run_loop_failure_reports_worker_failure_once_and_terminates():
    worker, _, _, worker_failures = make_worker()

    def fail_worker():
        raise RuntimeError("unexpected worker failure")

    worker._run_loop = fail_worker
    thread = threading.Thread(target=worker.run)
    thread.start()
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert worker_failures == [True]


def test_startup_callback_failure_reports_worker_failure(monkeypatch):
    worker, _, _, worker_failures = make_worker()
    worker._on_started = lambda: (_ for _ in ()).throw(
        RuntimeError("startup callback failed")
    )
    monkeypatch.setattr(
        worker, "_wait_for_next_window", lambda interval: _WaitResult.STOP
    )

    worker.run()

    assert worker_failures == [True]

def test_worker_recovers_after_measurement_failure(monkeypatch):
    worker, measurements, measurement_failures, worker_failures = make_worker()

    successful_snapshot = object()
    wait_results = iter([
        _WaitResult.TIMEOUT,
        _WaitResult.TIMEOUT,
        _WaitResult.STOP,
    ])

    collection_calls = []

    def collect_measurement(interval):
        collection_calls.append(interval)

        if len(collection_calls) == 1:
            raise ProcessWorkerError(
                "PROCESS_PROVIDER_FAILED",
                "Process provider temporarily unavailable.",
            )

        return successful_snapshot

    monkeypatch.setattr(
        worker,
        "_wait_for_next_window",
        lambda interval: next(wait_results),
    )
    monkeypatch.setattr(
        worker,
        "_collect_measurement",
        collect_measurement,
    )

    worker.run()

    assert collection_calls == [2.0, 2.0]
    assert measurement_failures == [
        (
            "PROCESS_PROVIDER_FAILED",
            "Process provider temporarily unavailable.",
        )
    ]
    assert measurements == [successful_snapshot]
    assert worker_failures == []


def make_service(pid, name):
    return SimpleNamespace(
        as_dict=lambda: {"pid": pid, "name": name}
    )


def test_service_map_is_unavailable_without_windows_api(monkeypatch):
    worker, _, _, _ = make_worker()

    monkeypatch.delattr(psutil, "win_service_iter", raising=False)

    service_map, available = worker._collect_service_map()

    assert service_map == {}
    assert available is False


def test_service_map_groups_deduplicates_and_sorts_names(monkeypatch):
    worker, _, _, _ = make_worker()

    services = [
        make_service(100, "Zulu"),
        make_service(100, "alpha"),
        make_service(100, "alpha"),
        make_service(200, "Beta"),
    ]

    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        lambda: iter(services),
        raising=False,
    )

    service_map, available = worker._collect_service_map()

    assert service_map == {
        100: ("alpha", "Zulu"),
        200: ("Beta",),
    }
    assert available is True


def test_service_map_ignores_invalid_service_metadata(monkeypatch):
    worker, _, _, _ = make_worker()

    services = [
        make_service(100, "Valid"),
        make_service(0, "Invalid PID"),
        make_service(True, "Boolean PID"),
        make_service(200, ""),
        make_service(300, None),
    ]

    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        lambda: iter(services),
        raising=False,
    )

    service_map, available = worker._collect_service_map()

    assert service_map == {100: ("Valid",)}
    assert available is True


def test_service_map_continues_after_individual_service_failure(monkeypatch):
    worker, _, _, _ = make_worker()

    class FailingService:
        def as_dict(self):
            raise OSError("service unavailable")

    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        lambda: iter([
            make_service(100, "First"),
            FailingService(),
            make_service(200, "Second"),
        ]),
        raising=False,
    )

    service_map, available = worker._collect_service_map()

    assert service_map == {
        100: ("First",),
        200: ("Second",),
    }
    assert available is False


def test_service_map_preserves_partial_results_on_iterator_failure(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    def failing_iterator():
        yield make_service(100, "First")
        raise OSError("enumeration failed")

    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        failing_iterator,
        raising=False,
    )

    service_map, available = worker._collect_service_map()

    assert service_map == {100: ("First",)}
    assert available is False


def test_service_map_stops_during_enumeration(monkeypatch):
    worker, _, _, _ = make_worker()

    def service_iterator():
        yield make_service(100, "First")
        worker._stop_event.set()
        yield make_service(200, "Second")

    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        service_iterator,
        raising=False,
    )

    service_map, available = worker._collect_service_map()

    assert service_map == {100: ("First",)}
    assert available is False


def test_service_map_returns_unavailable_when_already_stopped(monkeypatch):
    worker, _, _, _ = make_worker()

    worker.stop()

    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        lambda: pytest.fail("Service enumeration should not start."),
        raising=False,
    )

    service_map, available = worker._collect_service_map()

    assert service_map == {}
    assert available is False


def test_process_metadata_state_is_verified_when_collection_is_complete(
    monkeypatch,
):
    worker, _, _, _ = make_worker()
    process = make_process()
    process.info["exe"] = r"C:\Windows\example.exe"

    patch_processes(monkeypatch, [process])
    patch_clock(monkeypatch, [10.0])
    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        lambda: iter([]),
        raising=False,
    )

    snapshot = worker._collect_measurement(2.0)

    assert snapshot.processes[0].metadata_state == "verified"


def test_process_metadata_state_is_partial_when_service_collection_is_unavailable(
    monkeypatch,
):
    worker, _, _, _ = make_worker()
    process = make_process()
    process.info["exe"] = r"C:\Windows\example.exe"

    patch_processes(monkeypatch, [process])
    patch_clock(monkeypatch, [10.0])
    monkeypatch.delattr(psutil, "win_service_iter", raising=False)

    snapshot = worker._collect_measurement(2.0)

    assert snapshot.processes[0].metadata_state == "partial"


def test_process_metadata_state_is_unavailable_without_metadata(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    patch_processes(monkeypatch, [make_process()])
    patch_clock(monkeypatch, [10.0])
    monkeypatch.delattr(psutil, "win_service_iter", raising=False)

    snapshot = worker._collect_measurement(2.0)

    assert snapshot.processes[0].metadata_state == "unavailable"


def test_inaccessible_executable_path_preserves_process_measurement(
    monkeypatch,
):
    worker, _, _, _ = make_worker()
    process = make_process()
    process.info["exe"] = None

    def fake_process_iter(**kwargs):
        process.info["exe"] = kwargs["ad_value"]
        return iter([process])

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        fake_process_iter,
    )
    monkeypatch.setattr(
        psutil,
        "win_service_iter",
        lambda: iter([]),
        raising=False,
    )
    patch_clock(monkeypatch, [10.0])

    snapshot = worker._collect_measurement(2.0)

    assert len(snapshot.processes) == 1
    assert snapshot.processes[0].executable_path is None
    assert snapshot.processes[0].metadata_state == "partial"
    assert snapshot.process_errors == ()


def test_decreasing_cpu_counter_resets_baseline(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter([
        [make_process(user_time=2.0, system_time=1.0)],
        [make_process(user_time=1.5, system_time=0.5)],
        [make_process(user_time=2.5, system_time=0.5)],
    ])

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        lambda **kwargs: iter(next(samples)),
    )
    patch_clock(monkeypatch, [10.0, 12.0, 14.0])

    first = worker._collect_measurement(2.0)
    second = worker._collect_measurement(2.0)
    third = worker._collect_measurement(2.0)

    assert first.processes[0].cpu_percent is None
    assert second.processes[0].cpu_percent is None
    assert third.processes[0].cpu_percent == 50.0


@pytest.mark.parametrize(
    ("user_time", "system_time"),
    [
        (-1.0, 0.0),
        (float("inf"), 0.0),
        (float("nan"), 0.0),
        ("invalid", 0.0),
        (True, 0.0),
    ],
)
def test_invalid_cpu_counters_produce_unavailable_cpu(
    monkeypatch,
    user_time,
    system_time,
):
    worker, _, _, _ = make_worker()

    samples = iter([
        [make_process(user_time=2.0, system_time=1.0)],
        [make_process(user_time=user_time, system_time=system_time)],
    ])

    monkeypatch.setattr(
        "system_monitor.workers.process_monitoring_worker.psutil.process_iter",
        lambda **kwargs: iter(next(samples)),
    )
    patch_clock(monkeypatch, [10.0, 12.0])

    worker._collect_measurement(2.0)
    snapshot = worker._collect_measurement(2.0)

    assert snapshot.processes[0].cpu_percent is None
