from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from system_monitor.models.disk_error import DiskError
from system_monitor.models.disk_volume_measurement import DiskVolumeMeasurement


@dataclass(frozen=True, slots=True)
class DiskMeasurement:
    volumes: tuple[DiskVolumeMeasurement, ...]
    volume_errors: tuple[DiskError, ...]
    sampling_interval: float
    started_at: datetime
    completed_at: datetime

    def __post_init__(self):
        if not isinstance(self.volumes, (tuple, list)):
            raise TypeError("Volumes must be a tuple or list.")

        if not isinstance(self.volume_errors, (tuple, list)):
            raise TypeError("Volume errors must be a tuple or list.")

        volumes = tuple(self.volumes)
        errors = tuple(self.volume_errors)

        if any(not isinstance(item, DiskVolumeMeasurement) for item in volumes):
            raise TypeError("Every volume must be a DiskVolumeMeasurement.")

        if any(not isinstance(item, DiskError) for item in errors):
            raise TypeError("Every volume error must be a DiskError.")

        volume_ids = [item.volume_id for item in volumes]

        if len(volume_ids) != len(set(volume_ids)):
            raise ValueError("A measurement cannot contain duplicate volume identities.")

        error_ids = [
            item.volume_id for item in errors if item.volume_id is not None
        ]

        if len(error_ids) != len(set(error_ids)):
            raise ValueError("A measurement cannot contain duplicate volume errors.")

        if set(volume_ids).intersection(error_ids):
            raise ValueError("A volume cannot have both a measurement and an error.")

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

        object.__setattr__(self, "volumes", volumes)
        object.__setattr__(self, "volume_errors", errors)
        object.__setattr__(self, "sampling_interval", interval)

    @staticmethod
    def _validate_timestamp(value, field_name):
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} timestamp must be a datetime.")

        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} timestamp must be UTC-aware.")

    @property
    def is_partial(self) -> bool:
        return bool(self.volumes and self.volume_errors)

    @property
    def is_fully_successful(self) -> bool:
        return not self.volume_errors

    @property
    def is_empty(self) -> bool:
        return not self.volumes and not self.volume_errors

    @property
    def is_unavailable(self) -> bool:
        return not self.volumes and bool(self.volume_errors)
