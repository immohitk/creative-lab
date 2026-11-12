from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class ProcessError:
    error_code: str
    message: str
    occurred_at: datetime
    pid: int | None = None

    def __post_init__(self):
        if not isinstance(self.error_code, str) or not self.error_code.strip():
            raise ValueError("Error code must be a non-empty string.")

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Error message must be a non-empty string.")

        if self.pid is not None and (
            isinstance(self.pid, bool)
            or not isinstance(self.pid, int)
            or self.pid < 0
        ):
            raise ValueError("Process PID must be a non-negative integer or None.")

        if not isinstance(self.occurred_at, datetime):
            raise TypeError("Error timestamp must be a datetime.")

        if (
            self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("Error timestamp must be UTC-aware.")
