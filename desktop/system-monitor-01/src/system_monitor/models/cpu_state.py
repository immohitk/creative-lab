from dataclasses import dataclass
import math

from system_monitor.models.cpu_error import CpuError
from system_monitor.models.cpu_measurement import CpuMeasurement
from system_monitor.models.cpu_status import (
    CpuMeasurementFreshness,
    CpuMeasurementStatus,
    CpuWorkerState,
)


@dataclass(frozen=True, slots=True)
class CpuStateSnapshot:
    worker_state: CpuWorkerState
    measurement_status: CpuMeasurementStatus
    last_successful_measurement: CpuMeasurement | None
    last_successful_monotonic: float | None
    measurement_error: CpuError | None
    worker_error: CpuError | None
    consecutive_failures: int
    sampling_interval: float
    revision: int

    def __post_init__(self):
        if not isinstance(self.worker_state, CpuWorkerState):
            raise TypeError("Invalid CPU worker state.")

        if not isinstance(self.measurement_status, CpuMeasurementStatus):
            raise TypeError("Invalid CPU measurement status.")

        if (
            self.last_successful_measurement is not None
            and not isinstance(self.last_successful_measurement, CpuMeasurement)
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
            and not isinstance(self.measurement_error, CpuError)
        ):
            raise TypeError("Invalid measurement error.")

        if self.worker_error is not None and not isinstance(
            self.worker_error, CpuError
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
    def freshness(self) -> CpuMeasurementFreshness:
        if self.last_successful_measurement is None:
            return CpuMeasurementFreshness.NO_DATA

        if self.measurement_status == CpuMeasurementStatus.AVAILABLE:
            return CpuMeasurementFreshness.FRESH

        return CpuMeasurementFreshness.STALE

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
