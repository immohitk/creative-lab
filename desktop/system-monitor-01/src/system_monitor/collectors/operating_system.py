import platform
from datetime import datetime, timezone

from system_monitor.models import Availability, CategoryResult

try:
    import winreg
except ImportError:
    winreg = None


def collect() -> CategoryResult:
    collected_at = datetime.now(timezone.utc)

    if platform.system() != "Windows" or winreg is None:
        return CategoryResult(
            category="operating_system",
            status=Availability.UNSUPPORTED,
            data=None,
            collected_at=collected_at,
            error="Windows operating system information is not supported.",
        )

    version = platform.win32_ver()

    data = {
        "name": platform.system(),
        "version": version[0] or None,
        "release": platform.release() or None,
        "edition": None,
        "build": version[1] or None,
    }

    error = None

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            data["edition"] = winreg.QueryValueEx(
                key, "EditionID"
            )[0]

            data["build"] = winreg.QueryValueEx(
                key, "CurrentBuildNumber"
            )[0]

    except OSError as exc:
        error = f"Windows registry information unavailable: {exc}"

    return CategoryResult(
        category="operating_system",
        status=Availability.AVAILABLE,
        data=data,
        collected_at=collected_at,
        error=error,
    )
