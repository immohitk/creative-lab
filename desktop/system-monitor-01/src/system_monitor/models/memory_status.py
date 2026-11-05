from enum import Enum


class MemoryWorkerState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class MemoryMeasurementStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class MemoryMeasurementFreshness(str, Enum):
    NO_DATA = "NO_DATA"
    FRESH = "FRESH"
    STALE = "STALE"
