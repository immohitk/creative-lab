import psutil

from system_monitor.collectors import storage
from system_monitor.models import Availability


def test_collect_returns_mounted_volumes(monkeypatch):
    partition = type(
        "Partition",
        (),
        {
            "device": "C:\\",
            "mountpoint": "C:\\",
            "fstype": "NTFS",
        },
    )()

    usage = type(
        "Usage",
        (),
        {
            "total": 249160740864,
            "free": 146768707584,
        },
    )()

    monkeypatch.setattr(
        psutil, "disk_partitions", lambda all=False: [partition]
    )
    monkeypatch.setattr(psutil, "disk_usage", lambda path: usage)

    result = storage.collect()

    assert result.category == "storage"
    assert result.status == Availability.AVAILABLE
    assert len(result.data["volumes"]) == 1
    assert result.data["volumes"][0]["mount_point"] == "C:\\"
    assert result.data["volumes"][0]["filesystem"] == "NTFS"
    assert result.data["volumes"][0]["total_bytes"] == 249160740864
    assert result.data["volumes"][0]["available_bytes"] == 146768707584
    assert result.collected_at.tzinfo is not None
    assert result.error is None


def test_collect_returns_unavailable_when_no_volumes_exist(monkeypatch):
    monkeypatch.setattr(psutil, "disk_partitions", lambda all=False: [])

    result = storage.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data == {"volumes": []}
    assert result.error == "No accessible mounted volumes were found."


def test_collect_skips_inaccessible_volume(monkeypatch):
    accessible_partition = type(
        "Partition",
        (),
        {
            "device": "C:\\",
            "mountpoint": "C:\\",
            "fstype": "NTFS",
        },
    )()

    inaccessible_partition = type(
        "Partition",
        (),
        {
            "device": "D:\\",
            "mountpoint": "D:\\",
            "fstype": "NTFS",
        },
    )()

    usage = type(
        "Usage",
        (),
        {"total": 1000, "free": 500},
    )()

    monkeypatch.setattr(
        psutil,
        "disk_partitions",
        lambda all=False: [accessible_partition, inaccessible_partition],
    )

    def fake_disk_usage(path):
        if path == "D:\\":
            raise PermissionError("Access denied")
        return usage

    monkeypatch.setattr(psutil, "disk_usage", fake_disk_usage)

    result = storage.collect()

    assert result.status == Availability.AVAILABLE
    assert len(result.data["volumes"]) == 1
    assert result.data["volumes"][0]["mount_point"] == "C:\\"


def test_collect_handles_collection_error(monkeypatch):
    def raise_os_error(all=False):
        raise OSError("Storage information unavailable")

    monkeypatch.setattr(psutil, "disk_partitions", raise_os_error)

    result = storage.collect()

    assert result.status == Availability.UNAVAILABLE
    assert result.data is None
    assert "Storage information unavailable" in result.error
