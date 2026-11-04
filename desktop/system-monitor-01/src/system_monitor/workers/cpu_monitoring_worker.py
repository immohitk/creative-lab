import logging
import math
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

import psutil

from system_monitor.models import CpuMeasurement


logger = logging.getLogger(__name__)


class CpuWorkerError(Exception):
    def __init__(self, error_code, message):
        super().__init__(message)
        self.error_code = error_code
        self.public_message = message


class _WaitResult(str, Enum):
    TIMEOUT = "TIMEOUT"
    RECONFIGURE = "RECONFIGURE"
    STOP = "STOP"


class CpuMonitoringWorker:
    """Private CPU sampling worker without Qt dependencies."""

    MIN_INTERVAL = 0.5
    MAX_INTERVAL = 60.0

    def __init__(
        self,
        session_id: UUID,
        sampling_interval: float,
        on_measurement,
        on_measurement_failure,
        on_worker_failure,
        stop_event: threading.Event | None = None,
        reconfigure_event: threading.Event | None = None,
        on_started=None,
    ):
        if not isinstance(session_id, UUID):
            raise TypeError("Session ID must be a UUID.")

        self._validate_interval(sampling_interval)

        if not callable(on_measurement):
            raise TypeError("Measurement callback must be callable.")

        if not callable(on_measurement_failure):
            raise TypeError("Measurement failure callback must be callable.")

        if not callable(on_worker_failure):
            raise TypeError("Worker failure callback must be callable.")

        if on_started is not None and not callable(on_started):
            raise TypeError("Startup callback must be callable.")

        self.session_id = session_id
        self._sampling_interval = float(sampling_interval)

        self._on_measurement = on_measurement
        self._on_measurement_failure = on_measurement_failure
        self._on_worker_failure = on_worker_failure
        self._on_started = on_started

        self.stop_event = (
            stop_event if stop_event is not None else threading.Event()
        )
        self.reconfigure_event = (
            reconfigure_event
            if reconfigure_event is not None
            else threading.Event()
        )

        self._configuration_lock = threading.Lock()
        self._logical_cpu_count = None
        self._started = False

    @staticmethod
    def _validate_interval(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Sampling interval must be numeric.")

        value = float(value)

        if (
            not math.isfinite(value)
            or not CpuMonitoringWorker.MIN_INTERVAL
            <= value
            <= CpuMonitoringWorker.MAX_INTERVAL
        ):
            raise ValueError(
                "Sampling interval must be between 0.5 and 60 seconds."
            )

    @property
    def sampling_interval(self):
        with self._configuration_lock:
            return self._sampling_interval

    def set_sampling_interval(self, seconds):
        self._validate_interval(seconds)

        with self._configuration_lock:
            self._sampling_interval = float(seconds)
            self.reconfigure_event.set()

    def run(self):
        try:
            self._run_loop()

        except Exception:
            logger.exception(
                "Unexpected CPU worker failure. Session: %s",
                str(self.session_id)[:8],
            )

            try:
                self._on_worker_failure()
            except Exception:
                logger.exception("CPU worker failure callback failed.")

    def _run_loop(self):
        self._logical_cpu_count = self._get_logical_cpu_count()

        # Initial priming is part of startup. Failure here is a startup failure.
        self._prime_counters()

        if self.stop_event.is_set():
            return

        self._started = True

        if self._on_started is not None:
            self._on_started()

        while not self.stop_event.is_set():
            interval = self.sampling_interval

            wait_result = self._wait_for_next_window(interval)

            if wait_result == _WaitResult.STOP:
                break

            if wait_result == _WaitResult.RECONFIGURE:
                if self.stop_event.is_set():
                    break

                self._consume_reconfiguration()
                self._recover_counter_initialization()
                continue

            if self.stop_event.is_set():
                break

            try:
                measurement = self._collect_measurement(interval)

            except CpuWorkerError as exc:
                self._report_measurement_failure(
                    exc.error_code,
                    exc.public_message,
                )

                if self.stop_event.is_set():
                    break

                self._recover_counter_initialization()
                continue

            except Exception:
                logger.exception("Unexpected CPU measurement error.")

                self._report_measurement_failure(
                    "CPU_MEASUREMENT_FAILED",
                    "CPU measurement failed.",
                )

                if self.stop_event.is_set():
                    break

                self._recover_counter_initialization()
                continue

            if self.stop_event.is_set():
                break

            self._deliver_measurement(measurement)

    def _wait_for_next_window(self, interval):
        """Wait a full interval; stop takes priority over reconfiguration."""
        deadline = time.monotonic() + interval

        while True:
            if self.stop_event.is_set():
                return _WaitResult.STOP

            if self.reconfigure_event.is_set():
                return _WaitResult.RECONFIGURE

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                return _WaitResult.TIMEOUT

            self.stop_event.wait(min(remaining, 0.1))

    def _consume_reconfiguration(self):
        with self._configuration_lock:
            self.reconfigure_event.clear()

    def _recover_counter_initialization(self):
        """Retry counter initialization without terminating the worker."""
        while not self.stop_event.is_set():
            try:
                self._logical_cpu_count = self._get_logical_cpu_count()
                self._prime_counters()
                return

            except CpuWorkerError as exc:
                self._report_measurement_failure(
                    exc.error_code,
                    exc.public_message,
                )

            except Exception:
                logger.exception("CPU counter recovery failed.")

                self._report_measurement_failure(
                    "CPU_MEASUREMENT_FAILED",
                    "CPU counters could not be reinitialized.",
                )

            wait_result = self._wait_for_next_window(
                self.sampling_interval
            )

            if wait_result == _WaitResult.STOP:
                return

            if wait_result == _WaitResult.RECONFIGURE:
                self._consume_reconfiguration()

    @staticmethod
    def _get_logical_cpu_count():
        try:
            count = psutil.cpu_count(logical=True)

        except Exception as exc:
            raise CpuWorkerError(
                "CPU_PER_CORE_UNAVAILABLE",
                "Logical CPU information is unavailable.",
            ) from exc

        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count <= 0
        ):
            raise CpuWorkerError(
                "CPU_PER_CORE_UNAVAILABLE",
                "Logical CPU information is unavailable.",
            )

        return count

    def _prime_counters(self):
        try:
            readings = psutil.cpu_percent(interval=None, percpu=True)

        except Exception as exc:
            raise CpuWorkerError(
                "CPU_MEASUREMENT_FAILED",
                "CPU counters could not be initialized.",
            ) from exc

        if not isinstance(readings, (list, tuple)) or not readings:
            raise CpuWorkerError(
                "CPU_PER_CORE_UNAVAILABLE",
                "Per-core CPU counters are unavailable.",
            )

        if len(readings) != self._logical_cpu_count:
            raise CpuWorkerError(
                "CPU_PER_CORE_UNAVAILABLE",
                "Per-core CPU count does not match logical CPU topology.",
            )

    def _collect_measurement(self, interval):
        count_before = self._get_logical_cpu_count()

        if count_before != self._logical_cpu_count:
            self._handle_topology_change(count_before)

        started_at = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()

        try:
            # Only the per-core API supplies the authoritative measurement.
            per_cpu = psutil.cpu_percent(interval=None, percpu=True)

        except Exception as exc:
            raise CpuWorkerError(
                "CPU_MEASUREMENT_FAILED",
                "CPU utilization could not be collected.",
            ) from exc

        completed_at = datetime.now(timezone.utc)
        completed_monotonic = time.monotonic()

        count_after = self._get_logical_cpu_count()

        if count_after != count_before:
            self._handle_topology_change(count_after)

        if (
            not isinstance(per_cpu, (list, tuple))
            or len(per_cpu) != self._logical_cpu_count
        ):
            raise CpuWorkerError(
                "CPU_PER_CORE_UNAVAILABLE",
                "Per-core CPU readings are incomplete.",
            )

        validated_readings = tuple(
            self._validate_percentage(value)
            for value in per_cpu
        )

        calculated_overall = (
            math.fsum(validated_readings) / len(validated_readings)
        )

        if not math.isfinite(calculated_overall):
            raise CpuWorkerError(
                "CPU_INVALID_READING",
                "CPU utilization readings are invalid.",
            )

        if completed_monotonic < started_monotonic:
            raise CpuWorkerError(
                "CPU_INVALID_READING",
                "CPU sampling timestamps are invalid.",
            )

        return CpuMeasurement(
            overall_percent=calculated_overall,
            per_cpu_percent=validated_readings,
            logical_cpu_count=self._logical_cpu_count,
            sampling_interval=interval,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _validate_percentage(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CpuWorkerError(
                "CPU_INVALID_READING",
                "CPU utilization readings are invalid.",
            )

        value = float(value)

        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise CpuWorkerError(
                "CPU_INVALID_READING",
                "CPU utilization readings are outside the valid range.",
            )

        return value

    def _handle_topology_change(self, new_count):
        logger.debug(
            "CPU topology changed from %s to %s logical CPUs.",
            self._logical_cpu_count,
            new_count,
        )

        self._logical_cpu_count = new_count

        raise CpuWorkerError(
            "CPU_TOPOLOGY_CHANGED",
            "CPU topology changed; measurements are being reinitialized.",
        )

    def _deliver_measurement(self, measurement):
        try:
            self._on_measurement(measurement)
        except Exception:
            logger.exception("CPU measurement delivery callback failed.")

    def _report_measurement_failure(self, error_code, message):
        try:
            self._on_measurement_failure(error_code, message)
        except Exception:
            logger.exception("CPU measurement failure callback failed.")
