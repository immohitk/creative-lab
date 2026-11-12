from enum import Enum


class ProcessWorkerState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class ProcessMeasurementStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class ProcessMeasurementFreshness(str, Enum):
    NO_DATA = "NO_DATA"
    FRESH = "FRESH"
    STALE = "STALE"
