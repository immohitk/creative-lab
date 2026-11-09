from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class NetworkError:
    error_code: str
    message: str
    occurred_at: datetime
    consecutive_failures: int = 0
    interface_id: str | None = None

    def __post_init__(self):
        if not isinstance(self.error_code, str) or not self.error_code.strip():
            raise ValueError("Error code must be a non-empty string.")

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Error message must be a non-empty string.")

        if not isinstance(self.occurred_at, datetime):
            raise TypeError("Error timestamp must be a datetime.")

        if (
            self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("Error timestamp must be UTC-aware.")

        if (
            isinstance(self.consecutive_failures, bool)
            or not isinstance(self.consecutive_failures, int)
            or self.consecutive_failures < 0
        ):
            raise ValueError("Consecutive failures must be a non-negative integer.")

        if self.interface_id is not None and (
            not isinstance(self.interface_id, str) or not self.interface_id.strip()
        ):
            raise ValueError("Interface identity must be a non-empty string or None.")
