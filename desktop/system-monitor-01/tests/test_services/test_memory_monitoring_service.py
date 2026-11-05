import threading
import time
from datetime import datetime, timezone
from uuid import UUID

import pytest

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from system_monitor.models import (
    MemoryError,
    MemoryMeasurement,
    MemoryMeasurementStatus,
    MemoryStartResult,
    MemoryStopResult,
    MemoryConfigurationResult,
    MemoryWorkerState,
)

from system_monitor.services import memory_monitoring_service as service_module
from system_monitor.services.memory_monitoring_service import (
    MemoryMonitoringService,
)


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
            raise RuntimeError(
                "Simulated worker reconfiguration failure."
            )

        self.sampling_interval = seconds

        if self.reconfigure_event is not None:
            self.reconfigure_event.set()


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

        # Deliberately ignore the stop event.
        self.release.wait(timeout=10)


class StartupStallingFakeWorker(FakeWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(self):
        self.entered.set()

        # Deliberately never complete the startup handshake.
        self.release.wait(timeout=10)


@pytest.fixture(autouse=True)
def reset_fake_workers():
    FakeWorker.instances.clear()
    yield
    FakeWorker.instances.clear()


@pytest.fixture
def service(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        FakeWorker,
    )

    instance = MemoryMonitoringService()

    yield instance

    worker_thread = instance._worker_thread

    if worker_thread is not None:
        if worker_thread.is_alive():
            instance.stop()
            worker_thread.join(timeout=2)

        qt_app.processEvents()
        qt_app.processEvents()

        if worker_thread.is_alive():
            raise AssertionError(
                "Memory monitoring worker was not cleaned up."
            )

def make_measurement(
    *,
    total_bytes=16_000_000_000,
    used_bytes=8_000_000_000,
    available_bytes=8_000_000_000,
    free_bytes=4_000_000_000,
    percent=50.0,
    swap_total_bytes=4_000_000_000,
    swap_used_bytes=1_000_000_000,
    swap_free_bytes=3_000_000_000,
    swap_percent=25.0,
    sampling_interval=1.0,
):
    now = datetime.now(timezone.utc)

    return MemoryMeasurement(
        total_bytes=total_bytes,
        used_bytes=used_bytes,
        available_bytes=available_bytes,
        free_bytes=free_bytes,
        percent=percent,
        swap_total_bytes=swap_total_bytes,
        swap_used_bytes=swap_used_bytes,
        swap_free_bytes=swap_free_bytes,
        swap_percent=swap_percent,
        sampling_interval=sampling_interval,
        started_at=now,
        completed_at=now,
    )


def test_service_initial_state(service):
    assert service.get_worker_state() == MemoryWorkerState.STOPPED
    assert (
        service.get_measurement_status()
        == MemoryMeasurementStatus.UNAVAILABLE
    )
    assert service.get_last_successful_measurement() is None
    assert service.get_measurement_error() is None
    assert service.get_worker_error() is None
    assert service.get_consecutive_failures() == 0
    assert service.get_sampling_interval() == 1.0
    assert service.get_measurement_freshness().value == "NO_DATA"
    assert service.get_last_successful_age() is None


@pytest.mark.parametrize(
    "interval",
    [0.5, 1.0, 5.0, 60.0],
)
def test_service_accepts_valid_sampling_intervals(service, interval):
    result = service.set_sampling_interval(interval)

    assert isinstance(result, MemoryConfigurationResult)
    assert result.accepted is True
    assert result.sampling_interval == interval
    assert service.get_sampling_interval() == interval


@pytest.mark.parametrize(
    "interval",
    [
        0.49,
        60.01,
        0,
        -1,
        True,
        False,
        "1",
        None,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_service_rejects_invalid_sampling_intervals(service, interval):
    previous_interval = service.get_sampling_interval()

    result = service.set_sampling_interval(interval)

    assert isinstance(result, MemoryConfigurationResult)
    assert result.accepted is False
    assert service.get_sampling_interval() == previous_interval


def test_service_publishes_current_state(service, qt_app):
    published = []
    service.current_state_published.connect(published.append)

    service.publish_current_state()
    process_events(qt_app)

    assert len(published) == 1
    assert published[0].worker_state == MemoryWorkerState.STOPPED

def test_service_starts_worker(service, qt_app):
    result = service.start()

    assert isinstance(result, MemoryStartResult)
    assert result.accepted is True
    assert service.get_worker_state() == MemoryWorkerState.STARTING

    process_events(qt_app, 100)

    assert service.get_worker_state() == MemoryWorkerState.RUNNING
    assert len(FakeWorker.instances) == 1


def test_service_assigns_valid_session_id(service, qt_app):
    service.start()

    assert len(FakeWorker.instances) == 1

    worker = FakeWorker.instances[0]

    assert isinstance(worker.session_id, UUID)
    assert str(worker.session_id)


def test_service_does_not_start_duplicate_worker(service, qt_app):
    first_result = service.start()
    second_result = service.start()

    assert first_result.accepted is True
    assert second_result.accepted is True
    assert first_result.worker_state == MemoryWorkerState.STARTING
    assert second_result.worker_state == MemoryWorkerState.STARTING
    assert len(FakeWorker.instances) == 1

    process_events(qt_app, 100)

    third_result = service.start()

    assert third_result.accepted is True
    assert third_result.worker_state == MemoryWorkerState.RUNNING
    assert len(FakeWorker.instances) == 1


def test_service_stops_worker(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    result = service.stop()

    assert isinstance(result, MemoryStopResult)
    assert result.success is False
    assert result.worker_state == MemoryWorkerState.STOPPING

    process_events(qt_app, 200)

    assert service.get_worker_state() == MemoryWorkerState.STOPPED
    assert service._worker_thread is None
    assert service._worker is None


def test_service_start_stop_start_uses_new_session(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    first_session_id = FakeWorker.instances[0].session_id

    service.stop()
    process_events(qt_app, 200)

    service.start()

    assert len(FakeWorker.instances) == 2

    second_session_id = FakeWorker.instances[1].session_id

    assert first_session_id != second_session_id

    process_events(qt_app, 100)

    assert service.get_worker_state() == MemoryWorkerState.RUNNING

def test_service_accepts_successful_memory_measurement(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    measurement = make_measurement()

    worker.on_measurement(measurement)
    process_events(qt_app, 100)

    assert service.get_last_successful_measurement() == measurement
    assert service.get_measurement_status() == MemoryMeasurementStatus.AVAILABLE
    assert service.get_measurement_error() is None
    assert service.get_consecutive_failures() == 0


def test_service_emits_measurement_updated_signal(service, qt_app):
    received = []
    service.measurement_updated.connect(received.append)

    service.start()
    process_events(qt_app, 100)

    measurement = make_measurement()
    FakeWorker.instances[0].on_measurement(measurement)

    process_events(qt_app, 100)

    assert received == [measurement]


def test_service_updates_successful_measurement_atomically(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    first_measurement = make_measurement(used_bytes=7_000_000_000)
    second_measurement = make_measurement(used_bytes=9_000_000_000)

    worker = FakeWorker.instances[0]

    worker.on_measurement(first_measurement)
    process_events(qt_app, 100)

    first_snapshot = service._read_snapshot()

    worker.on_measurement(second_measurement)
    process_events(qt_app, 100)

    second_snapshot = service._read_snapshot()

    assert first_snapshot.last_successful_measurement == first_measurement
    assert second_snapshot.last_successful_measurement == second_measurement
    assert second_snapshot.revision > first_snapshot.revision


def test_service_ignores_measurement_from_stale_session(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    measurement = make_measurement()

    stale_session_id = UUID(int=0)

    service._worker_measurement_received.emit(
        stale_session_id,
        measurement,
    )
    process_events(qt_app, 100)

    assert service.get_last_successful_measurement() is None

def test_service_records_measurement_failure(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]

    worker.on_measurement_failure(
        "MEMORY_COLLECTION_FAILED",
        "Simulated memory collection failure.",
    )
    process_events(qt_app, 100)

    error = service.get_measurement_error()

    assert isinstance(error, MemoryError)
    assert error.error_code == "MEMORY_COLLECTION_FAILED"
    assert "Simulated memory collection failure." in error.message
    assert service.get_measurement_status() == MemoryMeasurementStatus.UNAVAILABLE
    assert service.get_consecutive_failures() == 1


def test_service_preserves_last_successful_measurement_after_failure(
    service,
    qt_app,
):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    measurement = make_measurement()

    worker.on_measurement(measurement)
    process_events(qt_app, 100)

    worker.on_measurement_failure(
        "MEMORY_COLLECTION_FAILED",
        "Simulated collection failure.",
    )
    process_events(qt_app, 100)

    assert service.get_last_successful_measurement() == measurement
    assert service.get_measurement_status() == MemoryMeasurementStatus.UNAVAILABLE
    assert service.get_measurement_error() is not None


def test_service_recovers_after_measurement_failure(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]

    worker.on_measurement_failure(
        "MEMORY_COLLECTION_FAILED",
        "Temporary failure.",
    )
    process_events(qt_app, 100)

    assert service.get_consecutive_failures() == 1

    measurement = make_measurement(used_bytes=9_000_000_000)

    worker.on_measurement(measurement)
    process_events(qt_app, 100)

    assert service.get_last_successful_measurement() == measurement
    assert service.get_measurement_status() == MemoryMeasurementStatus.AVAILABLE
    assert service.get_measurement_error() is None
    assert service.get_consecutive_failures() == 0


def wait_for_condition(app, condition, timeout=2.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        app.processEvents()

        if condition():
            return True

        time.sleep(0.01)

    app.processEvents()
    return condition()


def test_service_stops_real_worker_thread(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        BlockingFakeWorker,
    )

    instance = MemoryMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    stop_result = instance.stop()

    assert stop_result.success is False
    assert stop_result.worker_state == MemoryWorkerState.STOPPING

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.STOPPED,
    )

    assert instance._worker_thread is None
    assert instance._worker is None
    assert instance._session_id is None


def test_service_retains_worker_after_shutdown_timeout(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        UncooperativeFakeWorker,
    )

    monkeypatch.setattr(
        MemoryMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.1,
    )

    instance = MemoryMonitoringService()
    instance.start()

    worker = UncooperativeFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.FAILED,
    )

    assert (
        instance.get_worker_error().error_code
        == "MEMORY_SHUTDOWN_TIMEOUT"
    )

    # The still-running thread must remain tracked.
    assert instance._worker_thread is not None
    assert instance._worker_thread.is_alive()

    # Release the worker to prevent a non-daemon thread leak.
    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: not instance._worker_thread.is_alive(),
    )

    # Retry cleanup after thread termination.
    retry_result = instance.stop()

    assert retry_result.success is True
    assert instance.get_worker_state() == MemoryWorkerState.STOPPED
    assert instance._worker_thread is None


def test_service_startup_timeout_preserves_error_and_cleans_worker(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        MemoryMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        MemoryMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    instance = MemoryMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = StartupStallingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance.get_worker_state() == MemoryWorkerState.FAILED
            and instance.get_worker_error() is not None
        ),
    )

    assert (
        instance.get_worker_error().error_code
        == "MEMORY_STARTUP_TIMEOUT"
    )
    assert instance._startup_cleanup_pending is True
    assert instance._worker_thread is not None
    assert instance._worker_thread.is_alive()

    # A replacement worker must not start while the old worker is alive.
    rejected = instance.start()

    assert rejected.accepted is False
    assert len(StartupStallingFakeWorker.instances) == 1

    # Allow the original worker to terminate.
    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is None
            and not instance._startup_cleanup_pending
        ),
    )

    assert instance.get_worker_state() == MemoryWorkerState.FAILED
    assert (
        instance.get_worker_error().error_code
        == "MEMORY_STARTUP_TIMEOUT"
    )

    # Restart is allowed after cleanup.
    restarted = instance.start()

    assert restarted.accepted is True
    assert len(StartupStallingFakeWorker.instances) == 2

    # Clean up the restarted worker.
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

    assert instance.get_worker_state() == MemoryWorkerState.FAILED
    assert (
        instance.get_worker_error().error_code
        == "MEMORY_STARTUP_TIMEOUT"
    )


def test_concurrent_stop_requests_share_one_shutdown_operation(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        BlockingFakeWorker,
    )

    instance = MemoryMonitoringService()
    instance.start()

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    first_result = instance.stop()
    original_deadline = instance._shutdown_deadline

    assert first_result.worker_state == MemoryWorkerState.STOPPING
    assert original_deadline is not None

    second_result = instance.stop()
    third_result = instance.stop()

    assert second_result.success is False
    assert third_result.success is False
    assert second_result.worker_state == MemoryWorkerState.STOPPING
    assert third_result.worker_state == MemoryWorkerState.STOPPING

    assert instance._shutdown_deadline == original_deadline
    assert instance._pending_stop is True
    assert instance.get_worker_state() == MemoryWorkerState.STOPPING

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.STOPPED,
    )

    assert instance._worker_thread is None
    assert instance._pending_stop is False


def test_stop_during_startup_cleanup_preserves_startup_timeout(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        MemoryMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        MemoryMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    instance = MemoryMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = StartupStallingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance.get_worker_state() == MemoryWorkerState.FAILED
            and instance._startup_cleanup_pending
        ),
    )

    startup_error = instance.get_worker_error()

    assert startup_error is not None
    assert startup_error.error_code == "MEMORY_STARTUP_TIMEOUT"

    stop_result = instance.stop()

    assert stop_result.success is False
    assert stop_result.worker_state == MemoryWorkerState.FAILED

    assert instance.get_worker_state() == MemoryWorkerState.FAILED
    assert instance.get_worker_error() == startup_error
    assert instance._startup_cleanup_pending is True

    # Release the worker so startup cleanup can finish.
    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is None
            and not instance._startup_cleanup_pending
        ),
    )

    assert instance.get_worker_state() == MemoryWorkerState.FAILED
    assert instance.get_worker_error() == startup_error


def test_service_ignores_stale_callbacks_after_shutdown(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        FakeWorker,
    )

    instance = MemoryMonitoringService()

    first_start = instance.start()
    assert first_start.accepted is True

    first_worker = FakeWorker.instances[0]
    first_session_id = instance._session_id

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    # Shut down the first session through the service.
    stop_result = instance.stop()

    assert stop_result.success is False
    assert stop_result.worker_state == MemoryWorkerState.STOPPING

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.STOPPED,
    )

    assert instance._worker_thread is None

    # Start a new session.
    second_start = instance.start()
    assert second_start.accepted is True

    second_worker = FakeWorker.instances[1]
    second_session_id = instance._session_id

    assert second_session_id != first_session_id

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    current_measurement = make_measurement(
        used_bytes=6 * 1024**3,
    )

    instance._handle_worker_measurement(
        second_session_id,
        current_measurement,
    )

    assert (
        instance.get_last_successful_measurement()
        == current_measurement
    )

    previous_worker_state = instance.get_worker_state()
    previous_worker_error = instance.get_worker_error()

    # Simulate a delayed measurement from the old session.
    stale_measurement = make_measurement(
        used_bytes=12 * 1024**3,
    )

    instance._handle_worker_measurement(
        first_session_id,
        stale_measurement,
    )

    # Simulate a delayed worker failure from the old session.
    instance._handle_worker_failure(first_session_id)

    assert (
        instance.get_last_successful_measurement()
        == current_measurement
    )
    assert instance.get_worker_state() == previous_worker_state
    assert instance.get_worker_error() == previous_worker_error

    # Clean up the active session.
    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.STOPPED,
    )

    assert instance._worker_thread is None


def test_service_reconfigures_running_worker_sampling_interval(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        FakeWorker,
    )

    instance = MemoryMonitoringService()

    result = instance.start()
    assert result.accepted is True

    worker = FakeWorker.instances[0]

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    configuration = instance.set_sampling_interval(2.5)

    assert isinstance(configuration, MemoryConfigurationResult)
    assert configuration.accepted is True
    assert configuration.sampling_interval == 2.5
    assert configuration.worker_state == MemoryWorkerState.RUNNING

    assert worker.sampling_interval == 2.5
    assert instance.get_sampling_interval() == 2.5

    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.STOPPED,
    )

    assert instance._worker_thread is None


def test_service_preserves_configuration_when_worker_reconfiguration_fails(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        FakeWorker,
    )

    instance = MemoryMonitoringService()

    result = instance.start()
    assert result.accepted is True

    worker = FakeWorker.instances[0]

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    previous_interval = instance.get_sampling_interval()
    worker.raise_on_reconfigure = True

    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == MemoryWorkerState.RUNNING

    assert configuration.error is not None
    assert (
        configuration.error.error_code
        == "MEMORY_CONFIGURATION_FAILED"
    )

    assert instance.get_sampling_interval() == previous_interval
    assert worker.sampling_interval == previous_interval

    instance.stop()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.STOPPED,
    )

    assert instance._worker_thread is None


def test_service_rejects_configuration_change_while_stopping(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        BlockingFakeWorker,
    )

    instance = MemoryMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    stop_result = instance.stop()

    assert stop_result.success is False
    assert stop_result.worker_state == MemoryWorkerState.STOPPING

    previous_interval = instance.get_sampling_interval()

    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == MemoryWorkerState.STOPPING

    assert configuration.error is not None
    assert (
        configuration.error.error_code
        == "MEMORY_CONFIGURATION_REJECTED"
    )

    assert instance.get_sampling_interval() == previous_interval
    assert worker.sampling_interval == previous_interval

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.STOPPED,
    )

    assert instance._worker_thread is None


def test_service_rejects_configuration_during_startup_cleanup(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        MemoryMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        MemoryMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    instance = MemoryMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = StartupStallingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance.get_worker_state() == MemoryWorkerState.FAILED
            and instance._startup_cleanup_pending
        ),
    )

    previous_interval = instance.get_sampling_interval()

    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == MemoryWorkerState.FAILED

    assert configuration.error is not None
    assert (
        configuration.error.error_code
        == "MEMORY_CONFIGURATION_REJECTED"
    )

    assert instance.get_sampling_interval() == previous_interval

    # Allow the original worker to terminate.
    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is None
            and not instance._startup_cleanup_pending
        ),
    )

    assert instance.get_worker_state() == MemoryWorkerState.FAILED
    assert instance.get_sampling_interval() == previous_interval


def test_service_rejects_configuration_while_failed_worker_is_alive(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "MemoryMonitoringWorker",
        UncooperativeFakeWorker,
    )
    monkeypatch.setattr(
        MemoryMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.1,
    )

    instance = MemoryMonitoringService()
    result = instance.start()

    assert result.accepted is True

    worker = UncooperativeFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: instance.get_worker_state() == MemoryWorkerState.RUNNING,
    )

    # Simulate an unexpected worker failure.
    instance._handle_worker_failure(instance._session_id)

    assert instance.get_worker_state() == MemoryWorkerState.FAILED
    assert instance.get_worker_error().error_code == "MEMORY_WORKER_FAILED"

    previous_interval = instance.get_sampling_interval()

    configuration = instance.set_sampling_interval(3.0)

    assert configuration.accepted is False
    assert configuration.sampling_interval == previous_interval
    assert configuration.worker_state == MemoryWorkerState.FAILED

    assert configuration.error is not None
    assert (
        configuration.error.error_code
        == "MEMORY_CONFIGURATION_REJECTED"
    )

    assert instance.get_sampling_interval() == previous_interval

    # Release the uncooperative worker.
    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            instance._worker_thread is not None
            and not instance._worker_thread.is_alive()
        ),
    )

    # Explicitly complete cleanup after the worker terminates.
    stop_result = instance.stop()

    assert stop_result.success is True
    assert stop_result.worker_state == MemoryWorkerState.STOPPED

    assert instance._worker_thread is None
    assert instance.get_worker_state() == MemoryWorkerState.STOPPED
