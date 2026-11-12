from dataclasses import dataclass
import math

from system_monitor.models.process_error import ProcessError
from system_monitor.models.process_status import ProcessWorkerState


@dataclass(frozen=True, slots=True)
class ProcessStartResult:
    accepted: bool
    worker_state: ProcessWorkerState
    error: ProcessError | None = None

    def __post_init__(self):
        if not isinstance(self.accepted, bool):
            raise TypeError("Accepted must be a boolean.")

        if not isinstance(self.worker_state, ProcessWorkerState):
            raise TypeError("Worker state must be a ProcessWorkerState.")

        if self.error is not None and not isinstance(self.error, ProcessError):
            raise TypeError("Error must be a ProcessError or None.")


@dataclass(frozen=True, slots=True)
class ProcessStopResult:
    success: bool
    worker_state: ProcessWorkerState
    error: ProcessError | None = None

    def __post_init__(self):
        if not isinstance(self.success, bool):
            raise TypeError("Success must be a boolean.")

        if not isinstance(self.worker_state, ProcessWorkerState):
            raise TypeError("Worker state must be a ProcessWorkerState.")

        if self.error is not None and not isinstance(self.error, ProcessError):
            raise TypeError("Error must be a ProcessError or None.")


@dataclass(frozen=True, slots=True)
class ProcessConfigurationResult:
    accepted: bool
    sampling_interval: float
    worker_state: ProcessWorkerState
    error: ProcessError | None = None

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

        if not isinstance(self.worker_state, ProcessWorkerState):
            raise TypeError("Worker state must be a ProcessWorkerState.")

        if self.error is not None and not isinstance(self.error, ProcessError):
            raise TypeError("Error must be a ProcessError or None.")

        object.__setattr__(self, "sampling_interval", interval)
