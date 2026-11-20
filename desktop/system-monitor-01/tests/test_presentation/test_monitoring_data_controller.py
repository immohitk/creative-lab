"""Tests for service-to-presentation data coordination."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal

from system_monitor.presentation.monitoring_data_controller import (
    MonitoringDataController,
)


class FakeService(QObject):
    current_state_published = Signal(object)
    measurement_updated = Signal(object)
    measurement_status_changed = Signal(object)
    measurement_error_changed = Signal(object)
    worker_error_changed = Signal(object)
    worker_state_changed = Signal(object)

    def __init__(self, snapshot):
        super().__init__()
        self.snapshot = snapshot

    def publish_current_state(self):
        self.current_state_published.emit(self.snapshot)
        return self.snapshot

    def publish_measurement(self, measurement, snapshot):
        self.snapshot = snapshot
        self.measurement_updated.emit(measurement)


def _snapshot(status="AVAILABLE", freshness="FRESH", measurement=None):
    return SimpleNamespace(
        measurement_status=SimpleNamespace(value=status),
        freshness=SimpleNamespace(value=freshness),
        latest_measurement=measurement,
        last_successful_measurement=measurement,
        measurement_error=None,
    )


def _services():
    return {
        name: FakeService(_snapshot("INITIALIZING", "NO_DATA"))
        for name in ("cpu", "memory", "disk", "network", "process")
    }


def test_controller_publishes_initial_service_snapshots():
    services = _services()
    controller = MonitoringDataController(services)

    assert controller.service_names() == (
        "cpu", "memory", "disk", "network", "process"
    )
    assert controller.snapshot("cpu") is services["cpu"].snapshot
    assert controller.status("cpu") == "INITIALIZING"
    assert controller.freshness("cpu") == "NO_DATA"


def test_controller_tracks_cpu_measurements_and_bounded_history():
    services = _services()
    controller = MonitoringDataController(services)
    timestamp = datetime(2026, 11, 19, tzinfo=timezone.utc)
    measurement = SimpleNamespace(
        completed_at=timestamp,
        overall_percent=37.5,
    )
    snapshot = _snapshot(measurement=measurement)

    services["cpu"].publish_measurement(measurement, snapshot)

    assert controller.measurement("cpu") is measurement
    assert controller.history("cpu")[0].timestamp == timestamp
    assert controller.history("cpu")[0].value == 37.5
    assert controller.status("cpu") == "AVAILABLE"


def test_controller_uses_last_successful_measurement_when_latest_is_unavailable():
    services = _services()
    controller = MonitoringDataController(services)
    successful = object()
    services["disk"].snapshot = SimpleNamespace(
        measurement_status=SimpleNamespace(value="UNAVAILABLE"),
        freshness=SimpleNamespace(value="STALE"),
        latest_measurement=None,
        last_successful_measurement=successful,
        measurement_error="collection failed",
    )
    services["disk"].publish_current_state()

    assert controller.measurement("disk") is successful
    assert controller.freshness("disk") == "STALE"


def test_controller_rejects_incomplete_service_mapping():
    with pytest.raises(ValueError, match="exactly"):
        MonitoringDataController({"cpu": FakeService(_snapshot())})


def test_controller_ignores_duplicate_snapshot_publication():
    services = _services()
    controller = MonitoringDataController(services)
    emitted = []
    controller.data_changed.connect(emitted.append)
    snapshot = services["cpu"].snapshot

    services["cpu"].current_state_published.emit(snapshot)

    assert emitted == []
