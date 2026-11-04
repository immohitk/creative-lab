from dataclasses import dataclass

from system_monitor.models.cpu_error import CpuError
from system_monitor.models.cpu_status import CpuWorkerState


@dataclass(frozen=True, slots=True)
class StartResult:
    accepted: bool
    worker_state: CpuWorkerState
    error: CpuError | None = None

    def __post_init__(self):
        if not isinstance(self.accepted, bool):
            raise TypeError("Accepted must be a boolean.")

        if not isinstance(self.worker_state, CpuWorkerState):
            raise TypeError("Worker state must be a CpuWorkerState.")

        if self.error is not None and not isinstance(self.error, CpuError):
            raise TypeError("Error must be a CpuError or None.")


@dataclass(frozen=True, slots=True)
class StopResult:
    success: bool
    worker_state: CpuWorkerState
    error: CpuError | None = None

    def __post_init__(self):
        if not isinstance(self.success, bool):
            raise TypeError("Success must be a boolean.")

        if not isinstance(self.worker_state, CpuWorkerState):
            raise TypeError("Worker state must be a CpuWorkerState.")

        if self.error is not None and not isinstance(self.error, CpuError):
            raise TypeError("Error must be a CpuError or None.")


@dataclass(frozen=True, slots=True)
class ConfigurationResult:
    accepted: bool
    sampling_interval: float
    worker_state: CpuWorkerState
    error: CpuError | None = None

    def __post_init__(self):
        import math

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

        if not isinstance(self.worker_state, CpuWorkerState):
            raise TypeError("Worker state must be a CpuWorkerState.")

        if self.error is not None and not isinstance(self.error, CpuError):
            raise TypeError("Error must be a CpuError or None.")

        object.__setattr__(self, "sampling_interval", interval)
