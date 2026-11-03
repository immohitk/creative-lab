import psutil

from system_monitor.collectors import network_interfaces
from system_monitor.models import Availability


def test_collect_returns_network_interfaces(monkeypatch):
    interface_addresses = {
        "Ethernet": [],
        "Wi-Fi": [],
    }

    interface_stats = {
        "Ethernet": type(
            "Stats",
            (),
            {"isup": False, "speed": 0, "mtu": 1500},
        )(),
        "Wi-Fi": type(
            "Stats",
            (),
            {"isup": True, "speed": 780, "mtu": 1500},
        )(),
    }

    monkeypatch.setattr(
        psutil, "net_if_addrs", lambda: interface_addresses
    )
    monkeypatch.setattr(
        psutil, "net_if_stats", lambda: interface_stats
    )

    result = network_interfaces.collect()

    assert result.category == "network_interfaces"
    assert result.status == Availability.AVAILABLE
    assert len(result.data["interfaces"]) == 2

    ethernet, wifi = result.data["interfaces"]

    assert ethernet["name"] == "Ethernet"
    assert ethernet["is_up"] is False
    assert ethernet["speed_mbps"] == 0

    assert wifi["name"] == "Wi-Fi"
    assert wifi["is_up"] is True
    assert wifi["speed_mbps"] == 780

    assert result.collected_at.tzinfo is not None
    assert result.error is None


def test_collect_returns_unavailable_when_no_interfaces_exist(monkeypatch):
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: {})
    monkeypatch.setattr(psutil, "net_if_stats", lambda: {})

    result = network_interfaces.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data == {"interfaces": []}
    assert result.error == "No network interfaces were found."


def test_collect_handles_missing_interface_statistics(monkeypatch):
    monkeypatch.setattr(
        psutil, "net_if_addrs", lambda: {"Wi-Fi": []}
    )
    monkeypatch.setattr(psutil, "net_if_stats", lambda: {})

    result = network_interfaces.collect()

    assert result.status == Availability.AVAILABLE
    assert result.data["interfaces"][0] == {
        "name": "Wi-Fi",
        "is_up": None,
        "speed_mbps": None,
        "mtu": None,
    }


def test_collect_handles_collection_error(monkeypatch):
    def raise_os_error():
        raise OSError("Network information unavailable")

    monkeypatch.setattr(psutil, "net_if_addrs", raise_os_error)

    result = network_interfaces.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data is None
    assert "Network information unavailable" in result.error


def test_collect_does_not_expose_ip_or_mac_addresses(monkeypatch):
    address = type(
        "Address",
        (),
        {
            "family": 2,
            "address": "192.168.1.10",
        },
    )()

    monkeypatch.setattr(
        psutil, "net_if_addrs", lambda: {"Wi-Fi": [address]}
    )
    monkeypatch.setattr(
        psutil,
        "net_if_stats",
        lambda: {
            "Wi-Fi": type(
                "Stats",
                (),
                {"isup": True, "speed": 780, "mtu": 1500},
            )()
        },
    )

    result = network_interfaces.collect()

    assert result.status == Availability.AVAILABLE
    assert "192.168.1.10" not in str(result.data)
    assert "ip_address" not in str(result.data)
    assert "mac_address" not in str(result.data)
