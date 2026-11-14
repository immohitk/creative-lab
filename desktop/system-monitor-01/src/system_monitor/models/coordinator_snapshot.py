from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from system_monitor.models.coordinator_status import CoordinatorStatus


@dataclass(frozen=True, slots=True)
class CoordinatorSnapshot:
    """Immutable snapshot of the monitoring coordinator."""

    status: CoordinatorStatus
    service_states: Mapping[str, str]
    active_service_count: int
    failed_service_count: int
    last_error: str | None
    revision: int

    def __post_init__(self):
        if not isinstance(self.status, CoordinatorStatus):
            raise TypeError("status must be a CoordinatorStatus.")

        if not isinstance(self.service_states, Mapping):
            raise TypeError("service_states must be a mapping.")

        states = dict(self.service_states)

        if any(
            not isinstance(name, str) or not name.strip()
            for name in states
        ):
            raise ValueError("Service names must be non-empty strings.")

        if any(
            not isinstance(state, str) or not state.strip()
            for state in states.values()
        ):
            raise ValueError("Service states must be non-empty strings.")

        if (
            isinstance(self.active_service_count, bool)
            or not isinstance(self.active_service_count, int)
            or self.active_service_count < 0
        ):
            raise ValueError("active_service_count must be non-negative.")

        if (
            isinstance(self.failed_service_count, bool)
            or not isinstance(self.failed_service_count, int)
            or self.failed_service_count < 0
        ):
            raise ValueError("failed_service_count must be non-negative.")

        if self.active_service_count > len(states):
            raise ValueError("Active service count exceeds service count.")

        if self.failed_service_count > len(states):
            raise ValueError("Failed service count exceeds service count.")

        if self.active_service_count + self.failed_service_count > len(states):
            raise ValueError("Service counts exceed total service count.")

        if self.last_error is not None and not isinstance(self.last_error, str):
            raise TypeError("last_error must be a string or None.")

        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise ValueError("revision must be a non-negative integer.")

        object.__setattr__(
            self,
            "service_states",
            MappingProxyType(states),
        )
