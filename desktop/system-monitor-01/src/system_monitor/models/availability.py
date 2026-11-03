from enum import Enum


class Availability(str, Enum):
    AVAILABLE = "available"
    ZERO = "zero"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    ACCESS_DENIED = "access_denied"
    INITIALIZING = "initializing"
