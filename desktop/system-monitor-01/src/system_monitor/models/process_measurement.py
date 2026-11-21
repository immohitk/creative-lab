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
    executable_path: str | None = None
    service_names: tuple[str, ...] = ()
    metadata_state: str = "unavailable"

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

        if self.executable_path is not None:
            if (
                not isinstance(self.executable_path, str)
                or not self.executable_path.strip()
            ):
                raise ValueError(
                    "Executable path must be a non-empty string or None."
                )

        if not isinstance(self.service_names, (tuple, list)):
            raise TypeError("Service names must be a tuple or list.")

        normalized_services = tuple(self.service_names)

        if any(
            not isinstance(name, str) or not name.strip()
            for name in normalized_services
        ):
            raise ValueError("Service names must be non-empty strings.")

        if len(normalized_services) != len(set(normalized_services)):
            raise ValueError("Service names cannot contain duplicates.")

        object.__setattr__(self, "service_names", normalized_services)

        allowed_metadata_states = {
            "verified",
            "partial",
            "unavailable",
        }

        if not isinstance(self.metadata_state, str):
            raise TypeError("Metadata state must be a string.")

        if self.metadata_state not in allowed_metadata_states:
            raise ValueError(
                "metadata_state must be verified, partial, or unavailable."
            )
