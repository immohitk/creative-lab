from enum import Enum


class CoordinatorStatus(str, Enum):
    """Lifecycle status of the monitoring coordinator."""

    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPING = "STOPPING"
    FAILED = "FAILED"
