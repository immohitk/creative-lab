import platform
import socket

import pytest

from system_monitor.collectors import machine
from system_monitor.models import Availability


def test_collect_returns_machine_information(monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "TEST-PC")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(platform, "architecture", lambda: ("64bit", "WindowsPE"))

    result = machine.collect()

    assert result.category == "machine"
    assert result.status == Availability.AVAILABLE
    assert result.data["hostname"] == "TEST-PC"
    assert result.data["native_architecture"] == "AMD64"
    assert result.data["process_architecture"] == "64bit"
    assert result.collected_at.tzinfo is not None
    assert result.error is None


def test_collect_handles_missing_hostname(monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "")

    result = machine.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data is None
    assert result.error == "Hostname information is unavailable."


def test_collect_handles_os_error(monkeypatch):
    def raise_os_error():
        raise OSError("Machine information unavailable")

    monkeypatch.setattr(socket, "gethostname", raise_os_error)

    result = machine.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data is None
    assert "Machine information unavailable" in result.error


def test_collect_does_not_expose_network_identifiers(monkeypatch):
    monkeypatch.setattr(socket, "gethostname", lambda: "TEST-PC")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(platform, "architecture", lambda: ("64bit", "WindowsPE"))

    result = machine.collect()

    assert "ip_address" not in result.data
    assert "mac_address" not in result.data
