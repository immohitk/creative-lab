from dataclasses import dataclass
import math

from system_monitor.models.memory_error import MemoryError
from system_monitor.models.memory_measurement import MemoryMeasurement
from system_monitor.models.memory_status import (
    MemoryMeasurementFreshness,
    MemoryMeasurementStatus,
    MemoryWorkerState,
)


@dataclass(frozen=True, slots=True)
class MemoryStateSnapshot:
    worker_state: MemoryWorkerState
    measurement_status: MemoryMeasurementStatus
    last_successful_measurement: MemoryMeasurement | None
    last_successful_monotonic: float | None
    measurement_error: MemoryError | None
    worker_error: MemoryError | None
    consecutive_failures: int
    sampling_interval: float
    revision: int

    def __post_init__(self):
        if not isinstance(self.worker_state, MemoryWorkerState):
            raise TypeError("Invalid memory worker state.")

        if not isinstance(self.measurement_status, MemoryMeasurementStatus):
            raise TypeError("Invalid memory measurement status.")

        if (
            self.last_successful_measurement is not None
            and not isinstance(self.last_successful_measurement, MemoryMeasurement)
        ):
            raise TypeError("Invalid last successful measurement.")

        if self.last_successful_monotonic is not None:
            if (
                isinstance(self.last_successful_monotonic, bool)
                or not isinstance(self.last_successful_monotonic, (int, float))
            ):
                raise TypeError("Monotonic reference must be numeric.")

            if not math.isfinite(float(self.last_successful_monotonic)):
                raise ValueError("Monotonic reference must be finite.")

        if (
            (self.last_successful_measurement is None)
            != (self.last_successful_monotonic is None)
        ):
            raise ValueError(
                "Measurement and monotonic reference must both exist or both be None."
            )

        if (
            self.measurement_error is not None
            and not isinstance(self.measurement_error, MemoryError)
        ):
            raise TypeError("Invalid measurement error.")

        if self.worker_error is not None and not isinstance(
            self.worker_error, MemoryError
        ):
            raise TypeError("Invalid worker error.")

        if (
            isinstance(self.consecutive_failures, bool)
            or not isinstance(self.consecutive_failures, int)
            or self.consecutive_failures < 0
        ):
            raise ValueError("Consecutive failures must be a non-negative integer.")

        if (
            isinstance(self.sampling_interval, bool)
            or not isinstance(self.sampling_interval, (int, float))
        ):
            raise TypeError("Sampling interval must be numeric.")

        interval = float(self.sampling_interval)

        if not math.isfinite(interval) or not 0.5 <= interval <= 60.0:
            raise ValueError("Sampling interval must be between 0.5 and 60 seconds.")

        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise ValueError("Revision must be a non-negative integer.")

        object.__setattr__(self, "sampling_interval", interval)

    @property
    def freshness(self) -> MemoryMeasurementFreshness:
        if self.last_successful_measurement is None:
            return MemoryMeasurementFreshness.NO_DATA

        if self.measurement_status == MemoryMeasurementStatus.AVAILABLE:
            return MemoryMeasurementFreshness.FRESH

        return MemoryMeasurementFreshness.STALE

    def last_successful_age(self, now_monotonic: float) -> float | None:
        if self.last_successful_monotonic is None:
            return None

        if (
            isinstance(now_monotonic, bool)
            or not isinstance(now_monotonic, (int, float))
        ):
            raise TypeError("Current monotonic time must be numeric.")

        now = float(now_monotonic)

        if not math.isfinite(now):
            raise ValueError("Current monotonic time must be finite.")

        return max(0.0, now - self.last_successful_monotonic)
