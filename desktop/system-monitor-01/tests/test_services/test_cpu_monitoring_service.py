import time
import threading
from datetime import datetime, timezone
from uuid import UUID

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from system_monitor.models import (
    CpuMeasurement,
    CpuMeasurementStatus,
    CpuWorkerState,
    StartResult,
)
from system_monitor.services import cpu_monitoring_service as service_module
from system_monitor.services.cpu_monitoring_service import (
    CpuMonitoringService,
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
        self.stop_event = stop_event
        self.reconfigure_event = reconfigure_event
        self.on_started = on_started

        self.__class__.instances.append(self)

    def run(self):
        if self.on_started:
            self.on_started()

    def set_sampling_interval(self, seconds):
        if getattr(self, "raise_on_reconfigure", False):
            raise RuntimeError("Simulated worker reconfiguration failure.")

        self.sampling_interval = seconds
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
        "CpuMonitoringWorker",
        FakeWorker,
    )

    return CpuMonitoringService()


def test_service_initial_state(service):
    assert service.get_worker_state() == CpuWorkerState.STOPPED

    assert (
        service.get_measurement_status()
        == CpuMeasurementStatus.UNAVAILABLE
    )

    assert service.get_measurement_freshness().value == "NO_DATA"
    assert service.get_last_successful_measurement() is None
    assert service.get_measurement_error() is None
    assert service.get_worker_error() is None
    assert service.get_consecutive_failures() == 0
    assert service.get_sampling_interval() == 1.0

    assert service._read_snapshot().revision == 0


def test_service_rejects_invalid_sampling_interval():
    with pytest.raises((TypeError, ValueError)):
        CpuMonitoringService(sampling_interval=0.1)


def test_service_start_is_non_blocking_and_accepted(service):
    result = service.start()

    assert result.accepted is True
    assert result.worker_state == CpuWorkerState.STARTING
    assert service.get_worker_state() == CpuWorkerState.STARTING


def test_service_successful_startup(qt_app, service):
    result = service.start()

    assert result.accepted is True

    process_events(qt_app, 20)

    assert service.get_worker_state() == CpuWorkerState.RUNNING
    assert (
        service.get_measurement_status()
        == CpuMeasurementStatus.INITIALIZING
    )


def test_service_start_is_idempotent(qt_app, service):
    first = service.start()
    second = service.start()

    assert first.accepted is True
    assert second.accepted is True
    assert first.worker_state == CpuWorkerState.STARTING
    assert second.worker_state == CpuWorkerState.STARTING
    assert len(FakeWorker.instances) == 1

    process_events(qt_app, 20)

    third = service.start()

    assert third.accepted is True
    assert third.worker_state == CpuWorkerState.RUNNING
    assert len(FakeWorker.instances) == 1


def test_service_uses_uuid_session_id(service):
    service.start()

    worker = FakeWorker.instances[0]

    assert isinstance(worker.session_id, UUID)


def test_service_worker_startup_clears_startup_timer(qt_app, service):
    service.start()

    assert service._startup_timer.isActive()

    process_events(qt_app, 20)

    assert not service._startup_timer.isActive()
    assert service._startup_deadline is None


def test_service_worker_failure_updates_state(qt_app, service):
    service.start()

    worker = FakeWorker.instances[0]

    process_events(qt_app, 20)

    worker.on_worker_failure()

    process_events(qt_app, 20)

    assert service.get_worker_state() == CpuWorkerState.FAILED
    assert service.get_worker_error() is not None
    assert service.get_worker_error().error_code == "CPU_WORKER_FAILED"


def test_service_ignores_stale_worker_session(qt_app, service):
    service.start()

    worker = FakeWorker.instances[0]

    service._session_id = UUID(
        "00000000-0000-0000-0000-000000000001"
    )

    worker.on_started()

    process_events(qt_app, 20)

    assert service.get_worker_state() == CpuWorkerState.STARTING


def test_service_ignores_stale_worker_failure(qt_app, service):
    service.start()

    worker = FakeWorker.instances[0]

    process_events(qt_app, 20)

    assert service.get_worker_state() == CpuWorkerState.RUNNING

    service._session_id = UUID(
        "00000000-0000-0000-0000-000000000001"
    )

    worker.on_worker_failure()

    process_events(qt_app, 20)

    assert service.get_worker_state() == CpuWorkerState.RUNNING
    assert service.get_worker_error() is None


def test_service_snapshot_revision_increments_on_state_change(service):
    initial_revision = service._read_snapshot().revision

    service.start()

    assert service._read_snapshot().revision == initial_revision + 1


def test_service_publish_current_state_does_not_mutate_snapshot(
    qt_app,
    service,
):
    published = []

    service.current_state_published.connect(published.append)

    before = service._read_snapshot()
    result = service.publish_current_state()

    process_events(qt_app, 20)

    after = service._read_snapshot()

    assert result == before
    assert after == before
    assert len(published) == 1
    assert published[0] == before


def test_service_worker_measurement_callback_is_queued(qt_app, service):
    service.start()

    worker = FakeWorker.instances[0]

    process_events(qt_app, 20)

    worker.on_measurement_failure(
        "CPU_MEASUREMENT_FAILED",
        "Temporary test failure.",
    )

    assert service.get_measurement_error() is None

    process_events(qt_app, 20)

    assert service.get_measurement_error() is not None
    assert (
        service.get_measurement_error().error_code
        == "CPU_MEASUREMENT_FAILED"
    )


def test_service_measurement_failure_preserves_last_successful_data(
    qt_app,
    service,
):
    service.start()

    worker = FakeWorker.instances[0]

    process_events(qt_app, 20)

    worker.on_measurement_failure(
        "CPU_MEASUREMENT_FAILED",
        "Temporary failure.",
    )

    process_events(qt_app, 20)

    assert service.get_last_successful_measurement() is None
    assert service.get_measurement_freshness().value == "NO_DATA"


def test_service_topology_change_preserves_measurement_and_sets_initializing(
    qt_app,
    service,
):
    service.start()

    worker = FakeWorker.instances[0]

    process_events(qt_app, 20)

    now = datetime.now(timezone.utc)

    measurement = CpuMeasurement(
        overall_percent=42.0,
        per_cpu_percent=(42.0,),
        logical_cpu_count=1,
        sampling_interval=1.0,
        started_at=now,
        completed_at=now,
    )

    previous_monotonic = time.monotonic()

    service._commit_snapshot(
        measurement_status=CpuMeasurementStatus.AVAILABLE,
        last_successful_measurement=measurement,
        last_successful_monotonic=previous_monotonic,
    )

    worker.on_measurement_failure(
        "CPU_TOPOLOGY_CHANGED",
        "Logical CPU topology changed.",
    )

    process_events(qt_app, 20)

    current = service._read_snapshot()

    assert (
        current.measurement_status
        == CpuMeasurementStatus.INITIALIZING
    )
    assert current.last_successful_measurement is measurement
    assert current.last_successful_monotonic == previous_monotonic
    assert current.consecutive_failures == 1
    assert service.get_measurement_freshness().value == "STALE"


def test_service_worker_failure_does_not_clear_last_successful_data(
    qt_app,
    service,
):
    service.start()

    worker = FakeWorker.instances[0]

    process_events(qt_app, 20)

    previous = service._read_snapshot()

    worker.on_worker_failure()

    process_events(qt_app, 20)

    current = service._read_snapshot()

    assert current.last_successful_measurement == (
        previous.last_successful_measurement
    )
    assert current.last_successful_monotonic == (
        previous.last_successful_monotonic
    )


def test_service_signal_emits_only_on_state_change(qt_app, service):
    states = []

    service.worker_state_changed.connect(states.append)

    service.start()

    process_events(qt_app, 20)

    assert states == [
        CpuWorkerState.STARTING,
        CpuWorkerState.RUNNING,
    ]

    service.start()

    process_events(qt_app, 20)

    assert states == [
        CpuWorkerState.STARTING,
        CpuWorkerState.RUNNING,
    ]


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
        "CpuMonitoringWorker",
        BlockingFakeWorker,
    )

    service = CpuMonitoringService()
    result = service.start()

    assert result.accepted is True

    worker = BlockingFakeWorker.instances[0]

    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    stop_result = service.stop()

    assert stop_result.success is False
    assert stop_result.worker_state == CpuWorkerState.STOPPING

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.STOPPED,
    )

    assert service._worker_thread is None
    assert service._worker is None
    assert service._session_id is None

def test_service_retains_worker_after_shutdown_timeout(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        UncooperativeFakeWorker,
    )

    monkeypatch.setattr(
        CpuMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.1,
    )

    service = CpuMonitoringService()
    service.start()

    worker = UncooperativeFakeWorker.instances[0]

    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    service.stop()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.FAILED,
    )

    assert service.get_worker_error().error_code == "CPU_SHUTDOWN_TIMEOUT"

    # The still-running thread must remain tracked.
    assert service._worker_thread is not None
    assert service._worker_thread.is_alive()

    # Release the worker so the test does not leak a non-daemon thread.
    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: not service._worker_thread.is_alive(),
    )

    # Retry cleanup after termination is confirmed.
    retry_result = service.stop()

    assert retry_result.success is True
    assert service.get_worker_state() == CpuWorkerState.STOPPED
    assert service._worker_thread is None


class StartupStallingFakeWorker(FakeWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entered = threading.Event()
        self.release = threading.Event()

    def run(self):
        self.entered.set()

        # Deliberately never complete the startup handshake.
        self.release.wait(timeout=10)


def test_service_startup_timeout_preserves_error_and_cleans_worker(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        CpuMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        CpuMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    service = CpuMonitoringService()
    result = service.start()

    assert result.accepted is True

    worker = StartupStallingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: (
            service.get_worker_state() == CpuWorkerState.FAILED
            and service.get_worker_error() is not None
        ),
    )

    assert service.get_worker_error().error_code == "CPU_STARTUP_TIMEOUT"
    assert service._startup_cleanup_pending is True
    assert service._worker_thread is not None
    assert service._worker_thread.is_alive()

    # A late failure callback must not replace the startup-timeout error.
    worker.on_worker_failure()
    qt_app.processEvents()

    assert service.get_worker_error().error_code == "CPU_STARTUP_TIMEOUT"

    # A replacement worker must not start while the old worker is alive.
    rejected = service.start()

    assert rejected.accepted is False
    assert len(StartupStallingFakeWorker.instances) == 1

    # Allow the original thread to terminate.
    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: (
            service._worker_thread is None
            and not service._startup_cleanup_pending
        ),
    )

    assert service.get_worker_state() == CpuWorkerState.FAILED
    assert service.get_worker_error().error_code == "CPU_STARTUP_TIMEOUT"

    # Once cleanup is complete, a new startup may be accepted.
    restarted = service.start()

    assert restarted.accepted is True
    assert len(StartupStallingFakeWorker.instances) == 2

    # Prevent a non-daemon test thread from being left behind.
    restarted_worker = StartupStallingFakeWorker.instances[-1]
    restarted_thread = service._worker_thread

    restarted_worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: not restarted_thread.is_alive(),
    )

    # The startup timer must subsequently complete cleanup.
    assert wait_for_condition(
        qt_app,
        lambda: (
            service._worker_thread is None
            and not service._startup_cleanup_pending
        ),
    )

    assert service.get_worker_state() == CpuWorkerState.FAILED
    assert service.get_worker_error().error_code == "CPU_STARTUP_TIMEOUT"

def test_concurrent_stop_requests_share_one_shutdown_operation(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        BlockingFakeWorker,
    )

    service = CpuMonitoringService()
    service.start()

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    first_result = service.stop()
    original_deadline = service._shutdown_deadline

    assert first_result.worker_state == CpuWorkerState.STOPPING
    assert original_deadline is not None

    second_result = service.stop()
    third_result = service.stop()

    assert second_result.success is False
    assert third_result.success is False
    assert second_result.worker_state == CpuWorkerState.STOPPING
    assert third_result.worker_state == CpuWorkerState.STOPPING

    # Repeated requests must not create a new deadline.
    assert service._shutdown_deadline == original_deadline
    assert service._pending_stop is True
    assert service.get_worker_state() == CpuWorkerState.STOPPING

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.STOPPED,
    )

    assert service._worker_thread is None
    assert service._pending_stop is False


def test_stop_during_startup_cleanup_preserves_startup_timeout(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        CpuMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )

    service = CpuMonitoringService()
    service.start()

    worker = StartupStallingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service._startup_cleanup_pending,
    )

    original_deadline = service._shutdown_deadline
    original_error = service.get_worker_error()

    result = service.stop()

    assert result.success is False
    assert result.worker_state == CpuWorkerState.FAILED
    assert result.error == original_error
    assert service._shutdown_deadline == original_deadline
    assert service.get_worker_state() == CpuWorkerState.FAILED
    assert service.get_worker_error().error_code == "CPU_STARTUP_TIMEOUT"

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: service._worker_thread is None,
    )


@pytest.mark.parametrize(
    "interval",
    [0, -1, 0.49, 60.01, True, "2", None, float("nan"), float("inf"), float("-inf")],
)
def test_service_rejects_invalid_configuration_interval(service, interval):
    previous = service._read_snapshot()

    result = service.set_sampling_interval(interval)

    assert result.accepted is False
    assert result.sampling_interval == previous.sampling_interval
    assert result.worker_state == previous.worker_state
    assert result.error is not None
    assert result.error.error_code == "CPU_INVALID_SAMPLING_INTERVAL"
    assert service._read_snapshot() == previous


def test_service_updates_interval_while_stopped(service):
    previous_revision = service._read_snapshot().revision

    result = service.set_sampling_interval(2.5)

    assert result.accepted is True
    assert result.sampling_interval == 2.5
    assert result.worker_state == CpuWorkerState.STOPPED
    assert result.error is None
    assert service.get_sampling_interval() == 2.5
    assert service._sampling_interval == 2.5
    assert service._read_snapshot().revision == previous_revision + 1


def test_service_accepts_unchanged_interval_without_revision_change(service):
    previous = service._read_snapshot()

    result = service.set_sampling_interval(1.0)

    assert result.accepted is True
    assert result.sampling_interval == 1.0
    assert result.error is None
    assert service._read_snapshot() == previous


def test_service_updates_interval_while_running(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        BlockingFakeWorker,
    )

    service = CpuMonitoringService()
    service.start()

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    result = service.set_sampling_interval(2.5)

    assert result.accepted is True
    assert result.sampling_interval == 2.5
    assert result.worker_state == CpuWorkerState.RUNNING
    assert worker.sampling_interval == 2.5
    assert worker.reconfigure_event.is_set()
    assert service.get_sampling_interval() == 2.5

    service.stop()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.STOPPED,
    )


def test_service_configuration_failure_preserves_previous_state(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        BlockingFakeWorker,
    )

    service = CpuMonitoringService()
    service.start()

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    worker.raise_on_reconfigure = True
    previous = service._read_snapshot()
    previous_interval = service.get_sampling_interval()

    result = service.set_sampling_interval(2.5)

    assert result.accepted is False
    assert result.error is not None
    assert result.error.error_code == "CPU_CONFIGURATION_FAILED"
    assert result.sampling_interval == previous_interval
    assert result.worker_state == previous.worker_state
    assert service._read_snapshot() == previous
    assert service.get_sampling_interval() == previous_interval

    service.stop()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.STOPPED,
    )


def test_service_rejects_configuration_when_worker_reference_missing(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        BlockingFakeWorker,
    )

    service = CpuMonitoringService()
    service.start()

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    previous = service._read_snapshot()
    previous_interval = service.get_sampling_interval()

    service._worker = None

    result = service.set_sampling_interval(2.5)

    assert result.accepted is False
    assert result.error is not None
    assert result.error.error_code == "CPU_CONFIGURATION_REJECTED"
    assert result.sampling_interval == previous_interval
    assert result.worker_state == previous.worker_state
    assert service._read_snapshot() == previous
    assert service.get_sampling_interval() == previous_interval

    service._worker = worker
    service.stop()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.STOPPED,
    )


def test_service_rejects_configuration_while_stopping(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        BlockingFakeWorker,
    )

    service = CpuMonitoringService()
    service.start()

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    service.stop()

    previous_interval = service.get_sampling_interval()
    result = service.set_sampling_interval(3.0)

    assert result.accepted is False
    assert result.sampling_interval == previous_interval
    assert result.worker_state == CpuWorkerState.STOPPING
    assert result.error is not None
    assert service.get_sampling_interval() == previous_interval

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.STOPPED,
    )


def test_service_rejects_configuration_when_failed_worker_is_alive(
    monkeypatch,
    qt_app,
):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        UncooperativeFakeWorker,
    )

    monkeypatch.setattr(
        CpuMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.1,
    )

    service = CpuMonitoringService()
    service.start()

    worker = UncooperativeFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    service.stop()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.FAILED,
    )

    previous_interval = service.get_sampling_interval()
    result = service.set_sampling_interval(3.0)

    assert result.accepted is False
    assert result.sampling_interval == previous_interval
    assert result.worker_state == CpuWorkerState.FAILED
    assert result.error is not None
    assert service._worker_thread.is_alive()

    worker.release.set()

    assert wait_for_condition(
        qt_app,
        lambda: not service._worker_thread.is_alive(),
    )

    cleanup = service.stop()

    assert cleanup.success is True
    assert service.get_worker_state() == CpuWorkerState.STOPPED


def test_service_configuration_preserves_last_successful_measurement(service):
    now = datetime.now(timezone.utc)

    measurement = CpuMeasurement(
        overall_percent=42.0,
        per_cpu_percent=(42.0,),
        logical_cpu_count=1,
        sampling_interval=1.0,
        started_at=now,
        completed_at=now,
    )

    previous_monotonic = time.monotonic()

    service._commit_snapshot(
        measurement_status=CpuMeasurementStatus.AVAILABLE,
        last_successful_measurement=measurement,
        last_successful_monotonic=previous_monotonic,
    )

    result = service.set_sampling_interval(2.0)
    updated = service._read_snapshot()

    assert result.accepted is True
    assert updated.last_successful_measurement is measurement
    assert updated.last_successful_monotonic == previous_monotonic
    assert updated.sampling_interval == 2.0

# ---------------------------------------------------------------------------
# Cross-thread public API dispatch
# ---------------------------------------------------------------------------


def run_in_thread(callback):
    """Run a callback in a Python thread and capture its result or exception."""
    outcome = {}
    finished = threading.Event()

    def target():
        try:
            outcome["result"] = callback()
        except BaseException as exc:
            outcome["error"] = exc
        finally:
            finished.set()

    thread = threading.Thread(target=target)
    thread.start()
    return thread, outcome, finished


def test_service_start_dispatches_from_non_owner_thread(qt_app, service):
    owner_thread = service._owner_thread
    caller_thread_id = []

    def invoke():
        caller_thread_id.append(threading.get_ident())
        return service.start()

    thread, outcome, finished = run_in_thread(invoke)

    assert wait_for_condition(qt_app, finished.is_set)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert "error" not in outcome
    assert caller_thread_id
    assert caller_thread_id[0] != threading.get_ident()
    assert outcome["result"].accepted is True
    assert outcome["result"].worker_state == CpuWorkerState.STARTING

    process_events(qt_app, 20)
    assert service.get_worker_state() == CpuWorkerState.RUNNING
    assert len(FakeWorker.instances) == 1


def test_service_sampling_interval_dispatches_from_non_owner_thread(
    qt_app,
    service,
):
    thread, outcome, finished = run_in_thread(
        lambda: service.set_sampling_interval(2.5)
    )

    assert wait_for_condition(qt_app, finished.is_set)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert "error" not in outcome
    result = outcome["result"]
    assert result.accepted is True
    assert result.sampling_interval == 2.5
    assert result.worker_state == CpuWorkerState.STOPPED
    assert service.get_sampling_interval() == 2.5


def test_service_stop_dispatches_from_non_owner_thread(monkeypatch, qt_app):
    monkeypatch.setattr(
        service_module,
        "CpuMonitoringWorker",
        BlockingFakeWorker,
    )
    service = CpuMonitoringService()
    assert service.start().accepted is True

    worker = BlockingFakeWorker.instances[0]
    assert worker.entered.wait(timeout=1)
    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.RUNNING,
    )

    thread, outcome, finished = run_in_thread(service.stop)

    assert wait_for_condition(qt_app, finished.is_set)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert "error" not in outcome
    result = outcome["result"]
    assert result.success is False
    assert result.worker_state == CpuWorkerState.STOPPING

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == CpuWorkerState.STOPPED,
    )
    assert service._worker_thread is None


def test_expired_queued_request_never_executes_later(
    monkeypatch,
    qt_app,
    service,
):
    monkeypatch.setattr(
        CpuMonitoringService,
        "REQUEST_DISPATCH_TIMEOUT_SECONDS",
        0.05,
    )
    executions = []

    def rejected_start():
        executions.append("executed")
        return StartResult(
            accepted=True,
            worker_state=CpuWorkerState.STARTING,
            error=None,
        )

    monkeypatch.setattr(
        service,
        "_start_on_owner_thread",
        rejected_start,
    )

    # Do not process Qt events until the calling thread has timed out.
    thread, outcome, finished = run_in_thread(service.start)
    assert finished.wait(timeout=1)
    thread.join(timeout=1)

    assert not thread.is_alive()
    assert "error" not in outcome
    result = outcome["result"]
    assert result.accepted is False
    assert result.error is not None
    assert result.error.error_code == "CPU_REQUEST_DISPATCH_TIMEOUT"
    assert executions == []

    # The queued Qt signal may now be delivered, but the expired request
    # must be ignored and must never invoke the owner-thread handler.
    process_events(qt_app, 20)
    assert executions == []
    assert service.get_worker_state() == CpuWorkerState.STOPPED


def test_started_dispatch_request_finishes_after_deadline(
    monkeypatch,
    qt_app,
    service,
):
    monkeypatch.setattr(
        CpuMonitoringService,
        "REQUEST_DISPATCH_TIMEOUT_SECONDS",
        0.05,
    )
    original_start = service._start_on_owner_thread
    callback_entered = threading.Event()
    release_callback = threading.Event()

    def delayed_start():
        callback_entered.set()
        assert release_callback.wait(timeout=2)
        return original_start()

    monkeypatch.setattr(
        service,
        "_start_on_owner_thread",
        delayed_start,
    )

    thread, outcome, finished = run_in_thread(service.start)

    # This helper pumps the Qt owner thread. The dispatched callback blocks
    # until the independent releaser thread releases it.
    releaser = threading.Thread(
        target=lambda: (
            callback_entered.wait(timeout=1),
            time.sleep(0.15),
            release_callback.set(),
        )
    )
    releaser.start()

    assert wait_for_condition(qt_app, finished.is_set, timeout=2)
    thread.join(timeout=1)
    releaser.join(timeout=1)

    assert not thread.is_alive()
    assert not releaser.is_alive()
    assert "error" not in outcome
    assert callback_entered.is_set()
    assert outcome["result"].accepted is True
    assert outcome["result"].worker_state == CpuWorkerState.STARTING
    assert service.get_worker_state() in {
        CpuWorkerState.STARTING,
        CpuWorkerState.RUNNING,
    }

    process_events(qt_app, 20)
    assert service.get_worker_state() == CpuWorkerState.RUNNING


def test_dispatched_request_executor_runs_callback_exactly_once(service):
    executions = []

    request = {
        "operation": "start",
        "callback": lambda: executions.append("called") or "result",
        "deadline": time.monotonic() + 1,
        "lock": threading.Lock(),
        "started_event": threading.Event(),
        "completed_event": threading.Event(),
        "started": False,
        "expired": False,
        "completed": False,
        "result": None,
        "error": None,
    }

    service._execute_dispatched_request(request)
    service._execute_dispatched_request(request)

    assert executions == ["called"]
    assert request["started"] is True
    assert request["completed"] is True
    assert request["result"] == "result"
    assert request["started_event"].is_set()
    assert request["completed_event"].is_set()
