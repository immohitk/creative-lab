from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class DiskVolumeMeasurement:
    volume_id: str
    device: str
    mount_point: str
    filesystem: str | None
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent: float

    def __post_init__(self):
        for field_name in ("volume_id", "device", "mount_point"):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")

        expected_volume_id = self.build_volume_id(self.device, self.mount_point)

        if self.volume_id != expected_volume_id:
            raise ValueError("Volume identity does not match device and mount point.")

        if self.filesystem is not None and not isinstance(self.filesystem, str):
            raise TypeError("Filesystem must be a string or None.")

        if self.filesystem is not None and not self.filesystem.strip():
            raise ValueError("Filesystem must be a non-empty string or None.")

        for field_name in ("total_bytes", "used_bytes", "free_bytes"):
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{field_name} must be an integer.")

            if value < 0:
                raise ValueError(f"{field_name} cannot be negative.")

        if self.total_bytes <= 0:
            raise ValueError("Total volume capacity must be positive.")

        if self.used_bytes > self.total_bytes:
            raise ValueError("Used bytes cannot exceed total capacity.")

        if self.free_bytes > self.total_bytes:
            raise ValueError("Free bytes cannot exceed total capacity.")

        if self.used_bytes + self.free_bytes != self.total_bytes:
            raise ValueError("Used and free bytes must equal total capacity.")

        if isinstance(self.percent, bool) or not isinstance(
            self.percent, (int, float)
        ):
            raise TypeError("Disk utilization must be numeric.")

        percent = float(self.percent)

        if not math.isfinite(percent) or not 0.0 <= percent <= 100.0:
            raise ValueError("Disk utilization must be between 0 and 100.")

        object.__setattr__(self, "percent", round(percent, 2))

    @staticmethod
    def build_volume_id(device: str, mount_point: str) -> str:
        if not isinstance(device, str) or not device.strip():
            raise ValueError("Device must be a non-empty string.")

        if not isinstance(mount_point, str) or not mount_point.strip():
            raise ValueError("Mount point must be a non-empty string.")

        return f"{device}::{mount_point}"

