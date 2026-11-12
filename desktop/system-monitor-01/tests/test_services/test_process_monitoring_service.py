import threading
import time
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QThread, QTimer

from system_monitor.models import (
    ProcessError,
    ProcessMeasurement,
    ProcessMeasurementFreshness,
    ProcessMeasurementStatus,
    ProcessSnapshot,
    ProcessWorkerState,
)
from system_monitor.services import process_monitoring_service as service_module
from system_monitor.services.process_monitoring_service import (
    ProcessMonitoringService,
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
        *,
        sampling_interval,
        on_measurement,
        on_measurement_failure,
        on_worker_failure,
        on_started=None,
        stop_event=None,
        reconfigure_event=None,
    ):
        self.sampling_interval = sampling_interval
        self.on_measurement = on_measurement
        self.on_measurement_failure = on_measurement_failure
        self.on_worker_failure = on_worker_failure
        self.on_started = on_started
        self.stop_event = stop_event or threading.Event()
        self.reconfigure_event = (
            reconfigure_event or threading.Event()
        )
        self.raise_on_reconfigure = False
        self.__class__.instances.append(self)

    def run(self):
        if self.on_started is not None:
            self.on_started()

        self.stop_event.wait()

    def set_sampling_interval(self, seconds):
        if self.raise_on_reconfigure:
            raise RuntimeError("Simulated reconfiguration failure.")

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
        "ProcessMonitoringWorker",
        FakeWorker,
    )

    instance = ProcessMonitoringService()
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
                "Process worker thread did not stop."
            )


def make_process(
    pid=100,
    name="test-process",
    cpu_percent=12.5,
    memory_bytes=1024 * 1024,
    status="running",
):
    return ProcessMeasurement(
        pid=pid,
        name=name,
        cpu_percent=cpu_percent,
        memory_bytes=memory_bytes,
        status=status,
        sampled_at=datetime.now(timezone.utc),
    )


def make_error(
    pid=200,
    error_code="PROCESS_ACCESS_DENIED",
):
    return ProcessError(
        error_code=error_code,
        message="Simulated process collection failure.",
        occurred_at=datetime.now(timezone.utc),
        pid=pid,
    )


def make_snapshot(
    processes=None,
    errors=None,
    sampling_interval=2.0,
):
    now = datetime.now(timezone.utc)

    return ProcessSnapshot(
        processes=tuple(processes or ()),
        process_errors=tuple(errors or ()),
        sampling_interval=sampling_interval,
        started_at=now,
        completed_at=now,
    )


def test_service_initial_state(service):
    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.STOPPED
    assert snapshot.measurement_status == ProcessMeasurementStatus.INITIALIZING
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is None
    assert snapshot.consecutive_failures == 0
    assert snapshot.sampling_interval == 2.0
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.NO_DATA


def test_service_updates_sampling_interval_while_stopped(service):
    result = service.set_sampling_interval(2.5)

    assert result.accepted is True
    assert result.sampling_interval == 2.5
    assert service.get_sampling_interval() == 2.5
    assert service._read_snapshot().sampling_interval == 2.5


@pytest.mark.parametrize("interval", [0.5, 1.0, 2.0, 30.0, 60.0])
def test_service_accepts_valid_sampling_intervals(service, interval):
    result = service.set_sampling_interval(interval)

    assert result.accepted is True
    assert result.sampling_interval == interval
    assert service.get_sampling_interval() == interval


@pytest.mark.parametrize(
    "interval",
    [0.0, 0.49, 60.01, -1.0, float("inf"), float("nan"), True, "2"],
)
def test_service_rejects_invalid_sampling_intervals(service, interval):
    result = service.set_sampling_interval(interval)

    assert result.accepted is False
    assert result.sampling_interval == 2.0
    assert service.get_sampling_interval() == 2.0
    assert service._read_snapshot().sampling_interval == 2.0


def test_service_publishes_current_state(service, qt_app):
    published = []
    service.current_state_published.connect(published.append)

    state = service.publish_current_state()

    assert state is service._read_snapshot()
    assert published == [state]


def test_service_starts_worker(service, qt_app):
    result = service.start()

    assert result.accepted is True

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.RUNNING,
    )

    assert len(FakeWorker.instances) == 1
    assert service._worker is FakeWorker.instances[0]
    assert service._worker_thread is not None
    assert service._worker_thread.is_alive()


def test_service_prevents_duplicate_start(service, qt_app):
    first_result = service.start()

    assert first_result.accepted is True

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.RUNNING,
    )

    second_result = service.start()

    assert second_result.accepted is True
    assert len(FakeWorker.instances) == 1
    assert service.get_worker_state() == ProcessWorkerState.RUNNING


def test_service_stops_worker(service, qt_app):
    service.start()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.RUNNING,
    )

    result = service.stop()

    assert result.success is False
    assert result.worker_state == ProcessWorkerState.STOPPING

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.STOPPED,
    )

    assert service._worker is None
    assert service._worker_thread is None


def test_service_can_restart_after_stop(service, qt_app):
    service.start()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.RUNNING,
    )

    service.stop()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.STOPPED,
    )

    result = service.start()

    assert result.accepted is True

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.RUNNING,
    )

    assert len(FakeWorker.instances) == 2


def wait_for_condition(app, condition, timeout=2.0):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        app.processEvents()

        if condition():
            return True

        time.sleep(0.01)

    app.processEvents()
    return condition()



def start_running_service(service, qt_app):
    result = service.start()
    assert result.accepted is True

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.RUNNING,
    )

    return service._session_id


def test_service_accepts_successful_process_inventory(service, qt_app):
    session_id = start_running_service(service, qt_app)
    measurement = make_snapshot(
        processes=[
            make_process(pid=100, name="explorer.exe"),
            make_process(pid=200, name="python.exe"),
        ]
    )

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.AVAILABLE
    assert snapshot.latest_measurement is measurement
    assert snapshot.last_successful_measurement is measurement
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.FRESH


def test_service_treats_empty_inventory_as_success(service, qt_app):
    session_id = start_running_service(service, qt_app)
    measurement = make_snapshot()

    assert measurement.is_empty is True
    assert measurement.is_fully_successful is True

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.AVAILABLE
    assert snapshot.latest_measurement is measurement
    assert snapshot.last_successful_measurement is measurement
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.FRESH


def test_service_classifies_mixed_inventory_as_partial(service, qt_app):
    session_id = start_running_service(service, qt_app)
    measurement = make_snapshot(
        processes=[make_process(pid=100)],
        errors=[make_error(pid=200)],
    )

    assert measurement.is_partial is True

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.PARTIAL
    assert snapshot.latest_measurement is measurement
    assert snapshot.last_successful_measurement is None
    assert snapshot.measurement_error.error_code == "PROCESS_ACCESS_DENIED"
    assert snapshot.measurement_error.pid == 200
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.NO_DATA


def test_service_classifies_error_only_inventory_as_unavailable(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)
    measurement = make_snapshot(
        errors=[make_error(pid=200)]
    )

    assert measurement.is_unavailable is True

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is measurement
    assert snapshot.last_successful_measurement is None
    assert snapshot.measurement_error.error_code == "PROCESS_ACCESS_DENIED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.NO_DATA


def test_service_preserves_last_successful_inventory_on_partial_result(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    successful = make_snapshot(
        processes=[make_process(pid=100)]
    )
    service._handle_worker_measurement(session_id, successful)

    previous_timestamp = service._read_snapshot().last_successful_monotonic

    partial = make_snapshot(
        processes=[make_process(pid=100), make_process(pid=300)],
        errors=[make_error(pid=200)],
    )
    service._handle_worker_measurement(session_id, partial)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.PARTIAL
    assert snapshot.latest_measurement is partial
    assert snapshot.last_successful_measurement is successful
    assert snapshot.last_successful_monotonic == previous_timestamp
    assert snapshot.measurement_error.error_code == "PROCESS_ACCESS_DENIED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.STALE


def test_service_preserves_last_successful_inventory_when_unavailable(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    successful = make_snapshot(
        processes=[make_process(pid=100)]
    )
    service._handle_worker_measurement(session_id, successful)

    previous_timestamp = service._read_snapshot().last_successful_monotonic

    unavailable = make_snapshot(
        errors=[make_error(pid=200)]
    )
    service._handle_worker_measurement(session_id, unavailable)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is unavailable
    assert snapshot.last_successful_measurement is successful
    assert snapshot.last_successful_monotonic == previous_timestamp
    assert snapshot.measurement_error.error_code == "PROCESS_ACCESS_DENIED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.STALE


def test_service_resets_failure_count_after_successful_recovery(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    failed = make_snapshot(
        errors=[make_error(pid=200)]
    )
    service._handle_worker_measurement(session_id, failed)

    assert service._read_snapshot().consecutive_failures == 1

    recovered = make_snapshot(
        processes=[make_process(pid=100)]
    )
    service._handle_worker_measurement(session_id, recovered)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.AVAILABLE
    assert snapshot.latest_measurement is recovered
    assert snapshot.last_successful_measurement is recovered
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.FRESH



def test_service_handles_collection_level_failure(service, qt_app):
    session_id = start_running_service(service, qt_app)

    service._handle_worker_measurement_failure(
        session_id,
        "PROCESS_COLLECTION_FAILED",
        "Process inventory collection failed.",
    )

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is None
    assert snapshot.measurement_error.error_code == "PROCESS_COLLECTION_FAILED"
    assert snapshot.measurement_error.pid is None
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.NO_DATA


def test_service_preserves_successful_inventory_after_collection_failure(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    successful = make_snapshot(
        processes=[make_process(pid=100)]
    )
    service._handle_worker_measurement(session_id, successful)

    previous_monotonic = service._read_snapshot().last_successful_monotonic

    service._handle_worker_measurement_failure(
        session_id,
        "PROCESS_COLLECTION_FAILED",
        "Process inventory collection failed.",
    )

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is successful
    assert snapshot.last_successful_monotonic == previous_monotonic
    assert snapshot.measurement_error.error_code == "PROCESS_COLLECTION_FAILED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.STALE


def test_service_recovers_after_collection_level_failure(service, qt_app):
    session_id = start_running_service(service, qt_app)

    service._handle_worker_measurement_failure(
        session_id,
        "PROCESS_COLLECTION_FAILED",
        "Process inventory collection failed.",
    )

    recovered = make_snapshot(
        processes=[make_process(pid=100)]
    )
    service._handle_worker_measurement(session_id, recovered)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == ProcessMeasurementStatus.AVAILABLE
    assert snapshot.latest_measurement is recovered
    assert snapshot.last_successful_measurement is recovered
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.FRESH


def test_service_ignores_measurement_from_stale_session(service, qt_app):
    current_session_id = start_running_service(service, qt_app)

    measurement = make_snapshot(
        processes=[make_process(pid=100)]
    )

    service._handle_worker_measurement(
        "stale-session-id",
        measurement,
    )

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.RUNNING
    assert snapshot.measurement_status == ProcessMeasurementStatus.INITIALIZING
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is None
    assert snapshot.consecutive_failures == 0
    assert service._session_id == current_session_id


def test_service_ignores_collection_failure_from_stale_session(
    service, qt_app
):
    current_session_id = start_running_service(service, qt_app)

    service._handle_worker_measurement_failure(
        "stale-session-id",
        "PROCESS_COLLECTION_FAILED",
        "Stale process collection failure.",
    )

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.RUNNING
    assert snapshot.measurement_status == ProcessMeasurementStatus.INITIALIZING
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service._session_id == current_session_id


def test_service_ignores_measurement_while_starting(service):
    session_id = service._session_id = "starting-session"

    measurement = make_snapshot(
        processes=[make_process(pid=100)]
    )

    service._commit_snapshot(
        worker_state=ProcessWorkerState.STARTING,
        measurement_status=ProcessMeasurementStatus.INITIALIZING,
    )

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.STARTING
    assert snapshot.measurement_status == ProcessMeasurementStatus.INITIALIZING
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is None
    assert snapshot.consecutive_failures == 0


def test_service_accepts_collection_failure_while_starting(service):
    service._session_id = "starting-session"

    service._commit_snapshot(
        worker_state=ProcessWorkerState.STARTING,
        measurement_status=ProcessMeasurementStatus.INITIALIZING,
    )

    service._handle_worker_measurement_failure(
        "starting-session",
        "PROCESS_COLLECTION_FAILED",
        "Process collection failed during startup.",
    )

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.STARTING
    assert snapshot.measurement_status == ProcessMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is None
    assert snapshot.measurement_error.error_code == "PROCESS_COLLECTION_FAILED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == ProcessMeasurementFreshness.NO_DATA


def test_service_handles_worker_failure_and_preserves_history(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)
    measurement = make_snapshot(
        processes=[make_process(pid=100)]
    )
    service._handle_worker_measurement(session_id, measurement)

    successful_monotonic = (
        service._read_snapshot().last_successful_monotonic
    )

    service._handle_worker_failure(session_id)

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.FAILED
    assert snapshot.measurement_status == ProcessMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is measurement
    assert snapshot.last_successful_monotonic == successful_monotonic
    assert snapshot.measurement_error.error_code == "PROCESS_WORKER_FAILED"
    assert snapshot.worker_error.error_code == "PROCESS_WORKER_FAILED"
    assert snapshot.consecutive_failures == 1

    assert wait_for_condition(
        qt_app,
        lambda: service._worker_thread is None,
    )

    assert service.get_worker_state() == ProcessWorkerState.FAILED
    assert service._worker is None


def test_service_ignores_worker_failure_from_stale_session(
    service, qt_app
):
    current_session_id = start_running_service(service, qt_app)

    service._handle_worker_failure("stale-session-id")

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.RUNNING
    assert snapshot.worker_error is None
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service._session_id == current_session_id


def test_service_ignores_worker_failure_while_stopping(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    result = service.stop()
    assert result.worker_state == ProcessWorkerState.STOPPING

    service._handle_worker_failure(session_id)

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.STOPPING
    assert snapshot.worker_error is None

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.STOPPED,
    )


class UncooperativeFakeWorker(FakeWorker):
    def __init__(self, *, announce_started=True, **kwargs):
        super().__init__(**kwargs)
        self.release_event = threading.Event()
        self.announce_started = announce_started

    def run(self):
        if self.announce_started and self.on_started is not None:
            self.on_started()

        self.release_event.wait()


def test_service_retains_worker_after_shutdown_timeout(
    service, qt_app, monkeypatch
):
    monkeypatch.setattr(
        service_module,
        "ProcessMonitoringWorker",
        UncooperativeFakeWorker,
    )

    service.start()

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == ProcessWorkerState.RUNNING,
    )

    worker = service._worker
    worker_thread = service._worker_thread

    service.stop()

    service._shutdown_deadline = time.monotonic() - 1
    service._check_shutdown_timeout()

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.FAILED
    assert snapshot.worker_error.error_code == "PROCESS_SHUTDOWN_TIMEOUT"
    assert service._worker is worker
    assert service._worker_thread is worker_thread
    assert worker_thread.is_alive()

    worker.release_event.set()

    assert wait_for_condition(
        qt_app,
        lambda: service._worker_thread is None,
    )

    assert service.get_worker_state() == ProcessWorkerState.FAILED
    assert service._worker is None


def test_service_cleans_up_after_startup_timeout(
    service, qt_app, monkeypatch
):
    monkeypatch.setattr(
        service_module,
        "ProcessMonitoringWorker",
        UncooperativeFakeWorker,
    )

    worker_class = service_module.ProcessMonitoringWorker

    original_init = worker_class.__init__

    def delayed_start_init(self, **kwargs):
        original_init(self, announce_started=False, **kwargs)

    monkeypatch.setattr(worker_class, "__init__", delayed_start_init)

    service.start()

    assert wait_for_condition(
        qt_app,
        lambda: service._worker_thread is not None
        and service._worker_thread.is_alive(),
    )

    worker = service._worker
    worker_thread = service._worker_thread

    service._startup_deadline = time.monotonic() - 1
    service._check_startup_timeout()

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == ProcessWorkerState.FAILED
    assert snapshot.worker_error.error_code == "PROCESS_STARTUP_TIMEOUT"
    assert service._startup_cleanup_pending is True
    assert service._worker is worker
    assert service._worker_thread is worker_thread
    assert worker_thread.is_alive()

    worker.release_event.set()

    assert wait_for_condition(
        qt_app,
        lambda: service._worker_thread is None,
    )

    assert service.get_worker_state() == ProcessWorkerState.FAILED
    assert service._worker is None
    assert service._startup_cleanup_pending is False


def test_service_reconfigures_running_worker(service, qt_app):
    start_running_service(service, qt_app)
    worker = service._worker

    result = service.set_sampling_interval(3.5)

    assert result.accepted is True
    assert result.sampling_interval == 3.5
    assert worker.sampling_interval == 3.5
    assert service.get_sampling_interval() == 3.5
    assert service._read_snapshot().sampling_interval == 3.5


def test_service_preserves_interval_when_worker_reconfiguration_fails(
    service, qt_app
):
    start_running_service(service, qt_app)
    worker = service._worker
    worker.raise_on_reconfigure = True

    result = service.set_sampling_interval(3.5)

    assert result.accepted is False
    assert result.sampling_interval == 2.0
    assert result.error.error_code == "PROCESS_CONFIGURATION_FAILED"
    assert worker.sampling_interval == 2.0
    assert service.get_sampling_interval() == 2.0
    assert service._read_snapshot().sampling_interval == 2.0
    assert service.get_worker_state() == ProcessWorkerState.RUNNING
