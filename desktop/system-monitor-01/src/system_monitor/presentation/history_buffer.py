"""Bounded, timestamp-ordered metric history for presentation charts."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
import math


@dataclass(frozen=True, slots=True)
class HistorySample:
    timestamp: datetime
    value: float


class HistoryBuffer:
    """Store a fixed number of finite metric samples in timestamp order."""

    def __init__(self, capacity: int = 120):
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("capacity must be an integer")
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self._samples = deque(maxlen=capacity)

    @property
    def capacity(self) -> int:
        return self._samples.maxlen

    def __len__(self) -> int:
        return len(self._samples)

    def __iter__(self):
        return iter(tuple(self._samples))

    def samples(self) -> tuple[HistorySample, ...]:
        return tuple(self._samples)

    def append(self, timestamp: datetime, value: float) -> bool:
        """Append a sample; reject invalid or out-of-order data.

        Returns False for a duplicate timestamp, preventing duplicate chart points
        when a service republishes its current state.
        """
        if not isinstance(timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("value must be numeric")
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            raise ValueError("value must be finite")
        if self._samples:
            previous = self._samples[-1].timestamp
            if timestamp < previous:
                raise ValueError("timestamp cannot precede the latest sample")
            if timestamp == previous:
                return False
        self._samples.append(HistorySample(timestamp, numeric_value))
        return True

    def clear(self) -> None:
        self._samples.clear()
