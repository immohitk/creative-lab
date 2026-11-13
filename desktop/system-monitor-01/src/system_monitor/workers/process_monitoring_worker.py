from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
import logging
import math
import threading
import time

import psutil

from system_monitor.models.process_error import ProcessError
from system_monitor.models.process_measurement import ProcessMeasurement
from system_monitor.models.process_snapshot import ProcessSnapshot


logger = logging.getLogger(__name__)

_ACCESS_DENIED = object()


class ProcessWorkerError(Exception):
    """Represents a collection-level process monitoring failure."""

    def __init__(self, error_code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.error_code = error_code
        self.public_message = public_message


class _WaitResult(Enum):
    TIMEOUT = "timeout"
    STOP = "stop"
    RECONFIGURE = "reconfigure"


class ProcessMonitoringWorker:
    """Collects read-only measurements of running processes."""

    MIN_INTERVAL = 0.5
    MAX_INTERVAL = 60.0

    def __init__(
        self,
        *,
        sampling_interval: float = 2.0,
        on_measurement: Callable[[ProcessSnapshot], None],
        on_measurement_failure: Callable[[str, str], None],
        on_worker_failure: Callable[[], None],
        on_started: Callable[[], None] | None = None,
        stop_event: threading.Event | None = None,
        reconfigure_event: threading.Event | None = None,
    ) -> None:
        self._validate_interval(sampling_interval)

        for name, callback in (
            ("on_measurement", on_measurement),
            ("on_measurement_failure", on_measurement_failure),
            ("on_worker_failure", on_worker_failure),
        ):
            if not callable(callback):
                raise TypeError(f"{name} must be callable.")

        if on_started is not None and not callable(on_started):
            raise TypeError("on_started must be callable.")

        self._sampling_interval = float(sampling_interval)
        self._configuration_lock = threading.Lock()

        self._on_measurement = on_measurement
        self._on_measurement_failure = on_measurement_failure
        self._on_worker_failure = on_worker_failure
        self._on_started = on_started

        self._stop_event = stop_event or threading.Event()
        self._reconfigure_event = reconfigure_event or threading.Event()

        # Identity is (PID, process creation time).
        # Value is (cumulative CPU seconds, monotonic sample time).
        self._cpu_baselines: dict[tuple[int, float | None], tuple[float, float]] = {}

    @classmethod
    def _validate_interval(cls, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("sampling_interval must be numeric.")

        if not math.isfinite(value):
            raise ValueError("sampling_interval must be finite.")

        if not cls.MIN_INTERVAL <= value <= cls.MAX_INTERVAL:
            raise ValueError(
                f"sampling_interval must be between "
                f"{cls.MIN_INTERVAL} and {cls.MAX_INTERVAL} seconds."
            )

    @property
    def sampling_interval(self) -> float:
        with self._configuration_lock:
            return self._sampling_interval

    def set_sampling_interval(self, value: float) -> None:
        self._validate_interval(value)

        with self._configuration_lock:
            self._sampling_interval = float(value)
            self._reconfigure_event.set()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        """Run the worker loop and report unexpected worker failures."""
        try:
            self._run_loop()
        except Exception:
            logger.exception("Unexpected process monitoring worker failure.")
            self._safe_callback(self._on_worker_failure)

    def _run_loop(self) -> None:
        if self._stop_event.is_set():
            return

        if self._on_started is not None:
            self._safe_callback(self._on_started)

        while not self._stop_event.is_set():
            interval = self.sampling_interval
            wait_result = self._wait_for_next_window(interval)

            if wait_result is _WaitResult.STOP:
                break

            if wait_result is _WaitResult.RECONFIGURE:
                if self._stop_event.is_set():
                    break

                self._consume_reconfiguration()
                continue

            if self._stop_event.is_set():
                break

            try:
                snapshot = self._collect_measurement(interval)
            except ProcessWorkerError as exc:
                self._report_measurement_failure(
                    exc.error_code,
                    exc.public_message,
                )
                continue
            except Exception:
                logger.exception("Unexpected process collection failure.")
                self._report_measurement_failure(
                    "PROCESS_COLLECTION_FAILED",
                    "Process measurements could not be collected.",
                )
                continue

            if self._stop_event.is_set():
                break

            self._deliver_measurement(snapshot)

    def _consume_reconfiguration(self) -> None:
        with self._configuration_lock:
            self._reconfigure_event.clear()

    def _wait_for_next_window(self, interval: float) -> _WaitResult:
        deadline = time.monotonic() + interval

        while True:
            if self._stop_event.is_set():
                return _WaitResult.STOP

            if self._reconfigure_event.is_set():
                return _WaitResult.RECONFIGURE

            remaining = deadline - time.monotonic()

            if remaining <= 0:
                return _WaitResult.TIMEOUT

            self._stop_event.wait(min(remaining, 0.1))

    def _collect_measurement(self, interval: float) -> ProcessSnapshot:
        started_at = datetime.now(timezone.utc)

        try:
            processes = psutil.process_iter(
                attrs=[
                    "pid",
                    "name",
                    "memory_info",
                    "status",
                    "create_time",
                    "cpu_times",
                ],
                ad_value=_ACCESS_DENIED,
            )
        except Exception as exc:
            raise ProcessWorkerError(
                "PROCESS_PROVIDER_FAILED",
                "Running processes could not be enumerated.",
            ) from exc

        sampled_at = datetime.now(timezone.utc)
        sampled_monotonic = time.monotonic()

        measurements: list[ProcessMeasurement] = []
        errors: list[ProcessError] = []
        current_identities: set[tuple[int, float | None]] = set()

        try:
            for process in processes:
                if self._stop_event.is_set():
                    break

                pid = getattr(process, "pid", None)

                try:
                    info = process.info

                    if not isinstance(info, dict):
                        raise ValueError("Invalid process information.")

                    if any(value is _ACCESS_DENIED for value in info.values()):
                        raise psutil.AccessDenied(pid=pid)

                    process_pid = info.get("pid", pid)

                    if (
                        isinstance(process_pid, bool)
                        or not isinstance(process_pid, int)
                        or process_pid < 0
                    ):
                        raise ValueError("Invalid process PID.")

                    name = info.get("name")
                    if not isinstance(name, str) or not name.strip():
                        raise ValueError("Process name is unavailable.")

                    memory_info = info.get("memory_info")
                    memory_bytes = getattr(memory_info, "rss", None)

                    if (
                        isinstance(memory_bytes, bool)
                        or not isinstance(memory_bytes, int)
                        or memory_bytes < 0
                    ):
                        raise ValueError("Process memory usage is unavailable.")

                    status = info.get("status") or "unknown"
                    if not isinstance(status, str) or not status.strip():
                        status = "unknown"

                    creation_time = info.get("create_time")
                    if creation_time is not None:
                        if (
                            isinstance(creation_time, bool)
                            or not isinstance(creation_time, (int, float))
                            or not math.isfinite(float(creation_time))
                        ):
                            raise ValueError("Invalid process creation time.")
                        creation_time = float(creation_time)

                    identity = (process_pid, creation_time)
                    current_identities.add(identity)

                    cpu_times = info.get("cpu_times")
                    user_time = getattr(cpu_times, "user", None)
                    system_time = getattr(cpu_times, "system", None)

                    cpu_percent = None

                    if (
                        isinstance(user_time, (int, float))
                        and not isinstance(user_time, bool)
                        and isinstance(system_time, (int, float))
                        and not isinstance(system_time, bool)
                    ):
                        cpu_total = float(user_time) + float(system_time)

                        if math.isfinite(cpu_total) and cpu_total >= 0:
                            previous = self._cpu_baselines.get(identity)

                            if previous is not None:
                                previous_cpu, previous_time = previous
                                elapsed = sampled_monotonic - previous_time
                                cpu_delta = cpu_total - previous_cpu

                                if elapsed > 0 and cpu_delta >= 0:
                                    cpu_percent = cpu_delta / elapsed * 100.0

                            self._cpu_baselines[identity] = (
                                cpu_total,
                                sampled_monotonic,
                            )

                    measurements.append(
                        ProcessMeasurement(
                            pid=process_pid,
                            name=name,
                            cpu_percent=cpu_percent,
                            memory_bytes=memory_bytes,
                            status=status,
                            sampled_at=sampled_at,
                        )
                    )

                except psutil.AccessDenied:
                    errors.append(
                        self._make_error(
                            pid,
                            "PROCESS_ACCESS_DENIED",
                            "Access to this process was denied.",
                        )
                    )
                except psutil.ZombieProcess:
                    errors.append(
                        self._make_error(
                            pid,
                            "PROCESS_ZOMBIE",
                            "The process is in a zombie state.",
                        )
                    )
                except psutil.NoSuchProcess:
                    errors.append(
                        self._make_error(
                            pid,
                            "PROCESS_DISAPPEARED",
                            "The process no longer exists.",
                        )
                    )
                except (TypeError, ValueError, AttributeError):
                    errors.append(
                        self._make_error(
                            pid,
                            "PROCESS_INVALID_DATA",
                            "Process information was unavailable or invalid.",
                        )
                    )
                except OSError:
                    errors.append(
                        self._make_error(
                            pid,
                            "PROCESS_READ_FAILED",
                            "Process information could not be read.",
                        )
                    )
                except Exception:
                    logger.exception("Unexpected error reading process PID %s.", pid)
                    errors.append(
                        self._make_error(
                            pid,
                            "PROCESS_READ_FAILED",
                            "Process information could not be read.",
                        )
                    )

        except Exception as exc:
            raise ProcessWorkerError(
                "PROCESS_ENUMERATION_FAILED",
                "Running process enumeration failed.",
            ) from exc

        self._cpu_baselines = {
            identity: baseline
            for identity, baseline in self._cpu_baselines.items()
            if identity in current_identities
        }

        completed_at = datetime.now(timezone.utc)

        return ProcessSnapshot(
            processes=tuple(measurements),
            process_errors=tuple(errors),
            sampling_interval=interval,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _make_error(
        pid: int | None,
        error_code: str,
        message: str,
    ) -> ProcessError:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid < 0:
            pid = None

        return ProcessError(
            error_code=error_code,
            message=message,
            occurred_at=datetime.now(timezone.utc),
            pid=pid,
        )

    def _deliver_measurement(self, snapshot: ProcessSnapshot) -> None:
        self._safe_callback(self._on_measurement, snapshot)

    def _report_measurement_failure(
        self,
        error_code: str,
        message: str,
    ) -> None:
        self._safe_callback(
            self._on_measurement_failure,
            error_code,
            message,
        )

    @staticmethod
    def _safe_callback(callback: Callable, *args: object) -> None:
        try:
            callback(*args)
        except Exception:
            logger.exception("Process monitoring callback failed.")

