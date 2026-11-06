from enum import Enum


class DiskWorkerState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class DiskMeasurementStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class DiskMeasurementFreshness(str, Enum):
    NO_DATA = "NO_DATA"
    FRESH = "FRESH"
    STALE = "STALE"
