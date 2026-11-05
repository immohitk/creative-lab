from dataclasses import dataclass
from datetime import datetime, timedelta
import math


@dataclass(frozen=True, slots=True)
class MemoryMeasurement:
    total_bytes: int
    used_bytes: int
    available_bytes: int
    free_bytes: int
    percent: float

    swap_total_bytes: int
    swap_used_bytes: int
    swap_free_bytes: int
    swap_percent: float

    sampling_interval: float
    started_at: datetime
    completed_at: datetime

    def __post_init__(self):
        byte_fields = (
            "total_bytes",
            "used_bytes",
            "available_bytes",
            "free_bytes",
            "swap_total_bytes",
            "swap_used_bytes",
            "swap_free_bytes",
        )

        for field_name in byte_fields:
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if self.total_bytes <= 0:
            raise ValueError("Total physical memory must be positive.")

        if self.used_bytes > self.total_bytes:
            raise ValueError("Used physical memory cannot exceed total memory.")

        if self.available_bytes > self.total_bytes:
            raise ValueError("Available physical memory cannot exceed total memory.")

        if self.free_bytes > self.total_bytes:
            raise ValueError("Free physical memory cannot exceed total memory.")

        if self.swap_used_bytes > self.swap_total_bytes:
            raise ValueError("Used swap cannot exceed total swap.")

        if self.swap_free_bytes > self.swap_total_bytes:
            raise ValueError("Free swap cannot exceed total swap.")

        self._validate_percentage(self.percent, "Memory utilization")
        self._validate_percentage(self.swap_percent, "Swap utilization")

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

        object.__setattr__(self, "percent", round(float(self.percent), 2))
        object.__setattr__(self, "swap_percent", round(float(self.swap_percent), 2))
        object.__setattr__(self, "sampling_interval", interval)

    @staticmethod
    def _validate_percentage(value, field_name):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field_name} must be numeric.")

        value = float(value)

        if not math.isfinite(value) or not 0.0 <= value <= 100.0:
            raise ValueError(f"{field_name} must be between 0 and 100.")

    @staticmethod
    def _validate_timestamp(value, field_name):
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} timestamp must be a datetime.")

        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} timestamp must be UTC-aware.")
