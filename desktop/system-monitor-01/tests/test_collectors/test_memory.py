import psutil

from system_monitor.collectors import memory
from system_monitor.models import Availability


def test_collect_returns_installed_memory(monkeypatch):
    expected_bytes = 12_255_428_608

    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: type("Memory", (), {"total": expected_bytes})(),
    )

    result = memory.collect()

    assert result.category == "memory"
    assert result.status == Availability.AVAILABLE
    assert result.data == {"total_bytes": expected_bytes}
    assert result.collected_at.tzinfo is not None
    assert result.error is None


def test_collect_returns_unavailable_when_memory_is_zero(monkeypatch):
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: type("Memory", (), {"total": 0})(),
    )

    result = memory.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data is None
    assert result.error == (
        "Installed physical memory information is unavailable."
    )


def test_collect_handles_collection_error(monkeypatch):
    def raise_os_error():
        raise OSError("Memory information unavailable")

    monkeypatch.setattr(psutil, "virtual_memory", raise_os_error)

    result = memory.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data is None
    assert "Memory information unavailable" in result.error
