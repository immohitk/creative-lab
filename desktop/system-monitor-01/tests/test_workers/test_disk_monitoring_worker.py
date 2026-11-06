import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from system_monitor.workers.disk_monitoring_worker import (
    DiskMonitoringWorker,
    DiskWorkerError,
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

    worker = DiskMonitoringWorker(
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


def make_partition(
    device="C:\\",
    mountpoint="C:\\",
    fstype="NTFS",
):
    return SimpleNamespace(
        device=device,
        mountpoint=mountpoint,
        fstype=fstype,
    )


def make_usage(
    total=1000,
    used=400,
    free=600,
    percent=40.0,
):
    return SimpleNamespace(
        total=total,
        used=used,
        free=free,
        percent=percent,
    )


def patch_partitions(monkeypatch, partitions=None):
    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_partitions",
        lambda all=False: [] if partitions is None else partitions,
    )


def patch_usage(monkeypatch, usage=None):
    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_usage",
        lambda path: usage or make_usage(),
    )


@pytest.mark.parametrize(
    "value",
    [0, -1, 0.49, 60.01, True, float("nan"), float("inf"), float("-inf")],
)
def test_worker_rejects_invalid_sampling_interval(value):
    with pytest.raises((TypeError, ValueError)):
        make_worker(interval=value)


def test_worker_accepts_minimum_sampling_interval():
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
        DiskMonitoringWorker(
            session_id="not-a-uuid",
            sampling_interval=1.0,
            on_measurement=lambda value: None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
        )


def test_worker_requires_callable_callbacks():
    with pytest.raises(TypeError):
        DiskMonitoringWorker(
            session_id=uuid4(),
            sampling_interval=1.0,
            on_measurement=None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
        )


def test_worker_rejects_invalid_startup_callback():
    with pytest.raises(TypeError):
        DiskMonitoringWorker(
            session_id=uuid4(),
            sampling_interval=1.0,
            on_measurement=lambda value: None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
            on_started="not-callable",
        )


def test_worker_collects_mounted_volumes(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [make_partition()])
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert len(measurement.volumes) == 1
    volume = measurement.volumes[0]
    assert volume.volume_id == "C:\\::C:\\"
    assert volume.device == "C:\\"
    assert volume.mount_point == "C:\\"
    assert volume.filesystem == "NTFS"
    assert volume.total_bytes == 1000
    assert volume.used_bytes == 400
    assert volume.free_bytes == 600
    assert volume.percent == 40.0
    assert measurement.volume_errors == ()


def test_worker_collects_multiple_volumes(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [
            make_partition("C:\\", "C:\\"),
            make_partition("D:\\", "D:\\"),
        ],
    )

    calls = []

    def fake_usage(path):
        calls.append(path)
        return make_usage()

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_usage",
        fake_usage,
    )

    measurement = worker._collect_measurement(1.0)

    assert calls == ["C:\\", "D:\\"]
    assert len(measurement.volumes) == 2


def test_worker_preserves_sequential_volume_order(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [
            make_partition("A:", "A:"),
            make_partition("B:", "B:"),
            make_partition("C:", "C:"),
        ],
    )

    calls = []

    def fake_usage(path):
        calls.append(path)
        return make_usage()

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_usage",
        fake_usage,
    )

    worker._collect_measurement(1.0)

    assert calls == ["A:", "B:", "C:"]


def test_worker_returns_successful_empty_inventory(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [])

    measurement = worker._collect_measurement(1.0)

    assert measurement.volumes == ()
    assert measurement.volume_errors == ()
    assert measurement.is_empty
    assert measurement.is_fully_successful
    assert not measurement.is_unavailable


def test_worker_preserves_accessible_volume_when_another_fails(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [
            make_partition("C:", "C:"),
            make_partition("D:", "D:"),
        ],
    )

    def fake_usage(path):
        if path == "D:":
            raise PermissionError("Access denied")
        return make_usage()

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_usage",
        fake_usage,
    )

    measurement = worker._collect_measurement(1.0)

    assert len(measurement.volumes) == 1
    assert measurement.volumes[0].mount_point == "C:"
    assert len(measurement.volume_errors) == 1
    assert measurement.volume_errors[0].volume_id == "D:::D:"
    assert measurement.is_partial


def test_worker_returns_unavailable_when_all_volumes_fail(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [
            make_partition("C:", "C:"),
            make_partition("D:", "D:"),
        ],
    )

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_usage",
        lambda path: (_ for _ in ()).throw(PermissionError("Access denied")),
    )

    measurement = worker._collect_measurement(1.0)

    assert measurement.volumes == ()
    assert len(measurement.volume_errors) == 2
    assert measurement.is_unavailable


def test_worker_reports_duplicate_identity_and_keeps_first(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [
            make_partition("C:", "C:"),
            make_partition("C:", "C:"),
        ],
    )
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert len(measurement.volumes) == 1
    assert len(measurement.volume_errors) == 1

    error = measurement.volume_errors[0]
    assert error.error_code == "DUPLICATE_VOLUME_IDENTITY"
    assert error.volume_id is None
    assert error.device == "C:"
    assert error.mount_point == "C:"


def test_worker_keeps_first_duplicate_identity_even_if_first_read_fails(
    monkeypatch,
):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [
            make_partition("C:", "C:"),
            make_partition("C:", "C:"),
        ],
    )

    calls = []

    def fake_usage(path):
        calls.append(path)
        raise PermissionError("Access denied")

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_usage",
        fake_usage,
    )

    measurement = worker._collect_measurement(1.0)

    assert calls == ["C:"]
    assert len(measurement.volume_errors) == 2
    assert measurement.volume_errors[0].volume_id == "C:::C:"
    assert measurement.volume_errors[1].error_code == (
        "DUPLICATE_VOLUME_IDENTITY"
    )
    assert measurement.volume_errors[1].volume_id is None


def test_worker_reports_partition_enumeration_failure(monkeypatch):
    worker, *_ = make_worker()

    def fail(all=False):
        raise OSError("Partition enumeration failed")

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_partitions",
        fail,
    )

    with pytest.raises(DiskWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "DISK_PARTITION_ENUMERATION_FAILED"


@pytest.mark.parametrize("partitions", [None, "invalid", 123, {}])
def test_worker_rejects_invalid_partition_collection(monkeypatch, partitions):
    worker, *_ = make_worker()

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_partitions",
        lambda all=False: partitions,
    )

    with pytest.raises(DiskWorkerError) as error:
        worker._collect_measurement(1.0)

    assert error.value.error_code == "DISK_INVALID_PARTITION_LIST"


@pytest.mark.parametrize(
    "partition",
    [
        SimpleNamespace(device=None, mountpoint="C:", fstype="NTFS"),
        SimpleNamespace(device="C:", mountpoint=None, fstype="NTFS"),
        SimpleNamespace(device="", mountpoint="C:", fstype="NTFS"),
        SimpleNamespace(device="C:", mountpoint="", fstype="NTFS"),
    ],
)
def test_worker_reports_invalid_partition_metadata(monkeypatch, partition):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [partition])

    measurement = worker._collect_measurement(1.0)

    assert measurement.volumes == ()
    assert len(measurement.volume_errors) == 1
    assert measurement.volume_errors[0].error_code == "DISK_INVALID_PARTITION"


def test_worker_isolates_partition_metadata_exception(monkeypatch):
    worker, *_ = make_worker()

    class BrokenPartition:
        @property
        def device(self):
            raise OSError("Metadata unavailable")

    patch_partitions(
        monkeypatch,
        [
            BrokenPartition(),
            make_partition("D:", "D:"),
        ],
    )
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert len(measurement.volumes) == 1
    assert measurement.volumes[0].mount_point == "D:"
    assert len(measurement.volume_errors) == 1


@pytest.mark.parametrize(
    "usage",
    [
        make_usage(total=0, used=0, free=0),
        make_usage(total=-1, used=0, free=1),
        make_usage(total=1000, used=-1, free=1001),
        make_usage(total=1000, used=1001, free=0),
        make_usage(total=1000, used=500, free=400),
        make_usage(total=1000, used=500, free=600),
    ],
)
def test_worker_rejects_invalid_capacity_readings(monkeypatch, usage):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [make_partition()])
    patch_usage(monkeypatch, usage)

    measurement = worker._collect_measurement(1.0)

    assert measurement.volumes == ()
    assert measurement.volume_errors[0].error_code == "DISK_INVALID_READING"


@pytest.mark.parametrize(
    "field",
    ["total", "used", "free"],
)
@pytest.mark.parametrize(
    "value",
    [True, 1.5, "100", None],
)
def test_worker_rejects_non_integer_byte_readings(monkeypatch, field, value):
    worker, *_ = make_worker()
    usage = make_usage()
    setattr(usage, field, value)
    patch_partitions(monkeypatch, [make_partition()])
    patch_usage(monkeypatch, usage)

    measurement = worker._collect_measurement(1.0)

    assert measurement.volume_errors[0].error_code == "DISK_INVALID_READING"


@pytest.mark.parametrize(
    "value",
    [True, "40", None, -1.0, 101.0, float("nan"), float("inf")],
)
def test_worker_rejects_invalid_percentages(monkeypatch, value):
    worker, *_ = make_worker()
    usage = make_usage(percent=value)
    patch_partitions(monkeypatch, [make_partition()])
    patch_usage(monkeypatch, usage)

    measurement = worker._collect_measurement(1.0)

    assert measurement.volume_errors[0].error_code == "DISK_INVALID_READING"


def test_worker_rejects_invalid_filesystem_type(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [make_partition(fstype=123)],
    )
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert measurement.volumes == ()
    assert measurement.volume_errors[0].error_code == "DISK_INVALID_READING"


def test_worker_normalizes_empty_filesystem_to_none(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(
        monkeypatch,
        [make_partition(fstype="  ")],
    )
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert measurement.volumes[0].filesystem is None


def test_worker_handles_volume_read_failure(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [make_partition()])

    monkeypatch.setattr(
        "system_monitor.workers.disk_monitoring_worker.psutil.disk_usage",
        lambda path: (_ for _ in ()).throw(OSError("I/O failure")),
    )

    measurement = worker._collect_measurement(1.0)

    assert measurement.volumes == ()
    assert measurement.volume_errors[0].error_code == "DISK_VOLUME_READ_FAILED"


def test_worker_measurement_timestamps_are_utc(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [make_partition()])
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert isinstance(measurement.started_at, datetime)
    assert measurement.started_at.tzinfo == timezone.utc
    assert measurement.completed_at.tzinfo == timezone.utc
    assert measurement.completed_at >= measurement.started_at


def test_worker_measurement_is_immutable(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [make_partition()])
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    with pytest.raises(AttributeError):
        measurement.sampling_interval = 2.0


def test_worker_measurement_volumes_are_immutable(monkeypatch):
    worker, *_ = make_worker()
    patch_partitions(monkeypatch, [make_partition()])
    patch_usage(monkeypatch)

    measurement = worker._collect_measurement(1.0)

    assert isinstance(measurement.volumes, tuple)


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


def test_reconfiguration_is_consumed():
    worker, *_ = make_worker()
    worker.reconfigure_event.set()

    worker._consume_reconfiguration()

    assert not worker.reconfigure_event.is_set()


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


def test_worker_recovers_after_measurement_failure(monkeypatch):
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

    calls = []

    def collect(interval):
        calls.append(interval)

        if len(calls) == 1:
            raise DiskWorkerError(
                "DISK_PARTITION_ENUMERATION_FAILED",
                "Temporary failure.",
            )

        return object()

    monkeypatch.setattr(worker, "_collect_measurement", collect)

    worker._run_loop()

    assert calls == [1.0, 1.0]
    assert len(failures) == 1
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


def test_measurement_callback_failure_is_isolated():
    worker, _, _, worker_failures = make_worker(
        on_measurement=lambda measurement: (_ for _ in ()).throw(
            RuntimeError("Subscriber failed")
        )
    )

    worker._deliver_measurement(object())

    assert worker_failures == []


def test_measurement_failure_callback_failure_is_isolated():
    worker, *_ = make_worker(
        on_measurement_failure=lambda code, message: (_ for _ in ()).throw(
            RuntimeError("Subscriber failed")
        )
    )

    worker._report_measurement_failure(
        "DISK_MEASUREMENT_FAILED",
        "Measurement failed.",
    )


def test_worker_failure_callback_failure_is_isolated():
    worker, *_ = make_worker(
        on_worker_failure=lambda: (_ for _ in ()).throw(
            RuntimeError("Callback failed")
        )
    )

    worker._run_loop = lambda: (_ for _ in ()).throw(
        RuntimeError("Unexpected worker failure")
    )

    worker.run()

