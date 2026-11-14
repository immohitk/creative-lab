from dataclasses import dataclass

from system_monitor.models.coordinator_status import CoordinatorStatus


@dataclass(frozen=True, slots=True)
class CoordinatorStartResult:
    accepted: bool
    status: CoordinatorStatus
    error: str | None = None

    def __post_init__(self):
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be a bool.")
        if not isinstance(self.status, CoordinatorStatus):
            raise TypeError("status must be a CoordinatorStatus.")
        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be a string or None.")


@dataclass(frozen=True, slots=True)
class CoordinatorStopResult:
    success: bool
    status: CoordinatorStatus
    error: str | None = None

    def __post_init__(self):
        if not isinstance(self.success, bool):
            raise TypeError("success must be a bool.")
        if not isinstance(self.status, CoordinatorStatus):
            raise TypeError("status must be a CoordinatorStatus.")
        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be a string or None.")


@dataclass(frozen=True, slots=True)
class CoordinatorConfigurationResult:
    accepted: bool
    sampling_interval: float
    status: CoordinatorStatus
    error: str | None = None

    def __post_init__(self):
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be a bool.")
        if (
            isinstance(self.sampling_interval, bool)
            or not isinstance(self.sampling_interval, (int, float))
        ):
            raise TypeError("sampling_interval must be numeric.")
        if not 0.5 <= self.sampling_interval <= 60.0:
            raise ValueError(
                "sampling_interval must be between 0.5 and 60 seconds."
            )
        if not isinstance(self.status, CoordinatorStatus):
            raise TypeError("status must be a CoordinatorStatus.")
        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be a string or None.")
