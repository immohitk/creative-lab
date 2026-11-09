from enum import Enum


class NetworkWorkerState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class NetworkMeasurementStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class NetworkMeasurementFreshness(str, Enum):
    NO_DATA = "NO_DATA"
    FRESH = "FRESH"
    STALE = "STALE"
