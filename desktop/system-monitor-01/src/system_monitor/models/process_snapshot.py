from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from system_monitor.models.process_error import ProcessError
from system_monitor.models.process_measurement import ProcessMeasurement


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    processes: tuple[ProcessMeasurement, ...]
    process_errors: tuple[ProcessError, ...]
    sampling_interval: float
    started_at: datetime
    completed_at: datetime

    def __post_init__(self):
        for field_name, expected_type in (
            ("processes", ProcessMeasurement),
            ("process_errors", ProcessError),
        ):
            value = getattr(self, field_name)

            if not isinstance(value, (tuple, list)):
                raise TypeError(f"{field_name} must be a tuple or list.")

            normalized = tuple(value)

            if any(not isinstance(item, expected_type) for item in normalized):
                raise TypeError(
                    f"Every item in {field_name} must be a "
                    f"{expected_type.__name__}."
                )

            object.__setattr__(self, field_name, normalized)

        process_ids = [process.pid for process in self.processes]

        if len(process_ids) != len(set(process_ids)):
            raise ValueError("A snapshot cannot contain duplicate process PIDs.")

        error_ids = [
            error.pid for error in self.process_errors if error.pid is not None
        ]

        if len(error_ids) != len(set(error_ids)):
            raise ValueError("A snapshot cannot contain duplicate process errors.")

        if set(process_ids).intersection(error_ids):
            raise ValueError(
                "A process cannot have both a measurement and an error."
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

        object.__setattr__(self, "sampling_interval", interval)

    @staticmethod
    def _validate_timestamp(value, field_name):
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} timestamp must be a datetime.")

        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} timestamp must be UTC-aware.")

    @property
    def is_partial(self) -> bool:
        return bool(self.processes and self.process_errors)

    @property
    def is_fully_successful(self) -> bool:
        return not self.process_errors

    @property
    def is_empty(self) -> bool:
        return not self.processes and not self.process_errors

    @property
    def is_unavailable(self) -> bool:
        return not self.processes and bool(self.process_errors)
