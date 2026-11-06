from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True)
class DiskError:
    error_code: str
    message: str
    occurred_at: datetime
    consecutive_failures: int = 0
    volume_id: str | None = None
    device: str | None = None
    mount_point: str | None = None

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

        for field_name in ("volume_id", "device", "mount_point"):
            value = getattr(self, field_name)

            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{field_name} must be a non-empty string or None.")
