
import threading
import time
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QThread, QTimer

from system_monitor.models import (
    NetworkCounterReset,
    NetworkError,
    NetworkInterfaceMeasurement,
    NetworkMeasurement,
    NetworkMeasurementFreshness,
    NetworkMeasurementStatus,
    NetworkWorkerState,
)
from system_monitor.services import network_monitoring_service as service_module
from system_monitor.services.network_monitoring_service import (
    NetworkMonitoringService,
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
        "NetworkMonitoringWorker",
        FakeWorker,
    )

    instance = NetworkMonitoringService()
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
                "Network worker thread did not stop."
            )


def make_interface(
    name="Ethernet",
    bytes_received=1000,
    bytes_sent=500,
    download_rate=100.0,
    upload_rate=50.0,
    packets_received=10,
    packets_sent=5,
    errors_in=0,
    errors_out=0,
    drops_in=0,
    drops_out=0,
):
    return NetworkInterfaceMeasurement(
        interface_id=name,
        name=name,
        bytes_received=bytes_received,
        bytes_sent=bytes_sent,
        packets_received=packets_received,
        packets_sent=packets_sent,
        errors_in=errors_in,
        errors_out=errors_out,
        drops_in=drops_in,
        drops_out=drops_out,
        download_bytes_per_second=download_rate,
        upload_bytes_per_second=upload_rate,
        sampled_at=datetime.now(timezone.utc),
    )


def make_error(
    interface_id="Ethernet",
    error_code="NETWORK_INTERFACE_FAILED",
):
    return NetworkError(
        error_code=error_code,
        message="Simulated network interface collection failure.",
        occurred_at=datetime.now(timezone.utc),
        interface_id=interface_id,
    )


def make_measurement(
    interfaces=None,
    errors=None,
    resets=None,
    baseline_only_ids=None,
    sampling_interval=1.0,
):
    now = datetime.now(timezone.utc)

    return NetworkMeasurement(
        interfaces=tuple(interfaces or ()),
        interface_errors=tuple(errors or ()),
        counter_resets=tuple(resets or ()),
        baseline_only_interface_ids=tuple(
            baseline_only_ids or ()
        ),
        sampling_interval=sampling_interval,
        started_at=now,
        completed_at=now,
    )


def test_service_initial_state(service):
    assert service.get_worker_state() == NetworkWorkerState.STOPPED
    assert (
        service.get_measurement_status()
        == NetworkMeasurementStatus.UNAVAILABLE
    )
    assert (
        service.get_measurement_freshness()
        == NetworkMeasurementFreshness.NO_DATA
    )
    assert service.get_latest_measurement() is None
    assert service.get_last_successful_measurement() is None
    assert service.get_measurement_error() is None
    assert service.get_worker_error() is None
    assert service.get_consecutive_failures() == 0
    assert service.get_sampling_interval() == 1.0


@pytest.mark.parametrize("interval", [0.5, 1.0, 5.0, 30.0, 60.0])
def test_service_accepts_valid_sampling_intervals(service, interval):
    result = service.set_sampling_interval(interval)

    assert result.accepted is True
    assert result.sampling_interval == interval
    assert result.worker_state == NetworkWorkerState.STOPPED
    assert result.error is None
    assert service.get_sampling_interval() == interval


@pytest.mark.parametrize(
    "interval",
    [
        0,
        -1,
        0.49,
        60.01,
        float("inf"),
        float("-inf"),
        float("nan"),
        True,
        False,
        "1.0",
        None,
    ],
)


def test_service_rejects_invalid_sampling_intervals(service, interval):
    original_interval = service.get_sampling_interval()

    result = service.set_sampling_interval(interval)

    assert result.accepted is False
    assert result.sampling_interval == original_interval
    assert result.worker_state == NetworkWorkerState.STOPPED
    assert result.error is not None
    assert result.error.error_code == "NETWORK_INVALID_SAMPLING_INTERVAL"
    assert service.get_sampling_interval() == original_interval


def test_service_publishes_current_state(service, qt_app):
    received = []
    service.current_state_published.connect(received.append)

    snapshot = service.publish_current_state()

    assert len(received) == 1
    assert received[0] is snapshot
    assert snapshot.worker_state == NetworkWorkerState.STOPPED
    assert snapshot.measurement_status == NetworkMeasurementStatus.UNAVAILABLE


def test_service_starts_worker(service, qt_app):
    result = service.start()
    process_events(qt_app, 100)

    assert result.accepted is True
    assert len(FakeWorker.instances) == 1
    assert service.get_worker_state() == NetworkWorkerState.RUNNING


def test_service_assigns_valid_session_id(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    assert service._session_id is not None
    assert service.get_worker_state() == NetworkWorkerState.RUNNING


def test_service_does_not_start_duplicate_worker(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    result = service.start()
    process_events(qt_app, 50)

    assert result.accepted is True
    assert result.worker_state == NetworkWorkerState.RUNNING
    assert len(FakeWorker.instances) == 1


def test_service_stops_worker(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    worker = FakeWorker.instances[0]
    result = service.stop()

    assert result.success is False
    assert result.worker_state == NetworkWorkerState.STOPPING

    deadline = time.monotonic() + 2.0

    while (
        service.get_worker_state() != NetworkWorkerState.STOPPED
        and time.monotonic() < deadline
    ):
        process_events(qt_app, 50)

    assert service.get_worker_state() == NetworkWorkerState.STOPPED
    assert worker.stop_event.is_set()
    assert not service._worker_thread


def test_service_start_stop_start_uses_new_session(service, qt_app):
    service.start()
    process_events(qt_app, 100)

    first_session_id = service._session_id

    service.stop()

    deadline = time.monotonic() + 2.0

    while (
        service.get_worker_state() != NetworkWorkerState.STOPPED
        and time.monotonic() < deadline
    ):
        process_events(qt_app, 50)

    assert service.get_worker_state() == NetworkWorkerState.STOPPED

    service.start()
    process_events(qt_app, 100)

    assert len(FakeWorker.instances) == 2
    assert service._session_id != first_session_id
    assert service.get_worker_state() == NetworkWorkerState.RUNNING


def start_running_service(service, qt_app):
    result = service.start()
    process_events(qt_app, 100)

    assert result.accepted is True
    assert service.get_worker_state() == NetworkWorkerState.RUNNING

    return service._session_id


def test_service_accepts_baseline_only_measurement(service, qt_app):
    session_id = start_running_service(service, qt_app)

    measurement = make_measurement(
        interfaces=[
            make_interface(
                download_rate=None,
                upload_rate=None,
            )
        ],
        baseline_only_ids=["Ethernet"],
    )

    service._handle_worker_measurement(session_id, measurement)

    assert service.get_measurement_status() == NetworkMeasurementStatus.INITIALIZING
    assert service.get_latest_measurement() is measurement
    assert service.get_last_successful_measurement() is measurement
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.STALE
    assert service.get_consecutive_failures() == 0


def test_service_accepts_rate_ready_measurement(service, qt_app):
    session_id = start_running_service(service, qt_app)
    measurement = make_measurement(
        interfaces=[make_interface()],
    )

    service._handle_worker_measurement(session_id, measurement)

    assert service.get_measurement_status() == NetworkMeasurementStatus.AVAILABLE
    assert service.get_latest_measurement() is measurement
    assert service.get_last_successful_measurement() is measurement
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.FRESH


def test_service_accepts_mixed_interface_measurement(service, qt_app):
    session_id = start_running_service(service, qt_app)

    measurement = make_measurement(
        interfaces=[
            make_interface(
                name="Ethernet",
                download_rate=None,
                upload_rate=None,
            ),
            make_interface(
                name="Wi-Fi",
                download_rate=200.0,
                upload_rate=80.0,
            ),
        ],
        baseline_only_ids=["Ethernet"],
    )

    service._handle_worker_measurement(session_id, measurement)

    assert service.get_measurement_status() == NetworkMeasurementStatus.AVAILABLE
    assert service.get_latest_measurement() is measurement


def test_service_accepts_empty_inventory_as_success(service, qt_app):
    session_id = start_running_service(service, qt_app)
    measurement = make_measurement()

    service._handle_worker_measurement(session_id, measurement)

    assert service.get_measurement_status() == NetworkMeasurementStatus.AVAILABLE
    assert service.get_latest_measurement() is measurement
    assert service.get_last_successful_measurement() is measurement
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.FRESH


def test_service_emits_measurement_updated_signal(service, qt_app):
    session_id = start_running_service(service, qt_app)
    received = []
    service.measurement_updated.connect(received.append)

    measurement = make_measurement(
        interfaces=[make_interface()],
    )

    service._handle_worker_measurement(session_id, measurement)

    assert received == [measurement]


def test_service_preserves_last_successful_measurement_on_partial_failure(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    successful_measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")]
    )
    service._handle_worker_measurement(session_id, successful_measurement)

    previous_monotonic = service._read_snapshot().last_successful_monotonic

    partial_measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")],
        errors=[make_error(interface_id="Wi-Fi")],
    )
    service._handle_worker_measurement(session_id, partial_measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.PARTIAL
    assert snapshot.latest_measurement is partial_measurement
    assert snapshot.last_successful_measurement is successful_measurement
    assert snapshot.last_successful_monotonic == previous_monotonic
    assert snapshot.measurement_error.error_code == "NETWORK_INTERFACE_FAILED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.STALE


def test_service_preserves_last_successful_measurement_on_unavailable(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    successful_measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")]
    )
    service._handle_worker_measurement(session_id, successful_measurement)

    previous_monotonic = service._read_snapshot().last_successful_monotonic

    unavailable_measurement = make_measurement(
        errors=[make_error(interface_id="Ethernet")]
    )
    service._handle_worker_measurement(session_id, unavailable_measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is unavailable_measurement
    assert snapshot.last_successful_measurement is successful_measurement
    assert snapshot.last_successful_monotonic == previous_monotonic
    assert snapshot.measurement_error.error_code == "NETWORK_INTERFACE_FAILED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.STALE


def test_service_reports_no_data_on_first_unavailable_measurement(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    unavailable_measurement = make_measurement(
        errors=[make_error(interface_id="Ethernet")]
    )
    service._handle_worker_measurement(session_id, unavailable_measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is unavailable_measurement
    assert snapshot.last_successful_measurement is None
    assert snapshot.last_successful_monotonic is None
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.NO_DATA


def test_service_reports_no_data_on_first_unavailable_measurement(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    unavailable_measurement = make_measurement(
        errors=[make_error(interface_id="Ethernet")]
    )
    service._handle_worker_measurement(session_id, unavailable_measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is unavailable_measurement
    assert snapshot.last_successful_measurement is None
    assert snapshot.last_successful_monotonic is None
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.NO_DATA


def test_service_recovers_after_unavailable_measurement(service, qt_app):
    session_id = start_running_service(service, qt_app)

    unavailable_measurement = make_measurement(
        errors=[make_error(interface_id="Ethernet")]
    )
    service._handle_worker_measurement(session_id, unavailable_measurement)

    assert service.get_consecutive_failures() == 1

    recovered_measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")]
    )
    service._handle_worker_measurement(session_id, recovered_measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.AVAILABLE
    assert snapshot.latest_measurement is recovered_measurement
    assert snapshot.last_successful_measurement is recovered_measurement
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.FRESH


def test_service_preserves_last_successful_measurement_on_collection_failure(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    successful_measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")]
    )
    service._handle_worker_measurement(session_id, successful_measurement)

    previous_monotonic = service._read_snapshot().last_successful_monotonic

    service._handle_worker_measurement_failure(
        session_id,
        "NETWORK_COLLECTION_FAILED",
        "Network interface collection failed.",
    )

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is successful_measurement
    assert snapshot.last_successful_monotonic == previous_monotonic
    assert snapshot.measurement_error.error_code == "NETWORK_COLLECTION_FAILED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.STALE


def test_service_ignores_measurement_from_stale_session(service, qt_app):
    current_session_id = start_running_service(service, qt_app)

    measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")]
    )

    service._handle_worker_measurement(
        "stale-session-id",
        measurement,
    )

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.RUNNING
    assert snapshot.measurement_status == NetworkMeasurementStatus.INITIALIZING
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
        "NETWORK_COLLECTION_FAILED",
        "Old worker collection failed.",
    )

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.RUNNING
    assert snapshot.measurement_status == NetworkMeasurementStatus.INITIALIZING
    assert snapshot.latest_measurement is None
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service._session_id == current_session_id


def test_service_treats_counter_reset_as_successful_diagnostic(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    reset = NetworkCounterReset(
        interface_id="Ethernet",
        occurred_at=datetime.now(timezone.utc),
        reset_counters=("bytes_received", "bytes_sent"),
    )

    measurement = make_measurement(
        interfaces=[
            make_interface(
                name="Ethernet",
                download_rate=None,
                upload_rate=None,
            )
        ],
        resets=[reset],
    )

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.AVAILABLE
    assert snapshot.latest_measurement is measurement
    assert snapshot.last_successful_measurement is measurement
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.FRESH
    assert measurement.counter_resets == (reset,)


def test_service_classifies_reset_with_interface_error_as_partial(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    reset = NetworkCounterReset(
        interface_id="Ethernet",
        occurred_at=datetime.now(timezone.utc),
        reset_counters=("bytes_received",),
    )

    measurement = make_measurement(
        interfaces=[
            make_interface(
                name="Ethernet",
                download_rate=None,
                upload_rate=None,
            )
        ],
        errors=[make_error(interface_id="Wi-Fi")],
        resets=[reset],
    )

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.measurement_status == NetworkMeasurementStatus.PARTIAL
    assert snapshot.latest_measurement is measurement
    assert snapshot.last_successful_measurement is None
    assert snapshot.measurement_error.error_code == "NETWORK_INTERFACE_FAILED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.NO_DATA
    assert measurement.counter_resets == (reset,)


def test_service_ignores_measurement_while_starting(service):
    session_id = service._session_id = "starting-session"

    measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")]
    )

    service._commit_snapshot(
        worker_state=NetworkWorkerState.STARTING,
        measurement_status=NetworkMeasurementStatus.INITIALIZING,
    )

    service._handle_worker_measurement(session_id, measurement)

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.STARTING
    assert snapshot.measurement_status == NetworkMeasurementStatus.INITIALIZING
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is None
    assert snapshot.consecutive_failures == 0


def test_service_accepts_collection_failure_while_starting(service):
    service._session_id = "starting-session"

    service._commit_snapshot(
        worker_state=NetworkWorkerState.STARTING,
        measurement_status=NetworkMeasurementStatus.INITIALIZING,
    )

    service._handle_worker_measurement_failure(
        "starting-session",
        "NETWORK_COLLECTION_FAILED",
        "Network interface collection failed during startup.",
    )

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.STARTING
    assert snapshot.measurement_status == NetworkMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is None
    assert snapshot.measurement_error.error_code == "NETWORK_COLLECTION_FAILED"
    assert snapshot.consecutive_failures == 1
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.NO_DATA


def test_service_handles_worker_failure_and_preserves_measurement_history(
    service, qt_app
):
    session_id = start_running_service(service, qt_app)

    successful_measurement = make_measurement(
        interfaces=[make_interface(name="Ethernet")]
    )
    service._handle_worker_measurement(session_id, successful_measurement)

    service._handle_worker_failure(session_id)

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.FAILED
    assert snapshot.measurement_status == NetworkMeasurementStatus.UNAVAILABLE
    assert snapshot.latest_measurement is None
    assert snapshot.last_successful_measurement is successful_measurement
    assert snapshot.worker_error.error_code == "NETWORK_WORKER_FAILED"
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service.get_measurement_freshness() == NetworkMeasurementFreshness.STALE


def test_service_ignores_worker_failure_from_stale_session(
    service, qt_app
):
    current_session_id = start_running_service(service, qt_app)

    service._handle_worker_failure("stale-session-id")

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.RUNNING
    assert snapshot.measurement_status == NetworkMeasurementStatus.INITIALIZING
    assert snapshot.worker_error is None
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0
    assert service._session_id == current_session_id


def test_service_ignores_worker_failure_during_shutdown(
    service,
    qt_app,
):
    session_id = start_running_service(service, qt_app)

    result = service.stop()

    assert result.success is False
    assert result.worker_state == NetworkWorkerState.STOPPING

    service._handle_worker_failure(session_id)

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.STOPPING
    assert snapshot.worker_error is None

    assert wait_for_condition(
        qt_app,
        lambda: service.get_worker_state() == NetworkWorkerState.STOPPED,
    )


def test_service_ignores_worker_failure_during_startup_cleanup(service):
    service._session_id = "cleanup-session"
    service._startup_cleanup_pending = True

    service._commit_snapshot(
        worker_state=NetworkWorkerState.FAILED,
        measurement_status=NetworkMeasurementStatus.UNAVAILABLE,
    )

    service._handle_worker_failure("cleanup-session")

    snapshot = service._read_snapshot()

    assert snapshot.worker_state == NetworkWorkerState.FAILED
    assert snapshot.worker_error is None
    assert snapshot.measurement_error is None
    assert snapshot.consecutive_failures == 0


def test_service_updates_sampling_interval_while_running(service, qt_app):
    start_running_service(service, qt_app)

    worker = service._worker
    result = service.set_sampling_interval(2.5)

    assert result.accepted is True
    assert result.sampling_interval == 2.5
    assert worker.sampling_interval == 2.5
    assert service.get_sampling_interval() == 2.5
    assert service._read_snapshot().sampling_interval == 2.5


def test_service_preserves_interval_when_worker_rejects_configuration(
    service, qt_app
):
    start_running_service(service, qt_app)

    worker = service._worker
    worker.raise_on_reconfigure = True

    result = service.set_sampling_interval(2.5)

    assert result.accepted is False
    assert result.sampling_interval == 1.0
    assert result.error.error_code == "NETWORK_CONFIGURATION_FAILED"
    assert worker.sampling_interval == 1.0
    assert service.get_sampling_interval() == 1.0
    assert service._read_snapshot().sampling_interval == 1.0


def test_service_rejects_sampling_interval_change_while_stopping(
    service, qt_app
):
    start_running_service(service, qt_app)

    service._commit_snapshot(
        worker_state=NetworkWorkerState.STOPPING,
    )

    result = service.set_sampling_interval(2.5)

    assert result.accepted is False
    assert result.sampling_interval == 1.0
    assert result.error.error_code == "NETWORK_CONFIGURATION_REJECTED"
    assert service.get_sampling_interval() == 1.0
    assert service.get_worker_state() == NetworkWorkerState.STOPPING

    service._worker.stop_event.set()


def test_service_updates_sampling_interval_while_stopped(service):
    result = service.set_sampling_interval(2.5)

    assert result.accepted is True
    assert result.sampling_interval == 2.5
    assert service.get_sampling_interval() == 2.5
    assert service._read_snapshot().sampling_interval == 2.5
    assert service.get_worker_state() == NetworkWorkerState.STOPPED
    assert service._worker is None
    assert service._worker_thread is None


def test_service_rejects_invalid_interval_while_running(service, qt_app):
    start_running_service(service, qt_app)

    worker = service._worker
    result = service.set_sampling_interval(0.25)

    assert result.accepted is False
    assert result.sampling_interval == 1.0
    assert result.error.error_code == "NETWORK_INVALID_SAMPLING_INTERVAL"
    assert worker.sampling_interval == 1.0
    assert service.get_sampling_interval() == 1.0
    assert service._read_snapshot().sampling_interval == 1.0
    assert service.get_worker_state() == NetworkWorkerState.RUNNING


def test_service_rejects_reconfiguration_during_startup_cleanup(service):
    service._session_id = "cleanup-session"
    service._startup_cleanup_pending = True
    service._worker_thread = threading.Thread(target=lambda: time.sleep(0.5))
    service._worker_thread.start()

    service._commit_snapshot(
        worker_state=NetworkWorkerState.FAILED,
        measurement_status=NetworkMeasurementStatus.UNAVAILABLE,
    )

    result = service.set_sampling_interval(2.5)

    assert result.accepted is False
    assert result.sampling_interval == 1.0
    assert result.error.error_code == "NETWORK_CONFIGURATION_REJECTED"
    assert service.get_sampling_interval() == 1.0
    assert service._startup_cleanup_pending is True

    service._worker_thread.join(timeout=2)
    assert not service._worker_thread.is_alive()


def test_service_rejects_reconfiguration_when_failed_worker_is_alive(
    service,
):
    service._session_id = "failed-session"
    service._worker_thread = threading.Thread(
        target=lambda: time.sleep(0.5)
    )
    service._worker_thread.start()

    service._commit_snapshot(
        worker_state=NetworkWorkerState.FAILED,
        measurement_status=NetworkMeasurementStatus.UNAVAILABLE,
    )

    result = service.set_sampling_interval(2.5)

    assert result.accepted is False
    assert result.sampling_interval == 1.0
    assert result.error.error_code == "NETWORK_CONFIGURATION_REJECTED"
    assert service.get_sampling_interval() == 1.0

    service._worker_thread.join(timeout=2)
    assert not service._worker_thread.is_alive()


class UncooperativeFakeWorker(FakeWorker):
    instances = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.__class__.instances.append(self)

    def run(self):
        self.entered.set()
        if self.on_started is not None:
            self.on_started()
        self.release.wait(timeout=10)


class StartupStallingFakeWorker(FakeWorker):
    instances = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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


def test_service_retains_worker_after_shutdown_timeout(
    monkeypatch, qt_app
):
    monkeypatch.setattr(
        service_module,
        "NetworkMonitoringWorker",
        UncooperativeFakeWorker,
    )
    monkeypatch.setattr(
        NetworkMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.1,
    )

    UncooperativeFakeWorker.instances.clear()

    instance = NetworkMonitoringService()
    worker = None
    worker_thread = None

    try:
        instance.start()

        worker = UncooperativeFakeWorker.instances[0]
        assert worker.entered.wait(timeout=1)

        assert wait_for_condition(
            qt_app,
            lambda: instance.get_worker_state() == NetworkWorkerState.RUNNING,
        )

        instance.stop()

        assert wait_for_condition(
            qt_app,
            lambda: instance.get_worker_state() == NetworkWorkerState.FAILED,
        )

        assert instance.get_worker_error().error_code == "NETWORK_SHUTDOWN_TIMEOUT"
        assert instance._worker is worker
        assert instance._worker_thread is not None
        assert instance._worker_thread.is_alive()

        worker_thread = instance._worker_thread
        worker.release.set()

        assert wait_for_condition(
            qt_app,
            lambda: not worker_thread.is_alive(),
        )

        retry_result = instance.stop()

        assert retry_result.success is True
        assert instance.get_worker_state() == NetworkWorkerState.STOPPED
        assert instance._worker is None
        assert instance._worker_thread is None

    finally:
        if worker is not None:
            worker.release.set()

        if worker_thread is None:
            worker_thread = instance._worker_thread

        if worker_thread is not None:
            worker_thread.join(timeout=2)

        qt_app.processEvents()

        if (
            worker_thread is not None
            and not worker_thread.is_alive()
            and instance._worker is not None
        ):
            instance.stop()
            qt_app.processEvents()


def test_service_handles_startup_timeout_and_preserves_error(
    monkeypatch, qt_app
):
    monkeypatch.setattr(
        service_module,
        "NetworkMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        NetworkMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        NetworkMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    StartupStallingFakeWorker.instances.clear()

    instance = NetworkMonitoringService()
    worker = None
    worker_thread = None

    try:
        result = instance.start()
        assert result.accepted is True

        worker = StartupStallingFakeWorker.instances[0]
        assert worker.entered.wait(timeout=1)

        assert wait_for_condition(
            qt_app,
            lambda: (
                instance.get_worker_state() == NetworkWorkerState.FAILED
                and instance._startup_cleanup_pending
            ),
        )

        assert instance.get_worker_error().error_code == "NETWORK_STARTUP_TIMEOUT"
        assert instance._worker is worker
        assert instance._worker_thread is not None
        assert instance._worker_thread.is_alive()

        worker_thread = instance._worker_thread
        worker.release.set()

        assert wait_for_condition(
            qt_app,
            lambda: (
                instance._worker_thread is None
                and not instance._startup_cleanup_pending
            ),
        )

        assert instance.get_worker_state() == NetworkWorkerState.FAILED
        assert instance.get_worker_error().error_code == "NETWORK_STARTUP_TIMEOUT"

    finally:
        if worker is not None:
            worker.release.set()

        if worker_thread is None:
            worker_thread = instance._worker_thread

        if worker_thread is not None:
            worker_thread.join(timeout=2)

        qt_app.processEvents()
        qt_app.processEvents()


def test_service_can_restart_after_startup_timeout_cleanup(
    monkeypatch, qt_app
):
    monkeypatch.setattr(
        service_module,
        "NetworkMonitoringWorker",
        StartupStallingFakeWorker,
    )
    monkeypatch.setattr(
        NetworkMonitoringService,
        "STARTUP_TIMEOUT_SECONDS",
        0.1,
    )
    monkeypatch.setattr(
        NetworkMonitoringService,
        "SHUTDOWN_TIMEOUT_SECONDS",
        0.2,
    )

    StartupStallingFakeWorker.instances.clear()

    instance = NetworkMonitoringService()
    workers = []
    threads = []

    try:
        instance.start()

        first_worker = StartupStallingFakeWorker.instances[0]
        workers.append(first_worker)
        assert first_worker.entered.wait(timeout=1)

        first_thread = instance._worker_thread
        threads.append(first_thread)

        assert wait_for_condition(
            qt_app,
            lambda: instance._startup_cleanup_pending,
        )

        first_worker.release.set()

        assert wait_for_condition(
            qt_app,
            lambda: (
                instance._worker_thread is None
                and not instance._startup_cleanup_pending
            ),
        )

        assert instance.get_worker_error().error_code == "NETWORK_STARTUP_TIMEOUT"

        restarted = instance.start()

        assert restarted.accepted is True
        assert len(StartupStallingFakeWorker.instances) == 2

        second_worker = StartupStallingFakeWorker.instances[-1]
        workers.append(second_worker)

        second_thread = instance._worker_thread
        threads.append(second_thread)

        assert second_worker.entered.wait(timeout=1)

        second_worker.release.set()

        assert wait_for_condition(
            qt_app,
            lambda: not second_thread.is_alive(),
        )

        instance.stop()

    finally:
        for worker in workers:
            worker.release.set()

        for thread in threads:
            if thread is not None:
                thread.join(timeout=2)

        current_thread = instance._worker_thread
        if current_thread is not None and current_thread not in threads:
            current_thread.join(timeout=2)

        qt_app.processEvents()
        qt_app.processEvents()

        if (
            instance._worker_thread is not None
            and not instance._worker_thread.is_alive()
        ):
            instance.stop()
            qt_app.processEvents()


def test_service_dispatches_directly_on_owner_thread(service, qt_app):
    execution_threads = []

    def callback():
        execution_threads.append(QThread.currentThread())
        return "completed"

    result = service._dispatch_request("test", callback)

    assert result == "completed"
    assert execution_threads == [service._owner_thread]


def test_service_dispatches_background_request_on_owner_thread(
    service, qt_app
):
    result_holder = {}
    execution_threads = []

    def callback():
        execution_threads.append(QThread.currentThread())
        return "completed"

    def request_from_background_thread():
        result_holder["result"] = service._dispatch_request(
            "start",  # CHANGE "test" TO "start"
            callback,
        )

    caller = threading.Thread(
        target=request_from_background_thread,
    )
    caller.start()

    assert wait_for_condition(
        qt_app,
        lambda: not caller.is_alive(),
    )

    caller.join(timeout=1)

    assert not caller.is_alive()
    assert result_holder["result"] == "completed"
    assert execution_threads == [service._owner_thread]


def test_service_returns_dispatch_result_to_calling_thread(service, qt_app):
    result_holder = {}
    caller_threads = []

    def callback():
        return "completed"

    def request_from_background_thread():
        caller_threads.append(QThread.currentThread())
        result_holder["result"] = service._dispatch_request(
            "start",  # CHANGE "test" TO "start"
            callback,
        )
        result_holder["return_thread"] = QThread.currentThread()

    caller = threading.Thread(
        target=request_from_background_thread,
    )
    caller.start()

    assert wait_for_condition(
        qt_app,
        lambda: not caller.is_alive(),
    )

    caller.join(timeout=1)

    assert not caller.is_alive()
    assert result_holder["result"] == "completed"
    assert result_holder["return_thread"] is caller_threads[0]


def test_service_propagates_dispatched_callback_exception(service, qt_app):
    result_holder = {}

    def callback():
        raise ValueError("dispatch callback failed")

    def request_from_background_thread():
        try:
            service._dispatch_request("test", callback)
        except Exception as exc:
            result_holder["error"] = exc

    caller = threading.Thread(
        target=request_from_background_thread,
    )
    caller.start()

    assert wait_for_condition(
        qt_app,
        lambda: not caller.is_alive(),
    )

    caller.join(timeout=1)

    assert not caller.is_alive()
    assert isinstance(result_holder["error"], ValueError)
    assert str(result_holder["error"]) == "dispatch callback failed"


def test_service_does_not_execute_expired_dispatched_request(
    service, qt_app
):
    execution_count = []
    result_holder = {}

    def callback():
        execution_count.append("executed")
        return "completed"

    def request_from_background_thread():
        result_holder["result"] = service._dispatch_request(
            "start",  # CHANGE "test" TO "start"
            callback,
        )

    caller = threading.Thread(
        target=request_from_background_thread,
    )
    caller.start()

    caller.join(
        timeout=service.REQUEST_DISPATCH_TIMEOUT_SECONDS + 1
    )

    assert not caller.is_alive()
    result = result_holder["result"]

    assert result.accepted is False
    assert result.worker_state == NetworkWorkerState.STOPPED
    assert result.error is not None
    assert result.error.error_code == "NETWORK_REQUEST_DISPATCH_TIMEOUT"
    assert execution_count == []

    process_events(qt_app)

    assert execution_count == []


def test_service_does_not_execute_dispatched_request_twice(
    service,
    qt_app,
):
    execution_count = []

    def callback():
        execution_count.append(QThread.currentThread())
        return "completed"

    request = {
        "operation": "start",
        "callback": callback,
        "deadline": time.monotonic() + 5.0,
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

    assert request["result"] == "completed"
    assert request["completed"] is True
    assert len(execution_count) == 1
    assert execution_count[0] == service._owner_thread


def test_real_worker_startup_then_unexpected_failure(monkeypatch, qt_app):
    from system_monitor.workers.network_monitoring_worker import (
        NetworkMonitoringWorker,
    )

    class FailingNetworkWorker(NetworkMonitoringWorker):
        def _wait_for_next_window(self, interval):
            raise RuntimeError("Simulated failure after startup.")

    monkeypatch.setattr(
        service_module,
        "NetworkMonitoringWorker",
        FailingNetworkWorker,
    )

    instance = NetworkMonitoringService()

    try:
        result = instance.start()

        assert result.accepted is True

        assert wait_for_condition(
            qt_app,
            lambda: (
                instance.get_worker_state()
                == NetworkWorkerState.FAILED
            ),
        )

        assert instance.get_measurement_status() == (
            NetworkMeasurementStatus.UNAVAILABLE
        )

        assert instance.get_latest_measurement() is None

        worker_error = instance.get_worker_error()
        assert worker_error is not None
        assert worker_error.error_code == "NETWORK_WORKER_FAILED"

        assert instance._worker_thread is not None
        assert not instance._worker_thread.is_alive()

    finally:
        worker_thread = instance._worker_thread

        if worker_thread is not None and worker_thread.is_alive():
            instance.stop()
            worker_thread.join(timeout=2)

        qt_app.processEvents()
        qt_app.processEvents()

        if worker_thread is not None:
            assert not worker_thread.is_alive()
