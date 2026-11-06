from dataclasses import dataclass
import math

from system_monitor.models.disk_error import DiskError
from system_monitor.models.disk_measurement import DiskMeasurement
from system_monitor.models.disk_status import (
    DiskMeasurementFreshness,
    DiskMeasurementStatus,
    DiskWorkerState,
)


@dataclass(frozen=True, slots=True)
class DiskStateSnapshot:
    worker_state: DiskWorkerState
    measurement_status: DiskMeasurementStatus
    latest_measurement: DiskMeasurement | None
    last_successful_measurement: DiskMeasurement | None
    last_successful_monotonic: float | None
    measurement_error: DiskError | None
    worker_error: DiskError | None
    consecutive_failures: int
    sampling_interval: float
    revision: int

    def __post_init__(self):
        if not isinstance(self.worker_state, DiskWorkerState):
            raise TypeError("Invalid disk worker state.")

        if not isinstance(self.measurement_status, DiskMeasurementStatus):
            raise TypeError("Invalid disk measurement status.")

        for field_name in ("latest_measurement", "last_successful_measurement"):
            value = getattr(self, field_name)

            if value is not None and not isinstance(value, DiskMeasurement):
                raise TypeError(f"Invalid {field_name.replace('_', ' ')}.")

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
            and not isinstance(self.measurement_error, DiskError)
        ):
            raise TypeError("Invalid measurement error.")

        if self.worker_error is not None and not isinstance(
            self.worker_error, DiskError
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

        if (
            self.measurement_status == DiskMeasurementStatus.AVAILABLE
            and (
                self.latest_measurement is None
                or not self.latest_measurement.is_fully_successful
            )
        ):
            raise ValueError("AVAILABLE status requires a fully successful measurement.")

        if (
            self.measurement_status == DiskMeasurementStatus.PARTIAL
            and (
                self.latest_measurement is None
                or not self.latest_measurement.is_partial
            )
        ):
            raise ValueError("PARTIAL status requires a partial measurement.")

        if (
            self.measurement_status == DiskMeasurementStatus.UNAVAILABLE
            and (
                self.latest_measurement is not None
                and not self.latest_measurement.is_unavailable
            )
        ):
            raise ValueError("UNAVAILABLE status requires an unavailable measurement.")

        if (
            self.measurement_status == DiskMeasurementStatus.INITIALIZING
            and self.latest_measurement is not None
        ):
            raise ValueError("INITIALIZING status cannot contain a latest measurement.")

        if (
            self.last_successful_measurement is not None
            and not self.last_successful_measurement.is_fully_successful
        ):
            raise ValueError("Last successful measurement must be fully successful.")

        object.__setattr__(self, "sampling_interval", interval)

    @property
    def freshness(self) -> DiskMeasurementFreshness:
        if self.last_successful_measurement is None:
            return DiskMeasurementFreshness.NO_DATA

        if self.measurement_status == DiskMeasurementStatus.AVAILABLE:
            return DiskMeasurementFreshness.FRESH

        return DiskMeasurementFreshness.STALE

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
