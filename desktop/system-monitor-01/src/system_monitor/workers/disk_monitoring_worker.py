import logging
import math
import threading
import time
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

import psutil

from system_monitor.models import (
    DiskError,
    DiskMeasurement,
    DiskVolumeMeasurement,
)


logger = logging.getLogger(__name__)


class DiskWorkerError(Exception):
    def __init__(self, error_code, message):
        super().__init__(message)
        self.error_code = error_code
        self.public_message = message


class _WaitResult(str, Enum):
    TIMEOUT = "TIMEOUT"
    RECONFIGURE = "RECONFIGURE"
    STOP = "STOP"


class DiskMonitoringWorker:
    """Private disk and mounted-volume sampling worker without Qt dependencies."""

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
            or not DiskMonitoringWorker.MIN_INTERVAL
            <= value
            <= DiskMonitoringWorker.MAX_INTERVAL
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
                "Unexpected disk worker failure. Session: %s",
                str(self.session_id)[:8],
            )

            try:
                self._on_worker_failure()
            except Exception:
                logger.exception("Disk worker failure callback failed.")

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

            except DiskWorkerError as exc:
                self._report_measurement_failure(
                    exc.error_code,
                    exc.public_message,
                )
                continue

            except Exception:
                logger.exception("Unexpected disk measurement error.")

                self._report_measurement_failure(
                    "DISK_MEASUREMENT_FAILED",
                    "Disk measurement failed.",
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
            partitions = psutil.disk_partitions(all=False)

        except Exception as exc:
            raise DiskWorkerError(
                "DISK_PARTITION_ENUMERATION_FAILED",
                "Mounted volume information could not be collected.",
            ) from exc

        if not isinstance(partitions, (list, tuple)):
            raise DiskWorkerError(
                "DISK_INVALID_PARTITION_LIST",
                "Mounted volume information is invalid.",
            )

        volumes = []
        volume_errors = []
        seen_identities = set()

        for partition in partitions:
            if self.stop_event.is_set():
                break

            device = None
            mount_point = None

            try:
                device = getattr(partition, "device", None)
                mount_point = getattr(partition, "mountpoint", None)
                filesystem = getattr(partition, "fstype", None)

                if (
                    not isinstance(device, str)
                    or not device.strip()
                    or not isinstance(mount_point, str)
                    or not mount_point.strip()
                ):
                    raise ValueError("Invalid device or mount point.")

                volume_id = DiskVolumeMeasurement.build_volume_id(
                    device,
                    mount_point,
                )

                if volume_id in seen_identities:
                    volume_errors.append(
                        self._create_error(
                            "DUPLICATE_VOLUME_IDENTITY",
                            "A duplicate device and mount identity was discovered.",
                            device=device,
                            mount_point=mount_point,
                        )
                    )
                    continue

                seen_identities.add(volume_id)

                if filesystem is not None:
                    if not isinstance(filesystem, str):
                        raise TypeError("Filesystem must be a string or None.")

                    filesystem = filesystem.strip() or None

                usage = psutil.disk_usage(mount_point)

                total_bytes = self._validate_bytes(
                    usage.total, "total_bytes", allow_zero=False
                )
                used_bytes = self._validate_bytes(usage.used, "used_bytes")
                free_bytes = self._validate_bytes(usage.free, "free_bytes")
                percent = self._validate_percentage(usage.percent)

                if (
                    used_bytes > total_bytes
                    or free_bytes > total_bytes
                    or used_bytes + free_bytes != total_bytes
                ):
                    raise ValueError("Disk capacity readings are inconsistent.")

                volumes.append(
                    DiskVolumeMeasurement(
                        volume_id=volume_id,
                        device=device,
                        mount_point=mount_point,
                        filesystem=filesystem,
                        total_bytes=total_bytes,
                        used_bytes=used_bytes,
                        free_bytes=free_bytes,
                        percent=percent,
                    )
                )

            except (AttributeError, TypeError, ValueError, OverflowError) as exc:
                logger.debug("Invalid disk volume information: %s", exc)
                volume_errors.append(
                    self._create_error(
                        "DISK_INVALID_PARTITION" if not (isinstance(device, str) and device.strip() and isinstance(mount_point, str) and mount_point.strip()) else "DISK_INVALID_READING",
                        "A mounted volume returned invalid information.",
                        device=device,
                        mount_point=mount_point,
                    )
                )

            except Exception as exc:
                logger.debug("Disk volume collection failed: %s", exc)
                volume_errors.append(
                    self._create_error(
                        "DISK_VOLUME_READ_FAILED",
                        "Disk information for a mounted volume could not be collected.",
                        volume_id=(
                            DiskVolumeMeasurement.build_volume_id(device, mount_point)
                            if isinstance(device, str)
                            and device.strip()
                            and isinstance(mount_point, str)
                            and mount_point.strip()
                            else None
                        ),
                        device=device,
                        mount_point=mount_point,
                    )
                )

        completed_at = datetime.now(timezone.utc)
        completed_monotonic = time.monotonic()

        if completed_monotonic < started_monotonic:
            raise DiskWorkerError(
                "DISK_INVALID_TIMESTAMPS",
                "Disk sampling timestamps are invalid.",
            )

        return DiskMeasurement(
            volumes=tuple(volumes),
            volume_errors=tuple(volume_errors),
            sampling_interval=interval,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _validate_bytes(value, field_name, allow_zero=True):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field_name} must be an integer.")

        if value < 0 or (not allow_zero and value == 0):
            raise ValueError(f"{field_name} is outside the valid range.")

        return value

    @staticmethod
    def _validate_percentage(value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Disk utilization must be numeric.")

        value = float(value)

        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError("Disk utilization is outside the valid range.")

        return value

    @staticmethod
    def _create_error(
        error_code,
        message,
        volume_id=None,
        device=None,
        mount_point=None,
    ):
        return DiskError(
            error_code=error_code,
            message=message,
            occurred_at=datetime.now(timezone.utc),
            volume_id=volume_id,
            device=device if isinstance(device, str) and device.strip() else None,
            mount_point=(
                mount_point
                if isinstance(mount_point, str) and mount_point.strip()
                else None
            ),
        )

    def _deliver_measurement(self, measurement):
        try:
            self._on_measurement(measurement)
        except Exception:
            logger.exception("Disk measurement delivery callback failed.")

    def _report_measurement_failure(self, error_code, message):
        try:
            self._on_measurement_failure(error_code, message)
        except Exception:
            logger.exception("Disk measurement failure callback failed.")
