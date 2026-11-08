import threading
import time
from datetime import datetime, timezone
from uuid import UUID

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from system_monitor.models import (
    DiskError,
    DiskMeasurement,
    DiskMeasurementFreshness,
    DiskMeasurementStatus,
    DiskVolumeMeasurement,
    DiskWorkerState,
)
from system_monitor.services import disk_monitoring_service as service_module
from system_monitor.services.disk_monitoring_service import DiskMonitoringService


@pytest.fixture
def qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def process_events(app, milliseconds=0):
    loop = QEventLoop()
    if milliseconds <= 0:
        QTimer.singleShot(0, loop.quit)
    else:
        QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


class FakeWorker:
    instances = []

    def __init__(
        self,
        session_id,
        sampling_interval,
        on_measurement,
        on_measurement_failure,
        on_worker_failure,
        stop_event=None,
        reconfigure_event=None,
        on_started=None,
    ):
        self.session_id = session_id
        self.sampling_interval = sampling_interval
        self.on_measurement = on_measurement
        self.on_measurement_failure = on_measurement_failure
        self.on_worker_failure = on_worker_failure
        self.stop_event = stop_event or threading.Event()
        self.reconfigure_event = reconfigure_event
        self.on_started = on_started
        self.raise_on_reconfigure = False
        self.__class__.instances.append(self)

    def run(self):
        if self.on_started:
            self.on_started()
        self.stop_event.wait()

    def set_sampling_interval(self, seconds):
        if self.raise_on_reconfigure:
            raise RuntimeError("Simulated reconfiguration failure.")
        self.sampling_interval = seconds
        if self.reconfigure_event is not None:
            self.reconfigure_event.set()


@pytest.fixture(autouse=True)
def reset_fake_workers():
    FakeWorker.instances.clear()
    yield
    FakeWorker.instances.clear()


@pytest.fixture
def service(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        FakeWorker,
    )
    instance = DiskMonitoringService()
    yield instance

    worker_thread = instance._worker_thread
    if worker_thread is not None:
        if worker_thread.is_alive():
            instance.stop()
            worker_thread.join(timeout=2)

        qt_app.processEvents()
        qt_app.processEvents()

        if worker_thread.is_alive():
            raise AssertionError("Disk worker thread did not stop.")


def make_volume(
    device="/dev/sda1",
    mount_point="/",
    total_bytes=1000,
    used_bytes=600,
    filesystem="ext4",
):
    free_bytes = total_bytes - used_bytes
    return DiskVolumeMeasurement(
        volume_id=DiskVolumeMeasurement.build_volume_id(
            device,
            mount_point,
        ),
        device=device,
        mount_point=mount_point,
        filesystem=filesystem,
        total_bytes=total_bytes,
        used_bytes=used_bytes,
        free_bytes=free_bytes,
        percent=(used_bytes / total_bytes) * 100,
    )


def make_error(
    device="/dev/sdb1",
    mount_point="/data",
    error_code="DISK_USAGE_FAILED",
):
    return DiskError(
        error_code=error_code,
        message="Simulated disk usage failure.",
        occurred_at=datetime.now(timezone.utc),
        volume_id=DiskVolumeMeasurement.build_volume_id(
            device,
            mount_point,
        ),
        device=device,
        mount_point=mount_point,
    )


def make_measurement(volumes=None, errors=None, sampling_interval=1.0):
    now = datetime.now(timezone.utc)
    return DiskMeasurement(
        volumes=tuple(volumes or ()),
        volume_errors=tuple(errors or ()),
        sampling_interval=sampling_interval,
        started_at=now,
        completed_at=now,
    )


def test_service_initial_state(service):
    assert service.get_worker_state() == DiskWorkerState.STOPPED
    assert service.get_measurement_status() == DiskMeasurementStatus.UNAVAILABLE
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.NO_DATA
    assert service.get_latest_measurement() is None
    assert service.get_last_successful_measurement() is None
    assert service.get_measurement_error() is None
    assert service.get_worker_error() is None
    assert service.get_consecutive_failures() == 0
    assert service.get_sampling_interval() == 1.0
    assert service.get_last_successful_age() is None


@pytest.mark.parametrize("interval", [0.5, 1.0, 2.5, 30.0, 60.0])
def test_service_accepts_valid_sampling_intervals(service, interval):
    result = service.set_sampling_interval(interval)

    assert result.accepted is True
    assert result.sampling_interval == interval
    assert service.get_sampling_interval() == interval


@pytest.mark.parametrize(
    "interval",
    [0, -1, 0.49, 60.01, float("inf"), float("nan"), True, "1"],
)
def test_service_rejects_invalid_sampling_intervals(service, interval):
    result = service.set_sampling_interval(interval)

    assert result.accepted is False
    assert result.error is not None
    assert service.get_sampling_interval() == 1.0


def test_service_publishes_current_state(service):
    received = []
    service.current_state_published.connect(received.append)

    snapshot = service.publish_current_state()

    assert received == [snapshot]
    assert snapshot.worker_state == DiskWorkerState.STOPPED


def test_service_starts_worker(service, qt_app):
    result = service.start()
    process_events(qt_app, 100)

    assert result.accepted is True
    assert len(FakeWorker.instances) == 1
    assert service.get_worker_state() == DiskWorkerState.RUNNING


def test_service_assigns_valid_session_id(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    assert isinstance(FakeWorker.instances[0].session_id, UUID)
    assert FakeWorker.instances[0].session_id == service._session_id


def test_service_does_not_start_duplicate_worker(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    result = service.start()
    process_events(qt_app, 50)

    assert result.accepted is True
    assert len(FakeWorker.instances) == 1


def test_service_stops_worker(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    result = service.stop()
    process_events(qt_app, 150)

    assert result.worker_state in (
        DiskWorkerState.STOPPING,
        DiskWorkerState.STOPPED,
    )

    deadline = time.monotonic() + 2.0
    while (
        service.get_worker_state() != DiskWorkerState.STOPPED
        and time.monotonic() < deadline
    ):
        process_events(qt_app, 50)

    assert service.get_worker_state() == DiskWorkerState.STOPPED
    assert FakeWorker.instances[0].stop_event.is_set()
    assert FakeWorker.instances[0].stop_event.is_set()


def test_service_start_stop_start_uses_new_session(service, qt_app):
    service.start()
    process_events(qt_app, 100)
    first_session_id = FakeWorker.instances[0].session_id

    service.stop()
    process_events(qt_app, 150)

    service.start()
    process_events(qt_app, 100)

    assert len(FakeWorker.instances) == 2
    assert FakeWorker.instances[1].session_id != first_session_id
    assert service.get_worker_state() == DiskWorkerState.RUNNING


def test_service_accepts_successful_disk_measurement(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    measurement = make_measurement(
        volumes=[
            make_volume("/dev/sda1", "/", 1000, 600),
            make_volume("/dev/sdb1", "/data", 2000, 900),
        ],
    )

    FakeWorker.instances[0].on_measurement(measurement)
    process_events(qt_app, 100)

    assert service.get_latest_measurement() == measurement
    assert service.get_last_successful_measurement() == measurement
    assert service.get_measurement_status() == DiskMeasurementStatus.AVAILABLE
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.FRESH
    assert service.get_measurement_error() is None
    assert service.get_consecutive_failures() == 0


def test_service_emits_measurement_updated_signal(service, qt_app):
    received = []
    service.measurement_updated.connect(received.append)

    service.start()
    process_events(qt_app, 100)

    measurement = make_measurement(volumes=[make_volume()])
    FakeWorker.instances[0].on_measurement(measurement)
    process_events(qt_app, 100)

    assert len(received) == 1
    assert received[0] == measurement


def test_service_updates_successful_measurement_atomically(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]

    first = make_measurement(
        volumes=[make_volume(used_bytes=600)],
    )
    second = make_measurement(
        volumes=[make_volume(used_bytes=800)],
    )

    worker.on_measurement(first)
    process_events(qt_app, 100)
    first_snapshot = service._read_snapshot()

    worker.on_measurement(second)
    process_events(qt_app, 100)
    second_snapshot = service._read_snapshot()

    assert first_snapshot.last_successful_measurement == first
    assert second_snapshot.last_successful_measurement == second
    assert second_snapshot.revision > first_snapshot.revision


def test_service_ignores_measurement_from_stale_session(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    measurement = make_measurement(volumes=[make_volume()])

    service._worker_measurement_received.emit(
        UUID(int=0),
        measurement,
    )
    process_events(qt_app, 100)

    assert service.get_latest_measurement() is None
    assert service.get_last_successful_measurement() is None


def test_service_records_partial_measurement(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    measurement = make_measurement(
        volumes=[make_volume("/dev/sda1", "/", 1000, 600)],
        errors=[make_error()],
    )

    FakeWorker.instances[0].on_measurement(measurement)
    process_events(qt_app, 100)

    latest = service.get_latest_measurement()

    assert latest is not None
    assert len(latest.volumes) == 1
    assert len(latest.volume_errors) == 1
    assert service.get_measurement_status() == DiskMeasurementStatus.PARTIAL
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.NO_DATA
    assert service.get_last_successful_measurement() is None
    assert service.get_measurement_error().error_code == "DISK_USAGE_FAILED"
    assert service.get_consecutive_failures() == 1


def test_service_preserves_last_successful_measurement_after_partial_cycle(
    service,
    qt_app,
):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    successful = make_measurement(
        volumes=[make_volume("/dev/sda1", "/", 1000, 600)],
    )

    worker.on_measurement(successful)
    process_events(qt_app, 100)

    partial = make_measurement(
        volumes=[make_volume("/dev/sda1", "/", 1000, 700)],
        errors=[make_error()],
    )
    worker.on_measurement(partial)
    process_events(qt_app, 100)

    assert service.get_latest_measurement().is_partial
    assert service.get_last_successful_measurement() == successful
    assert service.get_measurement_status() == DiskMeasurementStatus.PARTIAL
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.STALE


def test_service_records_all_volume_failure(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    measurement = make_measurement(errors=[make_error()])
    FakeWorker.instances[0].on_measurement(measurement)
    process_events(qt_app, 100)

    latest = service.get_latest_measurement()
    assert latest is not None
    assert latest.volumes == ()
    assert len(latest.volume_errors) == 1
    assert latest.volume_errors[0].error_code == "DISK_USAGE_FAILED"
    assert latest.volume_errors[0].consecutive_failures == 1
    assert service.get_measurement_status() == DiskMeasurementStatus.UNAVAILABLE
    assert service.get_measurement_error() is not None
    assert service.get_consecutive_failures() == 1


def test_service_accepts_empty_inventory_as_success(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    measurement = make_measurement()
    FakeWorker.instances[0].on_measurement(measurement)
    process_events(qt_app, 100)

    assert measurement.is_empty
    assert service.get_latest_measurement() == measurement
    assert service.get_last_successful_measurement() == measurement
    assert service.get_measurement_status() == DiskMeasurementStatus.AVAILABLE
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.FRESH
    assert service.get_measurement_error() is None
    assert service.get_consecutive_failures() == 0


def test_service_tracks_consecutive_failures_per_volume(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    error = make_error()

    worker.on_measurement(make_measurement(errors=[error]))
    process_events(qt_app, 100)

    assert service.get_latest_measurement().volume_errors[0].consecutive_failures == 1

    worker.on_measurement(make_measurement(errors=[error]))
    process_events(qt_app, 100)

    assert service.get_latest_measurement().volume_errors[0].consecutive_failures == 2


def test_service_resets_volume_failure_count_after_success(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    error = make_error()

    worker.on_measurement(make_measurement(errors=[error]))
    process_events(qt_app, 100)

    worker.on_measurement(make_measurement(errors=[error]))
    process_events(qt_app, 100)

    successful_volume = make_volume("/dev/sdb1", "/data")
    worker.on_measurement(
        make_measurement(volumes=[successful_volume]),
    )
    process_events(qt_app, 100)

    assert service.get_measurement_status() == DiskMeasurementStatus.AVAILABLE
    assert service.get_consecutive_failures() == 0
    assert service._volume_failure_counts == {}


def test_service_clears_failure_counts_for_disappeared_volumes(
    service,
    qt_app,
):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    error = make_error()

    worker.on_measurement(make_measurement(errors=[error]))
    process_events(qt_app, 100)

    worker.on_measurement(make_measurement(errors=[error]))
    process_events(qt_app, 100)

    volume_id = error.volume_id
    assert service._volume_failure_counts[volume_id] == 2

    # The volume disappears from the inventory.
    worker.on_measurement(make_measurement())
    process_events(qt_app, 100)

    assert volume_id not in service._volume_failure_counts

    # If the volume returns and fails again, its count starts at one.
    worker.on_measurement(make_measurement(errors=[error]))
    process_events(qt_app, 100)

    assert (
        service.get_latest_measurement()
        .volume_errors[0]
        .consecutive_failures
        == 1
    )


def test_service_recovers_after_all_volume_failure(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    successful = make_measurement(
        volumes=[make_volume("/dev/sda1", "/", 1000, 600)],
    )
    worker.on_measurement(successful)
    process_events(qt_app, 100)

    failed = make_measurement(errors=[make_error()])
    worker.on_measurement(failed)
    process_events(qt_app, 100)

    assert service.get_measurement_status() == DiskMeasurementStatus.UNAVAILABLE
    assert service.get_last_successful_measurement() == successful
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.STALE

    recovered = make_measurement(
        volumes=[make_volume("/dev/sda1", "/", 1000, 750)],
    )
    worker.on_measurement(recovered)
    process_events(qt_app, 100)

    assert service.get_latest_measurement() == recovered
    assert service.get_last_successful_measurement() == recovered
    assert service.get_measurement_status() == DiskMeasurementStatus.AVAILABLE
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.FRESH
    assert service.get_measurement_error() is None
    assert service.get_consecutive_failures() == 0


def test_service_records_worker_measurement_failure(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    worker.on_measurement_failure(
        "DISK_ENUMERATION_FAILED",
        "Simulated partition enumeration failure.",
    )
    process_events(qt_app, 100)

    error = service.get_measurement_error()

    assert isinstance(error, DiskError)
    assert error.error_code == "DISK_ENUMERATION_FAILED"
    assert "partition enumeration failure" in error.message
    assert service.get_latest_measurement() is None
    assert service.get_measurement_status() == DiskMeasurementStatus.UNAVAILABLE
    assert service.get_consecutive_failures() == 1


def test_service_preserves_successful_snapshot_after_worker_failure(
    service,
    qt_app,
):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    successful = make_measurement(
        volumes=[make_volume()],
    )
    worker.on_measurement(successful)
    process_events(qt_app, 100)

    worker.on_measurement_failure(
        "DISK_ENUMERATION_FAILED",
        "Temporary enumeration failure.",
    )
    process_events(qt_app, 100)

    assert service.get_latest_measurement() is None
    assert service.get_last_successful_measurement() == successful
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.STALE


def test_service_recovers_after_all_volume_failure(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    successful = make_measurement(
        volumes=[make_volume("/dev/sda1", "/", 1000, 600)],
    )
    worker.on_measurement(successful)
    process_events(qt_app, 100)

    failed = make_measurement(errors=[make_error()])
    worker.on_measurement(failed)
    process_events(qt_app, 100)

    assert service.get_measurement_status() == DiskMeasurementStatus.UNAVAILABLE
    assert service.get_last_successful_measurement() == successful
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.STALE

    recovered = make_measurement(
        volumes=[make_volume("/dev/sda1", "/", 1000, 750)],
    )
    worker.on_measurement(recovered)
    process_events(qt_app, 100)

    assert service.get_latest_measurement() == recovered
    assert service.get_last_successful_measurement() == recovered
    assert service.get_measurement_status() == DiskMeasurementStatus.AVAILABLE
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.FRESH
    assert service.get_measurement_error() is None
    assert service.get_consecutive_failures() == 0


def test_service_records_worker_measurement_failure(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    worker.on_measurement_failure(
        "DISK_ENUMERATION_FAILED",
        "Simulated partition enumeration failure.",
    )
    process_events(qt_app, 100)

    error = service.get_measurement_error()

    assert isinstance(error, DiskError)
    assert error.error_code == "DISK_ENUMERATION_FAILED"
    assert "partition enumeration failure" in error.message
    assert service.get_latest_measurement() is None
    assert service.get_measurement_status() == DiskMeasurementStatus.UNAVAILABLE
    assert service.get_consecutive_failures() == 1


def test_service_preserves_successful_snapshot_after_worker_failure(
    service,
    qt_app,
):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    successful = make_measurement(
        volumes=[make_volume()],
    )
    worker.on_measurement(successful)
    process_events(qt_app, 100)

    worker.on_measurement_failure(
        "DISK_ENUMERATION_FAILED",
        "Temporary enumeration failure.",
    )
    process_events(qt_app, 100)

    assert service.get_latest_measurement() is None
    assert service.get_last_successful_measurement() == successful
    assert service.get_measurement_freshness() == DiskMeasurementFreshness.STALE


class BlockingFakeWorker(FakeWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(self):
        self.entered.set()
        if self.on_started:
            self.on_started()
        self.stop_event.wait(timeout=10)


class UncooperativeFakeWorker(BlockingFakeWorker):
    def run(self):
        self.entered.set()
        if self.on_started:
            self.on_started()
        self.release.wait(timeout=10)


class StartupStallingFakeWorker(FakeWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(self):
        self.entered.set()
        self.release.wait(timeout=10)


def wait_for_condition(app, condition, timeout=2.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        app.processEvents()

        if condition():
            return True

        time.sleep(0.01)

    app.processEvents()
    return condition()


def test_service_retains_worker_after_shutdown_timeout(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        UncooperativeFakeWorker,
    )
    monkeypatch.setattr(
        DiskMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.1,
    )

    instance = DiskMonitoringService()
    instance.start()

    worker = UncooperativeFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.FAILED,
    )

    assert instance.get_worker_error().error_code == "DISK_SHUTDOWN_TIMEOUT"
    assert instance._worker_thread is not None
    assert instance._worker_thread.is_alive()

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: not instance._worker_thread.is_alive(),
    )

    retry_result = instance.stop()

    assert retry_result.success is True
    assert instance.get_worker_state() == DiskWorkerState.STOPPED
    assert instance._worker_thread is None


def test_service_startup_timeout_preserves_error_and_cleans_worker(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        DiskMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        DiskMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    instance = DiskMonitoringService()
    result = instance.start()
    assert result.accepted is True

    worker = StartupStallingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance.get_worker_state() == DiskWorkerState.FAILED
            and instance.get_worker_error() is not None
        ),
    )

    assert instance.get_worker_error().error_code == "DISK_STARTUP_TIMEOUT"
    assert instance._startup_cleanup_pending is True
    assert instance._worker_thread is not None
    assert instance._worker_thread.is_alive()

    rejected = instance.start()
    assert rejected.accepted is False
    assert len(StartupStallingFakeWorker.instances) == 1

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is None
            and not instance._startup_cleanup_pending
        ),
    )

    assert instance.get_worker_state() == DiskWorkerState.FAILED
    assert instance.get_worker_error().error_code == "DISK_STARTUP_TIMEOUT"

    restarted = instance.start()
    assert restarted.accepted is True
    assert len(StartupStallingFakeWorker.instances) == 2

    restarted_worker = StartupStallingFakeWorker.instances[-1]
    restarted_thread = instance._worker_thread

    restarted_worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: not restarted_thread.is_alive(),
    )

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is None
            and not instance._startup_cleanup_pending
        ),
    )

    assert instance.get_worker_state() == DiskWorkerState.FAILED
    assert instance.get_worker_error().error_code == "DISK_STARTUP_TIMEOUT"


def test_service_ignores_stale_callbacks_after_shutdown(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        FakeWorker,
    )

    instance = DiskMonitoringService()

    first_start = instance.start()
    assert first_start.accepted is True

    first_session_id = instance._session_id

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    stop_result = instance.stop()
    assert stop_result.success is False
    assert stop_result.worker_state == DiskWorkerState.STOPPING

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.STOPPED,
    )
    assert instance._worker_thread is None

    second_start = instance.start()
    assert second_start.accepted is True

    second_session_id = instance._session_id
    assert second_session_id != first_session_id

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    current_measurement = make_measurement(
        volumes=[make_volume(used_bytes=600)],
    )
    instance._handle_worker_measurement(
        second_session_id,
        current_measurement,
    )

    service_state = instance.get_last_successful_measurement()
    assert service_state is not None
    assert service_state == current_measurement

    previous_worker_state = instance.get_worker_state()
    previous_worker_error = instance.get_worker_error()

    stale_measurement = make_measurement(
        volumes=[make_volume(used_bytes=900)],
    )

    instance._handle_worker_measurement(
        first_session_id,
        stale_measurement,
    )
    instance._handle_worker_failure(first_session_id)

    assert instance.get_last_successful_measurement() == current_measurement
    assert instance.get_worker_state() == previous_worker_state
    assert instance.get_worker_error() == previous_worker_error

    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.STOPPED,
    )
    assert instance._worker_thread is None


def test_service_reconfigures_running_worker_sampling_interval(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        FakeWorker,
    )

    instance = DiskMonitoringService()

    result = instance.start()
    assert result.accepted is True

    worker = FakeWorker.instances[0]

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    configuration = instance.set_sampling_interval(2.5)

    assert configuration.accepted is True
    assert configuration.sampling_interval == 2.5
    assert configuration.worker_state == DiskWorkerState.RUNNING

    assert worker.sampling_interval == 2.5
    assert instance.get_sampling_interval() == 2.5

    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.STOPPED,
    )

    assert instance._worker_thread is None

def test_service_preserves_configuration_when_worker_reconfiguration_fails(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        FakeWorker,
    )

    instance = DiskMonitoringService()

    result = instance.start()
    assert result.accepted is True

    worker = FakeWorker.instances[0]

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    previous_interval = instance.get_sampling_interval()
    worker.raise_on_reconfigure = True

    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == DiskWorkerState.RUNNING

    assert configuration.error is not None
    assert configuration.error.error_code == "DISK_CONFIGURATION_FAILED"

    assert instance.get_sampling_interval() == previous_interval
    assert worker.sampling_interval == previous_interval

    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.STOPPED,
    )

    assert instance._worker_thread is None

def test_service_rejects_configuration_change_while_stopping(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        BlockingFakeWorker,
    )

    instance = DiskMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    stop_result = instance.stop()

    assert stop_result.success is False
    assert stop_result.worker_state == DiskWorkerState.STOPPING

    previous_interval = instance.get_sampling_interval()
    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == DiskWorkerState.STOPPING

    assert configuration.error is not None
    assert configuration.error.error_code == "DISK_CONFIGURATION_REJECTED"

    assert instance.get_sampling_interval() == previous_interval
    assert worker.sampling_interval == previous_interval

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.STOPPED,
    )

    assert instance._worker_thread is None

def test_service_rejects_configuration_during_startup_cleanup(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        DiskMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        DiskMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    instance = DiskMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = StartupStallingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance.get_worker_state() == DiskWorkerState.FAILED
            and instance._startup_cleanup_pending
        ),
    )

    previous_interval = instance.get_sampling_interval()
    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == DiskWorkerState.FAILED

    assert configuration.error is not None
    assert configuration.error.error_code == "DISK_CONFIGURATION_REJECTED"

    assert instance.get_sampling_interval() == previous_interval

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is None
            and not instance._startup_cleanup_pending
        ),
    )

    assert instance.get_worker_state() == DiskWorkerState.FAILED
    assert instance.get_sampling_interval() == previous_interval

def test_service_rejects_configuration_while_failed_worker_is_alive(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        UncooperativeFakeWorker,
    )
    monkeypatch.setattr(
        DiskMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.1,
    )

    instance = DiskMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = UncooperativeFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    instance._handle_worker_failure(instance._session_id)

    assert instance.get_worker_state() == DiskWorkerState.FAILED
    assert instance.get_worker_error().error_code == "DISK_WORKER_FAILED"

    previous_interval = instance.get_sampling_interval()
    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == DiskWorkerState.FAILED

    assert configuration.error is not None
    assert configuration.error.error_code == "DISK_CONFIGURATION_REJECTED"

    assert instance.get_sampling_interval() == previous_interval

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is not None
            and not instance._worker_thread.is_alive()
        ),
    )

    stop_result = instance.stop()

    assert stop_result.success is True
    assert stop_result.worker_state == DiskWorkerState.STOPPED

    assert instance._worker_thread is None
    assert instance.get_worker_state() == DiskWorkerState.STOPPED

def test_service_stops_worker_thread_cleanly(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "DiskMonitoringWorker",
        BlockingFakeWorker,
    )

    instance = DiskMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.RUNNING,
    )

    stop_result = instance.stop()

    assert stop_result.success is False
    assert stop_result.worker_state == DiskWorkerState.STOPPING

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == DiskWorkerState.STOPPED,
    )

    assert instance._worker_thread is None
    assert instance._worker is None
    assert instance._session_id is None

def test_service_integrates_with_real_disk_worker(monkeypatch, qt_app):
    from types import SimpleNamespace
    from system_monitor.workers import disk_monitoring_worker as worker_module

    partition = SimpleNamespace(
        device=r"\\?\Volume{TEST-VOLUME}",
        mountpoint="C:\\",
        fstype="NTFS",
    )

    usage = SimpleNamespace(
        total=1000,
        used=600,
        free=400,
        percent=60.0,
    )

    monkeypatch.setattr(
        worker_module.psutil,
        "disk_partitions",
        lambda all=False: [partition],
    )
    monkeypatch.setattr(
        worker_module.psutil,
        "disk_usage",
        lambda mount_point: usage,
    )

    instance = DiskMonitoringService(sampling_interval=0.5)

    result = instance.start()
    assert result.accepted is True

    try:
        assert wait_for_condition(
            qt_app,
            lambda: (
                instance.get_last_successful_measurement() is not None
            ),
            timeout=3.0,
        )

        measurement = instance.get_last_successful_measurement()

        assert len(measurement.volumes) == 1
        assert measurement.volume_errors == ()

        volume = measurement.volumes[0]

        assert volume.device == partition.device
        assert volume.mount_point == partition.mountpoint
        assert volume.filesystem == "NTFS"
        assert volume.total_bytes == 1000
        assert volume.used_bytes == 600
        assert volume.free_bytes == 400
        assert volume.percent == 60.0

        assert volume.volume_id == (
            f"{partition.device}::{partition.mountpoint}"
        )

        assert instance.get_measurement_status() == (
            DiskMeasurementStatus.AVAILABLE
        )

    finally:
        instance.stop()

        assert wait_for_condition(
            qt_app,
            lambda: (
                instance.get_worker_state() == DiskWorkerState.STOPPED
            ),
            timeout=3.0,
        )

        assert instance._worker_thread is None
