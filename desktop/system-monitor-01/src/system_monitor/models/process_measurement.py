from dataclasses import dataclass
from datetime import datetime, timedelta
import math


@dataclass(frozen=True, slots=True)
class ProcessMeasurement:
    pid: int
    name: str
    cpu_percent: float | None
    memory_bytes: int
    status: str
    sampled_at: datetime

    def __post_init__(self):
        if (
            isinstance(self.pid, bool)
            or not isinstance(self.pid, int)
            or self.pid < 0
        ):
            raise ValueError("Process PID must be a non-negative integer.")

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Process name must be a non-empty string.")

        if self.cpu_percent is not None:
            if isinstance(self.cpu_percent, bool) or not isinstance(
                self.cpu_percent, (int, float)
            ):
                raise TypeError("CPU percentage must be numeric or None.")

            cpu_percent = float(self.cpu_percent)

            if not math.isfinite(cpu_percent) or cpu_percent < 0.0:
                raise ValueError(
                    "CPU percentage must be finite and non-negative."
                )

            object.__setattr__(self, "cpu_percent", cpu_percent)

        if (
            isinstance(self.memory_bytes, bool)
            or not isinstance(self.memory_bytes, int)
        ):
            raise TypeError("Memory usage must be an integer.")

        if self.memory_bytes < 0:
            raise ValueError("Memory usage cannot be negative.")

        if not isinstance(self.status, str) or not self.status.strip():
            raise ValueError("Process status must be a non-empty string.")

        if not isinstance(self.sampled_at, datetime):
            raise TypeError("Sampling timestamp must be a datetime.")

        if (
            self.sampled_at.tzinfo is None
            or self.sampled_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("Sampling timestamp must be UTC-aware.")
