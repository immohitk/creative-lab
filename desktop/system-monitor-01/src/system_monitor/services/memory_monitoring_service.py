import logging
import math
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt

from system_monitor.models import (
    MemoryConfigurationResult,
    MemoryError,
    MemoryMeasurement,
    MemoryMeasurementStatus,
    MemoryStartResult,
    MemoryStateSnapshot,
    MemoryStopResult,
    MemoryWorkerState,
)
from system_monitor.workers.memory_monitoring_worker import (
    MemoryMonitoringWorker,
)


logger = logging.getLogger(__name__)


class MemoryMonitoringService(QObject):
    """Owns memory monitoring state and coordinates its sampling worker."""

    DEFAULT_SAMPLING_INTERVAL = 1.0
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

        self._snapshot = MemoryStateSnapshot(
            worker_state=MemoryWorkerState.STOPPED,
            measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
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

            new_snapshot = MemoryStateSnapshot(**values)
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
        """Configure memory sampling through the owning Qt thread."""
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
            error = MemoryError(
                error_code="MEMORY_INVALID_SAMPLING_INTERVAL",
                message=(
                    "Sampling interval must be between "
                    "0.5 and 60 seconds."
                ),
                occurred_at=datetime.now(timezone.utc),
            )
            return MemoryConfigurationResult(
                accepted=False,
                sampling_interval=current_interval,
                worker_state=snapshot.worker_state,
                error=error,
            )

        new_interval = float(seconds)

        if new_interval == current_interval:
            return MemoryConfigurationResult(
                accepted=True,
                sampling_interval=current_interval,
                worker_state=snapshot.worker_state,
            )

        if snapshot.worker_state == MemoryWorkerState.STOPPING:
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

        if snapshot.worker_state == MemoryWorkerState.FAILED:
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
            MemoryWorkerState.STARTING,
            MemoryWorkerState.RUNNING,
        ):
            if (
                self._worker is None
                or self._worker_thread is None
                or not self._worker_thread.is_alive()
            ):
                return self._configuration_rejected(
                    snapshot,
                    "Memory monitoring worker is not available "
                    "for reconfiguration.",
                )

            try:
                self._worker.set_sampling_interval(new_interval)
            except Exception:
                logger.exception(
                    "Could not update memory worker sampling interval."
                )
                error = MemoryError(
                    error_code="MEMORY_CONFIGURATION_FAILED",
                    message=(
                        "Memory sampling interval could not be updated."
                    ),
                    occurred_at=datetime.now(timezone.utc),
                )
                return MemoryConfigurationResult(
                    accepted=False,
                    sampling_interval=current_interval,
                    worker_state=snapshot.worker_state,
                    error=error,
                )

        self._sampling_interval = new_interval
        self._commit_snapshot(sampling_interval=new_interval)

        logger.info(
            "Memory sampling interval updated to %.2f seconds.",
            new_interval,
        )

        return MemoryConfigurationResult(
            accepted=True,
            sampling_interval=new_interval,
            worker_state=self.get_worker_state(),
        )

    def _configuration_rejected(self, snapshot, message):
        error = MemoryError(
            error_code="MEMORY_CONFIGURATION_REJECTED",
            message=message,
            occurred_at=datetime.now(timezone.utc),
        )

        return MemoryConfigurationResult(
            accepted=False,
            sampling_interval=snapshot.sampling_interval,
            worker_state=snapshot.worker_state,
            error=error,
        )

    def start(self):
        """Start memory monitoring through the owning Qt thread."""
        return self._dispatch_request(
            "start",
            self._start_on_owner_thread,
        )

    def _start_on_owner_thread(self):
        """Request non-blocking worker startup."""
        self._assert_owner_thread()
        snapshot = self._read_snapshot()

        if snapshot.worker_state in (
            MemoryWorkerState.STARTING,
            MemoryWorkerState.RUNNING,
        ):
            return MemoryStartResult(
                accepted=True,
                worker_state=snapshot.worker_state,
            )

        if snapshot.worker_state == MemoryWorkerState.STOPPING:
            return MemoryStartResult(
                accepted=False,
                worker_state=snapshot.worker_state,
            )

        if self._startup_cleanup_pending:
            if (
                self._worker_thread is not None
                and self._worker_thread.is_alive()
            ):
                return MemoryStartResult(
                    accepted=False,
                    worker_state=MemoryWorkerState.FAILED,
                    error=snapshot.worker_error,
                )

            self._complete_startup_cleanup()
            snapshot = self._read_snapshot()

        if self._worker_thread is not None:
            if self._worker_thread.is_alive():
                return MemoryStartResult(
                    accepted=False,
                    worker_state=MemoryWorkerState.FAILED,
                    error=snapshot.worker_error,
                )

            self._worker_thread = None
            self._worker = None
            self._session_id = None

        self._startup_timer.stop()
        self._shutdown_timer.stop()

        self._stop_event = threading.Event()
        self._reconfigure_event = threading.Event()

        self._session_id = uuid4()
        session_id = self._session_id

        self._worker = MemoryMonitoringWorker(
            session_id=session_id,
            sampling_interval=self._sampling_interval,
            on_measurement=lambda measurement: (
                self._worker_measurement_received.emit(
                    session_id,
                    measurement,
                )
            ),
            on_measurement_failure=lambda code, message: (
                self._worker_measurement_failed.emit(
                    session_id,
                    code,
                    message,
                )
            ),
            on_worker_failure=lambda: (
                self._worker_failed.emit(session_id)
            ),
            stop_event=self._stop_event,
            reconfigure_event=self._reconfigure_event,
            on_started=lambda: self._worker_started.emit(session_id),
        )

        self._startup_deadline = (
            time.monotonic() + self.STARTUP_TIMEOUT_SECONDS
        )
        self._pending_start = True

        self._commit_snapshot(
            worker_state=MemoryWorkerState.STARTING,
            measurement_status=MemoryMeasurementStatus.INITIALIZING,
            worker_error=None,
        )

        self._startup_timer.start()

        self._worker_thread = threading.Thread(
            target=self._worker.run,
            name=f"MemoryMonitoringWorker-{str(session_id)[:8]}",
            daemon=False,
        )

        try:
            self._worker_thread.start()

        except Exception:
            logger.exception(
                "Could not start memory monitoring worker."
            )

            self._startup_timer.stop()
            self._startup_deadline = None
            self._pending_start = False

            error = MemoryError(
                error_code="MEMORY_WORKER_START_FAILED",
                message=(
                    "Memory monitoring worker could not be started."
                ),
                occurred_at=datetime.now(timezone.utc),
            )

            self._commit_snapshot(
                worker_state=MemoryWorkerState.FAILED,
                measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
                worker_error=error,
            )

            return MemoryStartResult(
                accepted=False,
                worker_state=MemoryWorkerState.FAILED,
                error=error,
            )

        return MemoryStartResult(
            accepted=True,
            worker_state=MemoryWorkerState.STARTING,
        )

    def _is_current_session(self, session_id):
        return session_id == self._session_id

    def _handle_worker_started(self, session_id):
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        if self._read_snapshot().worker_state != MemoryWorkerState.STARTING:
            return

        self._startup_timer.stop()
        self._startup_deadline = None
        self._pending_start = False

        self._commit_snapshot(
            worker_state=MemoryWorkerState.RUNNING,
            measurement_status=MemoryMeasurementStatus.INITIALIZING,
            worker_error=None,
            consecutive_failures=0,
        )

        logger.info("Memory monitoring worker started.")

    def _handle_worker_measurement(self, session_id, measurement):
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        if self._read_snapshot().worker_state != MemoryWorkerState.RUNNING:
            return

        try:
            if not isinstance(measurement, MemoryMeasurement):
                raise TypeError(
                    "Worker returned an invalid memory measurement."
                )

        except Exception:
            logger.exception(
                "Memory measurement failed service validation."
            )
            self._handle_worker_measurement_failure(
                session_id,
                "MEMORY_INVALID_READING",
                "Memory measurement failed validation.",
            )
            return

        self._commit_snapshot(
            measurement_status=MemoryMeasurementStatus.AVAILABLE,
            last_successful_measurement=measurement,
            last_successful_monotonic=time.monotonic(),
            measurement_error=None,
            consecutive_failures=0,
        )

        self.measurement_updated.emit(measurement)

    def _handle_worker_measurement_failure(
        self,
        session_id,
        error_code,
        message,
    ):
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        snapshot = self._read_snapshot()

        if snapshot.worker_state not in (
            MemoryWorkerState.STARTING,
            MemoryWorkerState.RUNNING,
        ):
            return

        failure_count = snapshot.consecutive_failures + 1

        error = MemoryError(
            error_code=error_code,
            message=message,
            occurred_at=datetime.now(timezone.utc),
            consecutive_failures=failure_count,
        )

        self._commit_snapshot(
            measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
            measurement_error=error,
            consecutive_failures=failure_count,
        )

    def _handle_worker_failure(self, session_id):
        self._assert_owner_thread()

        if not self._is_current_session(session_id):
            return

        if self._startup_cleanup_pending:
            return

        self._startup_timer.stop()
        self._startup_deadline = None
        self._pending_start = False

        error = MemoryError(
            error_code="MEMORY_WORKER_FAILED",
            message=(
                "Memory monitoring worker stopped unexpectedly."
            ),
            occurred_at=datetime.now(timezone.utc),
            consecutive_failures=self.get_consecutive_failures(),
        )

        self._commit_snapshot(
            worker_state=MemoryWorkerState.FAILED,
            measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
            worker_error=error,
        )

        logger.error("Memory monitoring worker failed.")

    def stop(self):
        """Stop memory monitoring through the owning Qt thread."""
        return self._dispatch_request(
            "stop",
            self._stop_on_owner_thread,
        )

    def _stop_on_owner_thread(self):
        self._assert_owner_thread()
        snapshot = self._read_snapshot()

        if self._startup_cleanup_pending:
            return MemoryStopResult(
                success=False,
                worker_state=MemoryWorkerState.FAILED,
                error=snapshot.worker_error,
            )

        if snapshot.worker_state == MemoryWorkerState.STOPPING:
            return MemoryStopResult(
                success=False,
                worker_state=MemoryWorkerState.STOPPING,
            )

        if self._worker_thread is None:
            self._complete_shutdown()
            return MemoryStopResult(
                success=True,
                worker_state=MemoryWorkerState.STOPPED,
            )

        if not self._worker_thread.is_alive():
            self._complete_shutdown()
            return MemoryStopResult(
                success=True,
                worker_state=MemoryWorkerState.STOPPED,
            )

        self._begin_shutdown()

        return MemoryStopResult(
            success=False,
            worker_state=MemoryWorkerState.STOPPING,
        )

    def _begin_shutdown(self):
        self._assert_owner_thread()
        snapshot = self._read_snapshot()

        if snapshot.worker_state == MemoryWorkerState.STOPPED:
            return

        if self._worker_thread is None:
            self._complete_shutdown()
            return

        if not self._worker_thread.is_alive():
            self._complete_shutdown()
            return

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

        self._commit_snapshot(
            worker_state=MemoryWorkerState.STOPPING,
            measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
        )

        self._shutdown_timer.start()

    def _complete_startup_cleanup(self):
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

        self._pending_start = False
        self._pending_stop = False
        self._startup_cleanup_pending = False

        self._worker_thread = None
        self._worker = None
        self._session_id = None
        self._stop_event = None
        self._reconfigure_event = None

        logger.info(
            "Memory startup-timeout cleanup completed."
        )

        return True

    def _complete_shutdown(self):
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

        self._pending_start = False
        self._pending_stop = False

        self._worker_thread = None
        self._worker = None
        self._session_id = None
        self._stop_event = None
        self._reconfigure_event = None

        self._commit_snapshot(
            worker_state=MemoryWorkerState.STOPPED,
            measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
            worker_error=None,
        )

        logger.info("Memory monitoring worker stopped.")

        return True

    def _check_startup_timeout(self):
        self._assert_owner_thread()

        if self._startup_deadline is None:
            return

        if time.monotonic() < self._startup_deadline:
            return

        self._startup_timer.stop()
        self._startup_deadline = None
        self._pending_start = False

        if self._stop_event is not None:
            self._stop_event.set()

        if self._reconfigure_event is not None:
            self._reconfigure_event.set()

        error = MemoryError(
            error_code="MEMORY_STARTUP_TIMEOUT",
            message="Memory monitoring worker startup timed out.",
            occurred_at=datetime.now(timezone.utc),
        )

        self._startup_cleanup_pending = True
        self._shutdown_deadline = (
            time.monotonic() + self.SHUTDOWN_TIMEOUT_SECONDS
        )

        self._commit_snapshot(
            worker_state=MemoryWorkerState.FAILED,
            measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
            worker_error=error,
        )

        if (
            self._worker_thread is None
            or not self._worker_thread.is_alive()
        ):
            self._complete_startup_cleanup()
        else:
            self._shutdown_timer.start()

        logger.error("Memory monitoring worker startup timed out.")

    def _check_shutdown_timeout(self):
        self._assert_owner_thread()
        worker_thread = self._worker_thread

        if self._startup_cleanup_pending:
            if worker_thread is None or not worker_thread.is_alive():
                self._complete_startup_cleanup()
                return

            if (
                self._shutdown_deadline is not None
                and time.monotonic() >= self._shutdown_deadline
            ):
                self._shutdown_deadline = None
                logger.error(
                    "Memory worker did not terminate within the "
                    "startup cleanup deadline; continuing cleanup polling."
                )

            return

        if self._shutdown_deadline is None:
            return

        if worker_thread is None or not worker_thread.is_alive():
            self._complete_shutdown()
            return

        if time.monotonic() < self._shutdown_deadline:
            return

        self._shutdown_timer.stop()
        self._shutdown_deadline = None

        error = MemoryError(
            error_code="MEMORY_SHUTDOWN_TIMEOUT",
            message="Memory monitoring worker did not stop in time.",
            occurred_at=datetime.now(timezone.utc),
            consecutive_failures=self.get_consecutive_failures(),
        )

        self._commit_snapshot(
            worker_state=MemoryWorkerState.FAILED,
            measurement_status=MemoryMeasurementStatus.UNAVAILABLE,
            worker_error=error,
        )

        logger.error("Memory monitoring worker shutdown timed out.")

    def _dispatch_timeout_result(self, operation):
        snapshot = self._read_snapshot()

        error = MemoryError(
            error_code="MEMORY_REQUEST_DISPATCH_TIMEOUT",
            message=(
                "Memory service request could not begin "
                "before its deadline."
            ),
            occurred_at=datetime.now(timezone.utc),
            consecutive_failures=snapshot.consecutive_failures,
        )

        if operation == "start":
            return MemoryStartResult(
                accepted=False,
                worker_state=snapshot.worker_state,
                error=error,
            )

        if operation == "stop":
            return MemoryStopResult(
                success=False,
                worker_state=snapshot.worker_state,
                error=error,
            )

        if operation == "set_sampling_interval":
            return MemoryConfigurationResult(
                accepted=False,
                sampling_interval=snapshot.sampling_interval,
                worker_state=snapshot.worker_state,
                error=error,
            )

        raise ValueError("Unsupported memory service operation.")

    def _dispatch_request(self, operation, callback):
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
                "Dispatched memory service request failed."
            )

        finally:
            with request["lock"]:
                request["completed"] = True
                request["completed_event"].set()