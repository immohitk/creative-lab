from dataclasses import dataclass
from datetime import datetime, timedelta
import math


@dataclass(frozen=True, slots=True)
class CpuMeasurement:
    overall_percent: float
    per_cpu_percent: tuple[float, ...]
    logical_cpu_count: int
    sampling_interval: float
    started_at: datetime
    completed_at: datetime

    def __post_init__(self):
        if (
            isinstance(self.logical_cpu_count, bool)
            or not isinstance(self.logical_cpu_count, int)
            or self.logical_cpu_count <= 0
        ):
            raise ValueError("Logical CPU count must be a positive integer.")

        if not isinstance(self.per_cpu_percent, (tuple, list)):
            raise TypeError("Per-CPU readings must be a tuple or list.")

        readings = tuple(self.per_cpu_percent)

        if len(readings) != self.logical_cpu_count:
            raise ValueError("Per-CPU reading count does not match logical CPU count.")

        validated_readings = tuple(
            self._validate_percentage(value, "Per-CPU utilization")
            for value in readings
        )

        overall = self._validate_percentage(
            self.overall_percent,
            "Overall CPU utilization",
        )

        if (
            isinstance(self.sampling_interval, bool)
            or not isinstance(self.sampling_interval, (int, float))
        ):
            raise TypeError("Sampling interval must be numeric.")

        interval = float(self.sampling_interval)

        if not math.isfinite(interval) or not 0.5 <= interval <= 60.0:
            raise ValueError("Sampling interval must be between 0.5 and 60 seconds.")

        self._validate_timestamp(self.started_at, "Start")
        self._validate_timestamp(self.completed_at, "Completion")

        if self.completed_at < self.started_at:
            raise ValueError("Completion timestamp cannot precede start timestamp.")

        object.__setattr__(self, "overall_percent", round(overall, 2))
        object.__setattr__(self, "per_cpu_percent", validated_readings)
        object.__setattr__(self, "sampling_interval", interval)

    @staticmethod
    def _validate_percentage(value, field_name):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field_name} must be numeric.")

        value = float(value)

        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError(f"{field_name} must be between 0 and 100.")

        return round(value, 2)

    @staticmethod
    def _validate_timestamp(value, field_name):
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} timestamp must be a datetime.")

        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} timestamp must be UTC-aware.")
