from dataclasses import dataclass
from datetime import datetime, timedelta
import math


@dataclass(frozen=True, slots=True)
class NetworkInterfaceMeasurement:
    interface_id: str
    name: str
    bytes_received: int
    bytes_sent: int
    packets_received: int | None
    packets_sent: int | None
    errors_in: int | None
    errors_out: int | None
    drops_in: int | None
    drops_out: int | None
    download_bytes_per_second: float | None
    upload_bytes_per_second: float | None
    sampled_at: datetime

    def __post_init__(self):
        for field_name in ("interface_id", "name"):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")

        if self.interface_id != self.name:
            raise ValueError("Interface identity must match the provider-reported name.")

        required_counters = ("bytes_received", "bytes_sent")
        optional_counters = (
            "packets_received",
            "packets_sent",
            "errors_in",
            "errors_out",
            "drops_in",
            "drops_out",
        )

        for field_name in required_counters:
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        for field_name in optional_counters:
            value = getattr(self, field_name)

            if value is None:
                continue

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer or None.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        for field_name in (
            "download_bytes_per_second",
            "upload_bytes_per_second",
        ):
            value = getattr(self, field_name)

            if value is None:
                continue

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric or None.")

            value = float(value)

            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{field_name} must be finite and non-negative.")

            object.__setattr__(self, field_name, value)

        if not isinstance(self.sampled_at, datetime):
            raise TypeError("Sampling timestamp must be a datetime.")

        if (
            self.sampled_at.tzinfo is None
            or self.sampled_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("Sampling timestamp must be UTC-aware.")