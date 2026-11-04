from enum import Enum


class CpuWorkerState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class CpuMeasurementStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class CpuMeasurementFreshness(str, Enum):
    NO_DATA = "NO_DATA"
    FRESH = "FRESH"
    STALE = "STALE"