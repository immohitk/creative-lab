from dataclasses import dataclass
import math

from system_monitor.models.disk_error import DiskError
from system_monitor.models.disk_status import DiskWorkerState


@dataclass(frozen=True, slots=True)
class DiskStartResult:
    accepted: bool
    worker_state: DiskWorkerState
    error: DiskError | None = None

    def __post_init__(self):
        if not isinstance(self.accepted, bool):
            raise TypeError("Accepted must be a boolean.")

        if not isinstance(self.worker_state, DiskWorkerState):
            raise TypeError("Worker state must be a DiskWorkerState.")

        if self.error is not None and not isinstance(self.error, DiskError):
            raise TypeError("Error must be a DiskError or None.")


@dataclass(frozen=True, slots=True)
class DiskStopResult:
    success: bool
    worker_state: DiskWorkerState
    error: DiskError | None = None

    def __post_init__(self):
        if not isinstance(self.success, bool):
            raise TypeError("Success must be a boolean.")

        if not isinstance(self.worker_state, DiskWorkerState):
            raise TypeError("Worker state must be a DiskWorkerState.")

        if self.error is not None and not isinstance(self.error, DiskError):
            raise TypeError("Error must be a DiskError or None.")


@dataclass(frozen=True, slots=True)
class DiskConfigurationResult:
    accepted: bool
    sampling_interval: float
    worker_state: DiskWorkerState
    error: DiskError | None = None

    def __post_init__(self):
        if not isinstance(self.accepted, bool):
            raise TypeError("Accepted must be a boolean.")

        if (
            isinstance(self.sampling_interval, bool)
            or not isinstance(self.sampling_interval, (int, float))
        ):
            raise TypeError("Sampling interval must be numeric.")

        interval = float(self.sampling_interval)

        if not math.isfinite(interval) or not 0.5 <= interval <= 60.0:
            raise ValueError("Sampling interval must be between 0.5 and 60 seconds.")

        if not isinstance(self.worker_state, DiskWorkerState):
            raise TypeError("Worker state must be a DiskWorkerState.")

        if self.error is not None and not isinstance(self.error, DiskError):
            raise TypeError("Error must be a DiskError or None.")

        object.__setattr__(self, "sampling_interval", interval)
