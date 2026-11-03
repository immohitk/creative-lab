import platform
import socket
from datetime import datetime, timezone

from system_monitor.models import Availability, CategoryResult


def collect() -> CategoryResult:
    collected_at = datetime.now(timezone.utc)

    try:
        data = {
            "hostname": socket.gethostname(),
            "native_architecture": platform.machine() or None,
            "process_architecture": platform.architecture()[0] or None,
        }

        if not data["hostname"]:
            return CategoryResult(
                category="machine",
                status=Availability.UNAVAILABLE,
                data=None,
                collected_at=collected_at,
                error="Hostname information is unavailable.",
            )

        return CategoryResult(
            category="machine",
            status=Availability.AVAILABLE,
            data=data,
            collected_at=collected_at,
        )

    except OSError as exc:
        return CategoryResult(
            category="machine",
            status=Availability.UNAVAILABLE,
            data=None,
            collected_at=collected_at,
            error=f"{type(exc).__name__}: {exc}",
        )
