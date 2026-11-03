from datetime import datetime, timezone

import psutil

from system_monitor.models import Availability, CategoryResult


def collect() -> CategoryResult:
    collected_at = datetime.now(timezone.utc)

    try:
        total_bytes = psutil.virtual_memory().total

        if total_bytes <= 0:
            return CategoryResult(
                category="memory",
                status=Availability.UNAVAILABLE,
                data=None,
                collected_at=collected_at,
                error="Installed physical memory information is unavailable.",
            )

        return CategoryResult(
            category="memory",
            status=Availability.AVAILABLE,
            data={
                "total_bytes": total_bytes,
            },
            collected_at=collected_at,
        )

    except (OSError, RuntimeError) as exc:
        return CategoryResult(
            category="memory",
            status=Availability.UNAVAILABLE,
            data=None,
            collected_at=collected_at,
            error=f"{type(exc).__name__}: {exc}",
        )
