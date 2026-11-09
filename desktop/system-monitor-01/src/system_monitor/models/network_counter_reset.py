from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class NetworkCounterReset:
    interface_id: str
    occurred_at: datetime
    reset_counters: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.interface_id, str) or not self.interface_id.strip():
            raise ValueError("Interface identity must be a non-empty string.")

        if not isinstance(self.occurred_at, datetime):
            raise TypeError("Reset timestamp must be a datetime.")

        if (
            self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("Reset timestamp must be UTC-aware.")

        if not isinstance(self.reset_counters, (tuple, list)):
            raise TypeError("Reset counters must be a tuple or list.")

        reset_counters = tuple(self.reset_counters)

        if not reset_counters:
            raise ValueError("At least one reset counter must be specified.")

        allowed_counters = {"bytes_received", "bytes_sent"}

        if any(not isinstance(item, str) for item in reset_counters):
            raise TypeError("Every reset counter must be a string.")

        if any(item not in allowed_counters for item in reset_counters):
            raise ValueError("Reset counters contain an unsupported counter.")

        if len(reset_counters) != len(set(reset_counters)):
            raise ValueError("Reset counters cannot contain duplicates.")

        object.__setattr__(self, "reset_counters", reset_counters)
