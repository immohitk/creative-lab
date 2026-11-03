import platform

import pytest

from system_monitor.collectors import operating_system
from system_monitor.models import Availability


def test_collect_returns_windows_information(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        platform,
        "win32_ver",
        lambda: ("10", "19045", "SP0", "Multiprocessor Free"),
    )
    monkeypatch.setattr(platform, "release", lambda: "10")

    class FakeRegistryKey:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()

        @staticmethod
        def OpenKey(root, path):
            return FakeRegistryKey()

        @staticmethod
        def QueryValueEx(key, name):
            values = {
                "EditionID": "Professional",
                "CurrentBuildNumber": "19045",
            }
            return values[name], 1

    monkeypatch.setattr(operating_system, "winreg", FakeWinreg)

    result = operating_system.collect()

    assert result.category == "operating_system"
    assert result.status == Availability.AVAILABLE
    assert result.data["name"] == "Windows"
    assert result.data["version"] == "10"
    assert result.data["release"] == "10"
    assert result.data["edition"] == "Professional"
    assert result.data["build"] == "19045"
    assert result.collected_at.tzinfo is not None
    assert result.error is None


def test_collect_returns_unsupported_on_non_windows(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")

    result = operating_system.collect()

    assert result.status == Availability.UNSUPPORTED
    assert result.data is None


def test_collect_handles_registry_access_failure(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        platform,
        "win32_ver",
        lambda: ("10", "19045", "SP0", "Multiprocessor Free"),
    )
    monkeypatch.setattr(platform, "release", lambda: "10")

    class FakeWinreg:
        HKEY_LOCAL_MACHINE = object()

        @staticmethod
        def OpenKey(root, path):
            raise PermissionError("Access denied")

    monkeypatch.setattr(operating_system, "winreg", FakeWinreg)

    result = operating_system.collect()

    assert result.status == Availability.AVAILABLE
    assert result.data["name"] == "Windows"
    assert result.data["edition"] is None
    assert result.error is not None
    assert "Access denied" in result.error
