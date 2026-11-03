from datetime import datetime, timezone

import psutil

from system_monitor.models import Availability, CategoryResult


def collect() -> CategoryResult:
    collected_at = datetime.now(timezone.utc)

    try:
        interface_stats = psutil.net_if_stats()
        interface_names = psutil.net_if_addrs()

        interfaces = []

        for name in interface_names:
            stats = interface_stats.get(name)

            interfaces.append({
                "name": name,
                "is_up": stats.isup if stats is not None else None,
                "speed_mbps": stats.speed if stats is not None else None,
                "mtu": stats.mtu if stats is not None else None,
            })

        if not interfaces:
            return CategoryResult(
                category="network_interfaces",
                status=Availability.UNAVAILABLE,
                data={"interfaces": []},
                collected_at=collected_at,
                error="No network interfaces were found.",
            )

        return CategoryResult(
            category="network_interfaces",
            status=Availability.AVAILABLE,
            data={"interfaces": interfaces},
            collected_at=collected_at,
        )

    except (OSError, RuntimeError) as exc:
        return CategoryResult(
            category="network_interfaces",
            status=Availability.UNAVAILABLE,
            data=None,
            collected_at=collected_at,
            error=f"{type(exc).__name__}: {exc}",
        )
