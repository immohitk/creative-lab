from datetime import datetime, timezone

import psutil

from system_monitor.models import Availability, CategoryResult


def collect() -> CategoryResult:
    collected_at = datetime.now(timezone.utc)

    try:
        volumes = []

        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)

                volumes.append({
                    "device": partition.device,
                    "mount_point": partition.mountpoint,
                    "filesystem": partition.fstype or None,
                    "total_bytes": usage.total,
                    "available_bytes": usage.free,
                })

            except (OSError, PermissionError):
                continue

        if not volumes:
            return CategoryResult(
                category="storage",
                status=Availability.UNAVAILABLE,
                data={"volumes": []},
                collected_at=collected_at,
                error="No accessible mounted volumes were found.",
            )

        return CategoryResult(
            category="storage",
            status=Availability.AVAILABLE,
            data={"volumes": volumes},
            collected_at=collected_at,
        )

    except (OSError, RuntimeError) as exc:
        return CategoryResult(
            category="storage",
            status=Availability.UNAVAILABLE,
            data=None,
            collected_at=collected_at,
            error=f"{type(exc).__name__}: {exc}",
        )
