"""Background worker for per-interface network traffic monitoring."""

from __future__ import annotations

import logging
import math
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

import psutil

from system_monitor.models.network_counter_reset import NetworkCounterReset
from system_monitor.models.network_error import NetworkError
from system_monitor.models.network_interface_measurement import (
    NetworkInterfaceMeasurement,
)
from system_monitor.models.network_measurement import NetworkMeasurement


logger = logging.getLogger(__name__)


class NetworkWorkerError(Exception):
    """Represents a collection-level network worker error."""

    def __init__(self, error_code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.error_code = error_code
        self.public_message = public_message


class _WaitResult(Enum):
    TIMEOUT = "timeout"
    RECONFIGURE = "reconfigure"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class _InterfaceBaseline:
    bytes_received: int
    bytes_sent: int
    packets_received: int | None
    packets_sent: int | None
    errors_in: int | None
    errors_out: int | None
    drops_in: int | None
    drops_out: int | None
    monotonic_time: float


class NetworkMonitoringWorker:
    """Collects per-interface network traffic measurements."""

    MIN_INTERVAL = 0.5
    MAX_INTERVAL = 60.0

    def __init__(
        self,
        *,
        sampling_interval: float,
        on_measurement: Callable[[NetworkMeasurement], None],
        on_measurement_failure: Callable[[str, str], None],
        on_worker_failure: Callable[[], None],
        on_started: Callable[[], None] | None = None,
        stop_event: threading.Event | None = None,
        reconfigure_event: threading.Event | None = None,
    ) -> None:
        self.session_id = str(uuid.uuid4())

        self._validate_interval(sampling_interval)

        if not callable(on_measurement):
            raise TypeError("on_measurement must be callable.")

        if not callable(on_measurement_failure):
            raise TypeError("on_measurement_failure must be callable.")

        if not callable(on_worker_failure):
            raise TypeError("on_worker_failure must be callable.")

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

        self._baselines: dict[str, _InterfaceBaseline] = {}

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
            logger.exception(
                "Unexpected network worker failure. Session: %s",
                self.session_id[:8],
            )
            self._safe_callback(self._on_worker_failure)

    def _run_loop(self) -> None:
        if self._stop_event.is_set():
            return

        if self._on_started is not None:
            self._on_started()

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
                measurement = self._collect_measurement(interval)
            except NetworkWorkerError as exc:
                self._report_measurement_failure(
                    exc.error_code,
                    exc.public_message,
                )
                continue
            except Exception:
                logger.exception(
                    "Unexpected network measurement collection failure."
                )
                self._report_measurement_failure(
                    "NETWORK_COLLECTION_FAILED",
                    "Network measurements could not be collected.",
                )
                continue

            if self._stop_event.is_set():
                break

            self._deliver_measurement(measurement)

    def _consume_reconfiguration(self) -> None:
        """Consume a pending interval change under the configuration lock."""
        with self._configuration_lock:
            self._reconfigure_event.clear()

    def _wait_for_next_window(self, interval: float) -> _WaitResult:
        """Wait a full interval; stop takes priority over reconfiguration."""
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

    def _collect_measurement(self, interval: float) -> NetworkMeasurement:
        started_at = datetime.now(timezone.utc)

        try:
            provider_data = psutil.net_io_counters(pernic=True)
        except Exception as exc:
            raise NetworkWorkerError(
                "NETWORK_PROVIDER_FAILED",
                "Network interface counters could not be retrieved.",
            ) from exc

        if not isinstance(provider_data, Mapping):
            raise NetworkWorkerError(
                "NETWORK_PROVIDER_INVALID",
                "The network counter provider returned invalid data.",
            )

        completed_at = datetime.now(timezone.utc)
        sampled_monotonic = time.monotonic()

        interfaces: list[NetworkInterfaceMeasurement] = []
        interface_errors: list[NetworkError] = []
        counter_resets: list[NetworkCounterReset] = []
        baseline_only_ids: list[str] = []

        present_interface_ids: set[str] = set()
        interface_entries = list(provider_data.items())

        # Identify duplicate interface names before processing measurements.
        interface_counts: dict[str, int] = {}

        for interface_name, _ in interface_entries:
            if isinstance(interface_name, str) and interface_name:
                interface_counts[interface_name] = (
                    interface_counts.get(interface_name, 0) + 1
                )

        duplicate_interface_ids = {
            interface_name
            for interface_name, count in interface_counts.items()
            if count > 1
        }

        for interface_name, counters in interface_entries:
            if not isinstance(interface_name, str) or not interface_name:
                raise NetworkWorkerError(
                    "NETWORK_PROVIDER_INVALID",
                    "The network counter provider returned an invalid interface identity.",
                )

            present_interface_ids.add(interface_name)

            if interface_name in duplicate_interface_ids:
                continue

            try:
                current = self._read_counters(counters)
            except (TypeError, ValueError, AttributeError):
                interface_errors.append(
                    self._make_interface_error(
                        interface_name,
                        "NETWORK_INVALID_COUNTERS",
                        "Network counters for an interface were invalid.",
                    )
                )
                continue

            previous = self._baselines.get(interface_name)

            if previous is None:
                self._baselines[interface_name] = self._make_baseline(
                    current,
                    sampled_monotonic,
                )

                interfaces.append(
                    self._make_measurement(
                        interface_name,
                        current,
                        None,
                        None,
                        completed_at,
                    )
                )
                baseline_only_ids.append(interface_name)
                continue

            elapsed = sampled_monotonic - previous.monotonic_time

            if elapsed <= 0:
                self._baselines[interface_name] = self._make_baseline(
                    current,
                    sampled_monotonic,
                )

                interfaces.append(
                    self._make_measurement(
                        interface_name,
                        current,
                        None,
                        None,
                        completed_at,
                    )
                )
                baseline_only_ids.append(interface_name)
                continue

            received_reset = (
                current["bytes_recv"] < previous.bytes_received
            )
            sent_reset = current["bytes_sent"] < previous.bytes_sent

            if received_reset or sent_reset:
                reset_counters: list[str] = []

                if received_reset:
                    reset_counters.append("bytes_received")

                if sent_reset:
                    reset_counters.append("bytes_sent")

                counter_resets.append(
                    NetworkCounterReset(
                        interface_id=interface_name,
                        occurred_at=completed_at,
                        reset_counters=tuple(reset_counters),
                    )
                )

                self._baselines[interface_name] = self._make_baseline(
                    current,
                    sampled_monotonic,
                )

                interfaces.append(
                    self._make_measurement(
                        interface_name,
                        current,
                        None,
                        None,
                        completed_at,
                    )
                )
                continue

            try:
                download_rate = (
                    current["bytes_recv"] - previous.bytes_received
                ) / elapsed

                upload_rate = (
                    current["bytes_sent"] - previous.bytes_sent
                ) / elapsed

            except OverflowError:
                interface_errors.append(
                    self._make_interface_error(
                        interface_name,
                        "NETWORK_INVALID_RATE",
                        "Network traffic rates could not be calculated.",
                    )
                )
                continue

            if not math.isfinite(download_rate) or not math.isfinite(
                upload_rate
            ):
                interface_errors.append(
                    self._make_interface_error(
                        interface_name,
                        "NETWORK_INVALID_RATE",
                        "Network traffic rates could not be calculated.",
                    )
                )
                continue

            self._baselines[interface_name] = self._make_baseline(
                current,
                sampled_monotonic,
            )

            interfaces.append(
                self._make_measurement(
                    interface_name,
                    current,
                    download_rate,
                    upload_rate,
                    completed_at,
                )
            )

        for interface_name in duplicate_interface_ids:
            interface_errors.append(
                self._make_interface_error(
                    interface_name,
                    "NETWORK_DUPLICATE_INTERFACE",
                    "An interface identity was reported more than once.",
                )
            )

            # Ambiguous identity: discard its previous baseline.
            self._baselines.pop(interface_name, None)

        # A successful provider enumeration confirms which interfaces exist.
        # Remove baselines for interfaces that have disappeared.
        for interface_id in tuple(self._baselines):
            if interface_id not in present_interface_ids:
                del self._baselines[interface_id]

        return NetworkMeasurement(
            interfaces=tuple(interfaces),
            interface_errors=tuple(interface_errors),
            counter_resets=tuple(counter_resets),
            baseline_only_interface_ids=tuple(baseline_only_ids),
            sampling_interval=interval,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _read_counters(counters: object) -> dict[str, int | None]:
        required_fields = (
            "bytes_recv",
            "bytes_sent",
        )

        optional_fields = (
            "packets_recv",
            "packets_sent",
            "errin",
            "errout",
            "dropin",
            "dropout",
        )

        values: dict[str, int | None] = {}

        for field in required_fields:
            value = getattr(counters, field)

            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("Invalid required counter.")

            if value < 0:
                raise ValueError("Negative required counter.")

            values[field] = value

        for field in optional_fields:
            value = getattr(counters, field, None)

            if value is None:
                values[field] = None
                continue

            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("Invalid optional counter.")

            if value < 0:
                raise ValueError("Negative optional counter.")

            values[field] = value

        return values

    @staticmethod
    def _make_baseline(
        current: dict[str, int | None],
        monotonic_time: float,
    ) -> _InterfaceBaseline:
        return _InterfaceBaseline(
            bytes_received=current["bytes_recv"],
            bytes_sent=current["bytes_sent"],
            packets_received=current["packets_recv"],
            packets_sent=current["packets_sent"],
            errors_in=current["errin"],
            errors_out=current["errout"],
            drops_in=current["dropin"],
            drops_out=current["dropout"],
            monotonic_time=monotonic_time,
        )

    @staticmethod
    def _make_measurement(
        interface_name: str,
        current: dict[str, int | None],
        download_rate: float | None,
        upload_rate: float | None,
        sampled_at: datetime,
    ) -> NetworkInterfaceMeasurement:
        return NetworkInterfaceMeasurement(
            interface_id=interface_name,
            name=interface_name,
            bytes_received=current["bytes_recv"],
            bytes_sent=current["bytes_sent"],
            packets_received=current["packets_recv"],
            packets_sent=current["packets_sent"],
            errors_in=current["errin"],
            errors_out=current["errout"],
            drops_in=current["dropin"],
            drops_out=current["dropout"],
            download_bytes_per_second=download_rate,
            upload_bytes_per_second=upload_rate,
            sampled_at=sampled_at,
        )

    @staticmethod
    def _make_interface_error(
        interface_name: str,
        error_code: str,
        message: str,
    ) -> NetworkError:
        return NetworkError(
            error_code=error_code,
            message=message,
            occurred_at=datetime.now(timezone.utc),
            interface_id=interface_name,
        )

    def _deliver_measurement(
        self,
        measurement: NetworkMeasurement,
    ) -> None:
        self._safe_callback(self._on_measurement, measurement)

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
    def _safe_callback(
        callback: Callable,
        *args: object,
    ) -> None:
        try:
            callback(*args)
        except Exception:
            logger.exception("Network monitoring callback failed.")
