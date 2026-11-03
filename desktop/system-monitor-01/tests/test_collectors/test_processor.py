import platform

import psutil

from system_monitor.collectors import processor
from system_monitor.models import Availability


def test_collect_returns_processor_information(monkeypatch):
    monkeypatch.setattr(
        platform, "processor", lambda: "Intel GenuineIntel"
    )
    monkeypatch.setattr(
        psutil, "cpu_count",
        lambda logical=True: 4 if logical else 2,
    )

    result = processor.collect()

    assert result.category == "processor"
    assert result.status == Availability.AVAILABLE
    assert result.data["name"] == "Intel GenuineIntel"
    assert result.data["logical_cpu_count"] == 4
    assert result.data["physical_core_count"] == 2
    assert result.collected_at.tzinfo is not None
    assert result.error is None


def test_collect_preserves_unavailable_physical_core_count(monkeypatch):
    monkeypatch.setattr(platform, "processor", lambda: "Intel GenuineIntel")
    monkeypatch.setattr(
        psutil, "cpu_count",
        lambda logical=True: 4 if logical else None,
    )

    result = processor.collect()

    assert result.status == Availability.AVAILABLE
    assert result.data["logical_cpu_count"] == 4
    assert result.data["physical_core_count"] is None


def test_collect_returns_unavailable_when_all_information_is_missing(monkeypatch):
    monkeypatch.setattr(platform, "processor", lambda: "")
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=True: None)

    result = processor.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data == {
        "name": None,
        "logical_cpu_count": None,
        "physical_core_count": None,
    }
    assert result.error == "Processor information is unavailable."


def test_collect_handles_collection_error(monkeypatch):
    def raise_os_error(logical=True):
        raise OSError("CPU information unavailable")

    monkeypatch.setattr(platform, "processor", lambda: "Intel GenuineIntel")
    monkeypatch.setattr(psutil, "cpu_count", raise_os_error)

    result = processor.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data is None
    assert "CPU information unavailable" in result.error
