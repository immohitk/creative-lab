import logging
import math
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt

from system_monitor.models import (
    ProcessConfigurationResult,
    ProcessError,
    ProcessMeasurement,
    ProcessMeasurementStatus,
    ProcessSnapshot,
    ProcessStartResult,
    ProcessStateSnapshot,
    ProcessStopResult,
    ProcessWorkerState,
)
from system_monitor.workers.process_monitoring_worker import (
    ProcessMonitoringWorker,
)


logger = logging.getLogger(__name__)


class ProcessMonitoringService(QObject):
    """Owns process monitoring state and coordinates its sampling worker."""

    DEFAULT_SAMPLING_INTERVAL = 2.0
    MIN_SAMPLING_INTERVAL = 0.5
    MAX_SAMPLING_INTERVAL = 60.0

    STARTUP_TIMEOUT_SECONDS = 5.0
    SHUTDOWN_TIMEOUT_SECONDS = 5.0
    REQUEST_DISPATCH_TIMEOUT_SECONDS = 5.0
    CLEANUP_POLL_INTERVAL_MS = 100

    measurement_updated = Signal(object)
    measurement_status_changed = Signal(object)
    worker_state_changed = Signal(object)
    measurement_error_changed = Signal(object)
    worker_error_changed = Signal(object)
    current_state_published = Signal(object)

    _request_dispatched = Signal(object)
    _worker_started = Signal(object)
    _worker_measurement_received = Signal(object, object)
    _worker_measurement_failed = Signal(object, str, str)
    _worker_failed = Signal(object)

    def __init__(
        self,
        sampling_interval=DEFAULT_SAMPLING_INTERVAL,
        parent=None,
    ):
        super().__init__(parent)

        self._validate_sampling_interval(sampling_interval)

        self._owner_thread = QThread.currentThread()
        self._lock = threading.RLock()
        self._sampling_interval = float(sampling_interval)

        self._snapshot = ProcessStateSnapshot(
            worker_state=ProcessWorkerState.STOPPED,
            measurement_status=ProcessMeasurementStatus.INITIALIZING,
            latest_measurement=None,
            last_successful_measurement=None,
            last_successful_monotonic=None,
            measurement_error=None,
            worker_error=None,
            consecutive_failures=0,
            sampling_interval=self._sampling_interval,
            revision=0,
        )

        self._worker = None
        self._worker_thread = None
        self._session_id = None

        self._stop_event = None
        self._reconfigure_event = None

        self._startup_deadline = None
        self._shutdown_deadline = None

        self._pending_start = False
        self._pending_stop = False
        self._startup_cleanup_pending = False
        self._shutdown_cleanup_pending = False

        self._startup_timer = QTimer(self)
        self._startup_timer.setInterval(
            self.CLEANUP_POLL_INTERVAL_MS
        )
        self._startup_timer.timeout.connect(
            self._check_startup_timeout
        )

        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setInterval(
            self.CLEANUP_POLL_INTERVAL_MS
        )
        self._shutdown_timer.timeout.connect(
            self._check_shutdown_timeout
        )

        self._request_dispatched.connect(
            self._execute_dispatched_request,
            Qt.ConnectionType.QueuedConnection,
        )

        self._worker_started.connect(
            self._handle_worker_started,
            Qt.ConnectionType.QueuedConnection,
        )

        self._worker_measurement_received.connect(
            self._handle_worker_measurement,
            Qt.ConnectionType.QueuedConnection,
        )

        self._worker_measurement_failed.connect(
            self._handle_worker_measurement_failure,
            Qt.ConnectionType.QueuedConnection,
        )

        self._worker_failed.connect(
            self._handle_worker_failure,
            Qt.ConnectionType.QueuedConnection,
        )

    @classmethod
    def _validate_sampling_interval(cls, value):
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise TypeError("Sampling interval must be numeric.")

        value = float(value)

        if (
            not math.isfinite(value)
            or not cls.MIN_SAMPLING_INTERVAL
            <= value
            <= cls.MAX_SAMPLING_INTERVAL
        ):
            raise ValueError(
                "Sampling interval must be between "
                "0.5 and 60 seconds."
            )

    def _assert_owner_thread(self):
        if QThread.currentThread() != self._owner_thread:
            raise RuntimeError(
                "This operation must execute on the "
                "service's owning Qt thread."
            )

    def _commit_snapshot(self, **changes):
        self._assert_owner_thread()

        with self._lock:
            old_snapshot = self._snapshot

            values = {
                "worker_state": old_snapshot.worker_state,
                "measurement_status": old_snapshot.measurement_status,
                "latest_measurement": old_snapshot.latest_measurement,
                "last_successful_measurement": (
                    old_snapshot.last_successful_measurement
                ),
                "last_successful_monotonic": (
                    old_snapshot.last_successful_monotonic
                ),
                "measurement_error": old_snapshot.measurement_error,
                "worker_error": old_snapshot.worker_error,
                "consecutive_failures": (
                    old_snapshot.consecutive_failures
                ),
                "sampling_interval": old_snapshot.sampling_interval,
                "revision": old_snapshot.revision,
            }

            values.update(changes)

            changed = any(
                values[key] != getattr(old_snapshot, key)
                for key in values
                if key != "revision"
            )

            if not changed:
                return old_snapshot

            values["revision"] = old_snapshot.revision + 1

            new_snapshot = ProcessStateSnapshot(**values)
            self._snapshot = new_snapshot

        self._emit_snapshot_changes(old_snapshot, new_snapshot)

        return new_snapshot

    def _emit_snapshot_changes(self, old, new):
        if old.worker_state != new.worker_state:
            self.worker_state_changed.emit(new.worker_state)

        if old.measurement_status != new.measurement_status:
            self.measurement_status_changed.emit(
                new.measurement_status
            )

        if old.measurement_error != new.measurement_error:
            self.measurement_error_changed.emit(
                new.measurement_error
            )

        if old.worker_error != new.worker_error:
            self.worker_error_changed.emit(new.worker_error)

    def _read_snapshot(self):
        with self._lock:
            return self._snapshot

    def get_worker_state(self):
        return self._read_snapshot().worker_state

    def get_measurement_status(self):
        return self._read_snapshot().measurement_status

    def get_measurement_freshness(self):
        return self._read_snapshot().freshness

    def get_latest_measurement(self):
        return self._read_snapshot().latest_measurement

    def get_last_successful_measurement(self):
        return self._read_snapshot().last_successful_measurement

    def get_measurement_error(self):
        return self._read_snapshot().measurement_error

    def get_worker_error(self):
        return self._read_snapshot().worker_error

    def get_consecutive_failures(self):
        return self._read_snapshot().consecutive_failures

    def get_sampling_interval(self):
        return self._read_snapshot().sampling_interval

    def get_last_successful_age(self):
        return self._read_snapshot().last_successful_age(
            time.monotonic()
        )

    def publish_current_state(self):
        snapshot = self._read_snapshot()
        self.current_state_published.emit(snapshot)
        return snapshot

    def set_sampling_interval(self, seconds):
        """Configure process sampling through the owning Qt thread."""
        return self._dispatch_request(
            "set_sampling_interval",
            lambda: self._set_sampling_interval_on_owner_thread(seconds),
        )

    def _set_sampling_interval_on_owner_thread(self, seconds):
        self._assert_owner_thread()

        snapshot = self._read_snapshot()
        current_interval = snapshot.sampling_interval

        try:
            self._validate_sampling_interval(seconds)
        except (TypeError, ValueError):
            error = ProcessError(
                error_code="PROCESS_INVALID_SAMPLING_INTERVAL",
                message=(
                    "Sampling interval must be between "
                    "0.5 and 60 seconds."
                ),
                occurred_at=datetime.now(timezone.utc),
            )
            return ProcessConfigurationResult(
                accepted=False,
                sampling_interval=current_interval,
                worker_state=snapshot.worker_state,
                error=error,
            )

        new_interval = float(seconds)

        if new_interval == current_interval:
            return ProcessConfigurationResult(
                accepted=True,
                sampling_interval=current_interval,
                worker_state=snapshot.worker_state,
            )

        if snapshot.worker_state == ProcessWorkerState.STOPPING:
            return self._configuration_rejected(
                snapshot,
                "Sampling interval cannot be changed while stopping.",
            )

        if self._startup_cleanup_pending:
            if (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
            ):
                return self._configuration_rejected(
                    snapshot,
                    "Sampling interval cannot be changed while "
                    "worker cleanup is pending.",
                )

            self._complete_startup_cleanup()
            snapshot = self._read_snapshot()

        if snapshot.worker_state == ProcessWorkerState.FAILED:
            if (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
            ):
                return self._configuration_rejected(
                    snapshot,
                    "Sampling interval cannot be changed while "
                    "a failed worker is still running.",
                )

            self._worker_thread = None
            self._worker = None
            self._session_id = None
            self._stop_event = None
            self._reconfigure_event = None

        elif snapshot.worker_state in (
            ProcessWorkerState.STARTING,
            ProcessWorkerState.RUNNING,
        ):
            if (
                self._worker is None
                or self._worker_thread is None
                or not self._worker_thread.is_alive()
            ):
                return self._configuration_rejected(
                    snapshot,
                    "Process monitoring worker is not available "
                    "for reconfiguration.",
                )

            try:
                self._worker.set_sampling_interval(new_interval)
            except Exception:
                logger.exception(
                    "Could not update process worker sampling interval."
                )
                error = ProcessError(
                    error_code="PROCESS_CONFIGURATION_FAILED",
                    message=(
                        "Process sampling interval could not be updated."
                    ),
                    occurred_at=datetime.now(timezone.utc),
                )
                return ProcessConfigurationResult(
                    accepted=False,
                    sampling_interval=current_interval,
                    worker_state=snapshot.worker_state,
                    error=error,
                )

        self._sampling_interval = new_interval
        self._commit_snapshot(sampling_interval=new_interval)

        logger.info(
            "Process sampling interval updated to %.2f seconds.",
            new_interval,
        )

        return ProcessConfigurationResult(
            accepted=True,
            sampling_interval=new_interval,
            worker_state=self.get_worker_state(),
        )

    def _configuration_rejected(self, snapshot, message):
        error = ProcessError(
            error_code="PROCESS_CONFIGURATION_REJECTED",
            message=message,
            occurred_at=datetime.now(timezone.utc),
        )

        return ProcessConfigurationResult(
            accepted=False,
            sampling_interval=snapshot.sampling_interval,
            worker_state=snapshot.worker_state,
            error=error,
        )

    def _dispatch_timeout_result(self, operation):
        """Build the typed result returned when dispatch cannot begin."""
        snapshot = self._read_snapshot()

        error = ProcessError(
            error_code="PROCESS_REQUEST_DISPATCH_TIMEOUT",
            message=(
                "Process service request could not begin "
                "before its deadline."
            ),
            occurred_at=datetime.now(timezone.utc),
        )

        if operation == "start":
            return ProcessStartResult(
                accepted=False,
                worker_state=snapshot.worker_state,
                error=error,
            )

        if operation == "stop":
            return ProcessStopResult(
                success=False,
                worker_state=snapshot.worker_state,
                error=error,
            )

        if operation == "set_sampling_interval":
            return ProcessConfigurationResult(
                accepted=False,
                sampling_interval=snapshot.sampling_interval,
                worker_state=snapshot.worker_state,
                error=error,
            )

        raise ValueError("Unsupported Process service operation.")

    def _dispatch_request(self, operation, callback):
        """Execute on the owner thread, dispatching safely when necessary."""
        if QThread.currentThread() == self._owner_thread:
            return callback()

        request = {
            "operation": operation,
            "callback": callback,
            "deadline": (
                time.monotonic() + self.REQUEST_DISPATCH_TIMEOUT_SECONDS
            ),
            "lock": threading.Lock(),
            "started_event": threading.Event(),
            "completed_event": threading.Event(),
            "started": False,
            "expired": False,
            "completed": False,
            "result": None,
            "error": None,
        }

        self._request_dispatched.emit(request)
        request["started_event"].wait(
            timeout=self.REQUEST_DISPATCH_TIMEOUT_SECONDS
        )

        with request["lock"]:
            if not request["started"]:
                request["expired"] = True
                return self._dispatch_timeout_result(operation)

        request["completed_event"].wait()

        if request["error"] is not None:
            raise request["error"]

        return request["result"]

    def _execute_dispatched_request(self, request):
        """Execute a queued request once, respecting its dispatch deadline."""
        self._assert_owner_thread()

        with request["lock"]:
            if request["expired"] or request["started"]:
                return

            if time.monotonic() >= request["deadline"]:
                request["expired"] = True
                request["started_event"].set()
                return

            callback = request["callback"]
            if not callable(callback):
                request["expired"] = True
                request["started_event"].set()
                return

            request["started"] = True
            request["started_event"].set()

        try:
            request["result"] = callback()
        except Exception as exc:
            request["error"] = exc
            logger.exception(
                "Dispatched Process service request failed."
            )
        finally:
            with request["lock"]:
                request["completed"] = True
                request["completed_event"].set()

    def start(self):
        """Start process monitoring on the owning Qt thread."""
        return self._dispatch_request(
            "start",
            self._start_on_owner_thread,
        )

    def _start_on_owner_thread(self):
        self._assert_owner_thread()

        snapshot = self._read_snapshot()

        if snapshot.worker_state in (
            ProcessWorkerState.STARTING,
            ProcessWorkerState.RUNNING,
        ):
            return ProcessStartResult(
                accepted=True,
                worker_state=snapshot.worker_state,
            )

        if snapshot.worker_state == ProcessWorkerState.STOPPING:
            return ProcessStartResult(
                accepted=False,
                worker_state=snapshot.worker_state,
                error=ProcessError(
                    error_code="PROCESS_START_REJECTED",
                    message="Process monitoring is still stopping.",
                    occurred_at=datetime.now(timezone.utc),
                ),
            )

        if self._startup_cleanup_pending:
            if (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
            ):
                return ProcessStartResult(
                    accepted=False,
                    worker_state=snapshot.worker_state,
                    error=ProcessError(
                        error_code="PROCESS_START_REJECTED",
                        message="Previous worker cleanup is still pending.",
                        occurred_at=datetime.now(timezone.utc),
                    ),
                )

            self._complete_startup_cleanup()
            snapshot = self._read_snapshot()

        if self._worker_thread is not None:
            if self._worker_thread.is_alive():
                return ProcessStartResult(
                    accepted=False,
                    worker_state=snapshot.worker_state,
                    error=ProcessError(
                        error_code="PROCESS_START_REJECTED",
                        message="Previous process worker is still running.",
                        occurred_at=datetime.now(timezone.utc),
                    ),
                )

            self._worker_thread = None
            self._worker = None
            self._session_id = None
            self._stop_event = None
            self._reconfigure_event = None

        session_id = str(uuid4())
        stop_event = threading.Event()
        reconfigure_event = threading.Event()

        self._session_id = session_id
        self._stop_event = stop_event
        self._reconfigure_event = reconfigure_event
        self._startup_deadline = (
            time.monotonic() + self.STARTUP_TIMEOUT_SECONDS
        )
        self._startup_cleanup_pending = False
        self._shutdown_deadline = None
        self._shutdown_cleanup_pending = False
        self._pending_start = True
        self._pending_stop = False

        def on_started():
            self._worker_started.emit(session_id)

        def on_measurement(measurement):
            self._worker_measurement_received.emit(
                session_id,
                measurement,
            )

        def on_measurement_failure(error_code, message):
            self._worker_measurement_failed.emit(
                session_id,
                error_code,
                message,
            )

        def on_worker_failure():
            self._worker_failed.emit(session_id)

        try:
            worker = ProcessMonitoringWorker(
                sampling_interval=self._sampling_interval,
                on_started=on_started,
                on_measurement=on_measurement,
                on_measurement_failure=on_measurement_failure,
                on_worker_failure=on_worker_failure,
                stop_event=stop_event,
                reconfigure_event=reconfigure_event,
            )

            thread = threading.Thread(
                target=worker.run,
                name=f"ProcessMonitoringWorker-{session_id[:8]}",
                daemon=True,
            )

            self._worker = worker
            self._worker_thread = thread

            self._commit_snapshot(
                worker_state=ProcessWorkerState.STARTING,
                worker_error=None,
            )

            self._startup_timer.start(
                self.CLEANUP_POLL_INTERVAL_MS
            )

            thread.start()

        except Exception:
            logger.exception("Could not start process monitoring worker.")

            self._startup_timer.stop()
            self._worker = None
            self._worker_thread = None
            self._session_id = None
            self._stop_event = None
            self._reconfigure_event = None
            self._startup_deadline = None
            self._pending_start = False
            self._pending_stop = False

            error = ProcessError(
                error_code="PROCESS_START_FAILED",
                message="Process monitoring could not be started.",
                occurred_at=datetime.now(timezone.utc),
            )

            self._commit_snapshot(
                worker_state=ProcessWorkerState.FAILED,
                worker_error=error,
            )

            return ProcessStartResult(
                accepted=False,
                worker_state=ProcessWorkerState.FAILED,
                error=error,
            )

        return ProcessStartResult(
            accepted=True,
            worker_state=ProcessWorkerState.STARTING,
        )

    def _is_current_session(self, session_id):
        return (
            isinstance(session_id, str)
            and session_id == self._session_id
        )

    def _handle_worker_started(self, session_id):
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        if self.get_worker_state() != ProcessWorkerState.STARTING:
            return

        self._startup_timer.stop()
        self._startup_deadline = None
        self._pending_start = False

        self._commit_snapshot(
            worker_state=ProcessWorkerState.RUNNING,
            worker_error=None,
        )

        logger.info("Process monitoring worker started.")

    def _handle_worker_measurement(self, session_id, measurement):
        """Publish a process snapshot and update measurement health."""
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        snapshot = self._read_snapshot()

        if snapshot.worker_state != ProcessWorkerState.RUNNING:
            return

        if not isinstance(measurement, ProcessSnapshot):
            self._handle_worker_measurement_failure(
                session_id,
                "PROCESS_INVALID_SNAPSHOT",
                "Process worker returned an invalid measurement.",
            )
            return

        now_monotonic = time.monotonic()

        if measurement.is_fully_successful:
            self._commit_snapshot(
                measurement_status=ProcessMeasurementStatus.AVAILABLE,
                latest_measurement=measurement,
                last_successful_measurement=measurement,
                last_successful_monotonic=now_monotonic,
                measurement_error=None,
                consecutive_failures=0,
            )

        elif measurement.is_partial:
            first_error = measurement.process_errors[0]

            error = ProcessError(
                error_code=first_error.error_code,
                message=first_error.message,
                occurred_at=first_error.occurred_at,
                pid=first_error.pid,
            )

            self._commit_snapshot(
                measurement_status=ProcessMeasurementStatus.PARTIAL,
                latest_measurement=measurement,
                measurement_error=error,
                consecutive_failures=(
                    self.get_consecutive_failures() + 1
                ),
            )

        else:
            first_error = measurement.process_errors[0]

            error = ProcessError(
                error_code=first_error.error_code,
                message=first_error.message,
                occurred_at=first_error.occurred_at,
                pid=first_error.pid,
            )

            self._commit_snapshot(
                measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
                latest_measurement=measurement,
                measurement_error=error,
                consecutive_failures=(
                    self.get_consecutive_failures() + 1
                ),
            )

        self.measurement_updated.emit(measurement)

    def _handle_worker_measurement_failure(
        self,
        session_id,
        error_code,
        message,
    ):
        """Handle a collection-level measurement failure."""
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        snapshot = self._read_snapshot()

        if snapshot.worker_state not in (
            ProcessWorkerState.STARTING,
            ProcessWorkerState.RUNNING,
        ):
            return

        if not isinstance(error_code, str) or not error_code.strip():
            error_code = "PROCESS_COLLECTION_FAILED"

        if not isinstance(message, str) or not message.strip():
            message = "Process measurements could not be collected."

        error = ProcessError(
            error_code=error_code,
            message=message,
            occurred_at=datetime.now(timezone.utc),
        )

        self._commit_snapshot(
            measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
            latest_measurement=None,
            measurement_error=error,
            consecutive_failures=self.get_consecutive_failures() + 1,
        )

    def _handle_worker_failure(self, session_id):
        """Handle an unexpected process worker failure."""
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        if self.get_worker_state() in (
            ProcessWorkerState.STOPPING,
            ProcessWorkerState.STOPPED,
            ProcessWorkerState.FAILED,
        ):
            return

        self._startup_timer.stop()
        self._startup_deadline = None

        error = ProcessError(
            error_code="PROCESS_WORKER_FAILED",
            message="Process monitoring worker stopped unexpectedly.",
            occurred_at=datetime.now(timezone.utc),
        )

        self._commit_snapshot(
            worker_state=ProcessWorkerState.FAILED,
            measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
            latest_measurement=None,
            measurement_error=error,
            worker_error=error,
            consecutive_failures=self.get_consecutive_failures() + 1,
        )

        if (
            self._worker_thread is not None
            and self._worker_thread.is_alive()
        ):
            self._begin_shutdown()
        else:
            self._complete_shutdown()

        logger.error("Process monitoring worker failed.")



    def stop(self):
        """Stop process monitoring through the owning Qt thread."""
        return self._dispatch_request(
            "stop",
            self._stop_on_owner_thread,
        )

    def _stop_on_owner_thread(self):
        """Request non-blocking worker shutdown."""
        self._assert_owner_thread()
        snapshot = self._read_snapshot()

        if self._startup_cleanup_pending:
            return ProcessStopResult(
                success=False,
                worker_state=snapshot.worker_state,
                error=snapshot.worker_error,
            )

        if snapshot.worker_state == ProcessWorkerState.STOPPING:
            return ProcessStopResult(
                success=False,
                worker_state=snapshot.worker_state,
            )

        if (
            self._worker_thread is None
            or not self._worker_thread.is_alive()
        ):
            self._complete_shutdown()
            return ProcessStopResult(
                success=True,
                worker_state=self.get_worker_state(),
            )

        self._begin_shutdown()

        return ProcessStopResult(
            success=False,
            worker_state=self.get_worker_state(),
        )

    def _begin_shutdown(self):
        """Signal the worker to stop and begin bounded shutdown."""
        self._assert_owner_thread()

        self._startup_timer.stop()
        self._startup_deadline = None
        self._pending_start = False
        self._pending_stop = True

        if self._stop_event is not None:
            self._stop_event.set()

        if self._reconfigure_event is not None:
            self._reconfigure_event.set()

        self._shutdown_deadline = (
            time.monotonic() + self.SHUTDOWN_TIMEOUT_SECONDS
        )
        self._shutdown_cleanup_pending = True

        current_state = self.get_worker_state()

        if current_state != ProcessWorkerState.FAILED:
            self._commit_snapshot(
                worker_state=ProcessWorkerState.STOPPING,
                measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
                latest_measurement=None,
            )

        self._shutdown_timer.start(
            self.CLEANUP_POLL_INTERVAL_MS
        )

    def _complete_startup_cleanup(self):
        """Release startup resources after the worker thread has stopped."""
        self._assert_owner_thread()

        if (
            self._worker_thread is not None
            and self._worker_thread.is_alive()
        ):
            return False

        self._startup_timer.stop()
        self._shutdown_timer.stop()

        self._startup_deadline = None
        self._shutdown_deadline = None
        self._startup_cleanup_pending = False
        self._shutdown_cleanup_pending = False
        self._pending_start = False
        self._pending_stop = False

        self._worker_thread = None
        self._worker = None
        self._session_id = None
        self._stop_event = None
        self._reconfigure_event = None

        return True

    def _complete_shutdown(self):
        """Finalize shutdown after the worker thread has stopped."""
        self._assert_owner_thread()

        if (
            self._worker_thread is not None
            and self._worker_thread.is_alive()
        ):
            return False

        previous_state = self.get_worker_state()

        self._startup_timer.stop()
        self._shutdown_timer.stop()

        self._startup_deadline = None
        self._shutdown_deadline = None
        self._startup_cleanup_pending = False
        self._shutdown_cleanup_pending = False
        self._pending_start = False
        self._pending_stop = False

        self._worker_thread = None
        self._worker = None
        self._session_id = None
        self._stop_event = None
        self._reconfigure_event = None

        if previous_state != ProcessWorkerState.FAILED:
            self._commit_snapshot(
                worker_state=ProcessWorkerState.STOPPED,
                measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
                latest_measurement=None,
                worker_error=None,
            )

            logger.info("Process monitoring worker stopped.")
        else:
            logger.info(
                "Failed process monitoring worker resources cleaned up."
            )

        return True

    def _check_startup_timeout(self):
        """Handle a worker that did not complete startup in time."""
        self._assert_owner_thread()

        if not self._pending_start:
            return

        if self._startup_deadline is None:
            return

        if time.monotonic() < self._startup_deadline:
            return

        self._startup_timer.stop()
        self._startup_deadline = None
        self._pending_start = False
        self._startup_cleanup_pending = True
        self._pending_stop = False

        if self._stop_event is not None:
            self._stop_event.set()

        if self._reconfigure_event is not None:
            self._reconfigure_event.set()

        error = ProcessError(
            error_code="PROCESS_STARTUP_TIMEOUT",
            message="Process monitoring worker startup timed out.",
            occurred_at=datetime.now(timezone.utc),
        )

        self._shutdown_deadline = (
            time.monotonic() + self.SHUTDOWN_TIMEOUT_SECONDS
        )

        self._commit_snapshot(
            worker_state=ProcessWorkerState.FAILED,
            measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
            latest_measurement=None,
            worker_error=error,
        )

        if (
            self._worker_thread is None
            or not self._worker_thread.is_alive()
        ):
            self._complete_startup_cleanup()
        else:
            self._shutdown_timer.start(
                self.CLEANUP_POLL_INTERVAL_MS
            )

        logger.error("Process monitoring worker startup timed out.")

    def _check_shutdown_timeout(self):
        """Monitor normal shutdown and pending startup cleanup."""
        self._assert_owner_thread()

        thread_alive = (
            self._worker_thread is not None
            and self._worker_thread.is_alive()
        )

        if self._startup_cleanup_pending:
            if not thread_alive:
                self._complete_startup_cleanup()
                return

            if (
                self._shutdown_deadline is not None
                and time.monotonic() >= self._shutdown_deadline
            ):
                self._shutdown_deadline = (
                    time.monotonic() + self.SHUTDOWN_TIMEOUT_SECONDS
                )

                logger.error(
                    "Process worker startup cleanup is still pending."
                )

            return

        if not thread_alive:
            self._complete_shutdown()
            return

        if self._shutdown_deadline is None:
            return

        if time.monotonic() < self._shutdown_deadline:
            return

        self._shutdown_deadline = None

        error = ProcessError(
            error_code="PROCESS_SHUTDOWN_TIMEOUT",
            message="Process monitoring worker shutdown timed out.",
            occurred_at=datetime.now(timezone.utc),
        )

        self._commit_snapshot(
            worker_state=ProcessWorkerState.FAILED,
            measurement_status=ProcessMeasurementStatus.UNAVAILABLE,
            latest_measurement=None,
            worker_error=error,
        )

        logger.error("Process monitoring worker shutdown timed out.")



