import logging
import math
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

import psutil

from system_monitor.models import MemoryMeasurement


logger = logging.getLogger(__name__)


class MemoryWorkerError(Exception):
    def __init__(self, error_code, message):
        super().__init__(message)
        self.error_code = error_code
        self.public_message = message


class _WaitResult(str, Enum):
    TIMEOUT = "TIMEOUT"
    RECONFIGURE = "RECONFIGURE"
    STOP = "STOP"


class MemoryMonitoringWorker:
    """Private RAM and swap sampling worker without Qt dependencies."""

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
        self._started = False

    @staticmethod
    def _validate_interval(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Sampling interval must be numeric.")

        value = float(value)

        if (
            not math.isfinite(value)
            or not MemoryMonitoringWorker.MIN_INTERVAL
            <= value
            <= MemoryMonitoringWorker.MAX_INTERVAL
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
                "Unexpected memory worker failure. Session: %s",
                str(self.session_id)[:8],
            )

            try:
                self._on_worker_failure()
            except Exception:
                logger.exception("Memory worker failure callback failed.")

    def _run_loop(self):
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
                continue

            if self.stop_event.is_set():
                break

            try:
                measurement = self._collect_measurement(interval)

            except MemoryWorkerError as exc:
                self._report_measurement_failure(
                    exc.error_code,
                    exc.public_message,
                )
                continue

            except Exception:
                logger.exception("Unexpected memory measurement error.")

                self._report_measurement_failure(
                    "MEMORY_MEASUREMENT_FAILED",
                    "Memory measurement failed.",
                )
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

    def _collect_measurement(self, interval):
        started_at = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()

        try:
            virtual_memory = psutil.virtual_memory()
            swap_memory = psutil.swap_memory()

        except Exception as exc:
            raise MemoryWorkerError(
                "MEMORY_MEASUREMENT_FAILED",
                "Physical memory or swap information could not be collected.",
            ) from exc

        completed_at = datetime.now(timezone.utc)
        completed_monotonic = time.monotonic()

        if completed_monotonic < started_monotonic:
            raise MemoryWorkerError(
                "MEMORY_INVALID_READING",
                "Memory sampling timestamps are invalid.",
            )

        try:
            total_bytes = self._validate_bytes(
                virtual_memory.total, "total_bytes", allow_zero=False
            )
            used_bytes = self._validate_bytes(
                virtual_memory.used, "used_bytes"
            )
            available_bytes = self._validate_bytes(
                virtual_memory.available, "available_bytes"
            )
            free_bytes = self._validate_bytes(
                virtual_memory.free, "free_bytes"
            )
            percent = self._validate_percentage(
                virtual_memory.percent, "percent"
            )

            swap_total_bytes = self._validate_bytes(
                swap_memory.total, "swap_total_bytes"
            )
            swap_used_bytes = self._validate_bytes(
                swap_memory.used, "swap_used_bytes"
            )
            swap_free_bytes = self._validate_bytes(
                swap_memory.free, "swap_free_bytes"
            )
            swap_percent = self._validate_percentage(
                swap_memory.percent, "swap_percent"
            )

            if used_bytes > total_bytes:
                raise ValueError("Used physical memory exceeds total memory.")

            if available_bytes > total_bytes:
                raise ValueError("Available physical memory exceeds total memory.")

            if free_bytes > total_bytes:
                raise ValueError("Free physical memory exceeds total memory.")

            if swap_used_bytes > swap_total_bytes:
                raise ValueError("Used swap exceeds total swap.")

            if swap_free_bytes > swap_total_bytes:
                raise ValueError("Free swap exceeds total swap.")

            if swap_total_bytes == 0 and (
                swap_used_bytes != 0
                or swap_free_bytes != 0
                or swap_percent != 0.0
            ):
                raise ValueError("Zero-sized swap must have zero usage.")

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
                sampling_interval=interval,
                started_at=started_at,
                completed_at=completed_at,
            )

        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            raise MemoryWorkerError(
                "MEMORY_INVALID_READING",
                "Physical memory or swap readings are invalid.",
            ) from exc

    @staticmethod
    def _validate_bytes(value, field_name, allow_zero=True):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer.")

        if value < 0 or (not allow_zero and value == 0):
            raise ValueError(f"{field_name} is outside the valid range.")

        return value

    @staticmethod
    def _validate_percentage(value, field_name):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field_name} must be numeric.")

        value = float(value)

        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError(f"{field_name} is outside the valid range.")

        return value

    def _deliver_measurement(self, measurement):
        try:
            self._on_measurement(measurement)
        except Exception:
            logger.exception("Memory measurement delivery callback failed.")

    def _report_measurement_failure(self, error_code, message):
        try:
            self._on_measurement_failure(error_code, message)
        except Exception:
            logger.exception("Memory measurement failure callback failed.")
