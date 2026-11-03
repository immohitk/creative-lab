import platform
from datetime import datetime, timezone

import psutil

from system_monitor.models import Availability, CategoryResult


def collect() -> CategoryResult:
    collected_at = datetime.now(timezone.utc)

    try:
        processor_name = platform.processor() or None
        logical_count = psutil.cpu_count(logical=True)
        physical_count = psutil.cpu_count(logical=False)

        data = {
            "name": processor_name,
            "logical_cpu_count": logical_count,
            "physical_core_count": physical_count,
        }

        if not any(data.values()):
            return CategoryResult(
                category="processor",
                status=Availability.UNAVAILABLE,
                data=data,
                collected_at=collected_at,
                error="Processor information is unavailable.",
            )

        return CategoryResult(
            category="processor",
            status=Availability.AVAILABLE,
            data=data,
            collected_at=collected_at,
        )

    except (OSError, RuntimeError) as exc:
        return CategoryResult(
            category="processor",
            status=Availability.UNAVAILABLE,
            data=None,
            collected_at=collected_at,
            error=f"{type(exc).__name__}: {exc}",
        )
