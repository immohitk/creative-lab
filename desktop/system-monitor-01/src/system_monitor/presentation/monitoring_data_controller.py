"""Bridge monitoring-service snapshots and measurements to presentation widgets."""

from PySide6.QtCore import QObject, Signal


class MonitoringDataController(QObject):
    """Own presentation-facing state and bounded metric histories.

    Services remain responsible for collection and lifecycle. This controller
    only subscribes to their public signals and exposes immutable history views.
    """

    data_changed = Signal(str)

    HISTORY_CAPACITY = 120

    def __init__(self, services: dict, parent=None):
        super().__init__(parent)
        from system_monitor.presentation.history_buffer import HistoryBuffer

        required = {"cpu", "memory", "disk", "network", "process"}
        if set(services) != required:
            raise ValueError(f"services must contain exactly {sorted(required)}")

        self._services = dict(services)
        self._snapshots = {}
        self._histories = {
            "cpu": HistoryBuffer(self.HISTORY_CAPACITY),
            "memory": HistoryBuffer(self.HISTORY_CAPACITY),
            "disk": HistoryBuffer(self.HISTORY_CAPACITY),
            "network_download": HistoryBuffer(self.HISTORY_CAPACITY),
            "network_upload": HistoryBuffer(self.HISTORY_CAPACITY),
        }

        for name, service in self._services.items():
            service.current_state_published.connect(
                lambda snapshot, key=name: self._handle_snapshot(key, snapshot)
            )
            service.measurement_updated.connect(
                lambda measurement, key=name: self._handle_measurement(
                    key, measurement
                )
            )
            for signal_name in (
                "measurement_status_changed",
                "measurement_error_changed",
                "worker_error_changed",
                "worker_state_changed",
            ):
                getattr(service, signal_name).connect(
                    lambda _value, key=name: self._publish_service_state(key)
                )
            self._publish_service_state(name)

    def _publish_service_state(self, name: str):
        service = self._services[name]
        service.publish_current_state()

    def _handle_snapshot(self, name: str, snapshot):
        # Services may publish the same immutable snapshot through multiple
        # state signals during one measurement transition. Ignore duplicates.
        if self._snapshots.get(name) is snapshot:
            return
        self._snapshots[name] = snapshot
        self.data_changed.emit(name)

    def _handle_measurement(self, name: str, measurement):
        self._append_history(name, measurement)
        self._publish_service_state(name)

    def _safe_append(self, history_name, timestamp, value):
        try:
            return self._histories[history_name].append(timestamp, value)
        except (TypeError, ValueError):
            # A wall-clock adjustment or malformed provider sample must never
            # interrupt a Qt signal handler or the GUI event loop.
            return False

    def _append_history(self, name: str, measurement):
        if name == "cpu":
            self._safe_append(
                "cpu", measurement.completed_at, measurement.overall_percent
            )
        elif name == "memory":
            self._safe_append(
                "memory", measurement.completed_at, measurement.percent
            )
        elif name == "disk":
            volumes = measurement.volumes
            if volumes:
                total = sum(volume.total_bytes for volume in volumes)
                used = sum(volume.used_bytes for volume in volumes)
                if total:
                    self._safe_append(
                        "disk", measurement.completed_at, used * 100.0 / total
                    )
        elif name == "network":
            interfaces = measurement.interfaces
            timestamp = measurement.completed_at
            download_values = [
                item.download_bytes_per_second
                for item in interfaces
                if item.download_bytes_per_second is not None
            ]
            upload_values = [
                item.upload_bytes_per_second
                for item in interfaces
                if item.upload_bytes_per_second is not None
            ]
            if download_values:
                self._safe_append(
                    "network_download", timestamp, sum(download_values)
                )
            if upload_values:
                self._safe_append(
                    "network_upload", timestamp, sum(upload_values)
                )

    def snapshot(self, name: str):
        return self._snapshots.get(name)

    def measurement(self, name: str):
        snapshot = self.snapshot(name)
        if snapshot is None:
            return None
        latest = getattr(snapshot, "latest_measurement", None)
        status = getattr(snapshot.measurement_status, "value", snapshot.measurement_status)
        if str(status) == "UNAVAILABLE":
            return getattr(snapshot, "last_successful_measurement", None)
        if latest is not None:
            return latest
        return getattr(snapshot, "last_successful_measurement", None)

    def status(self, name) -> str:
        snapshot = self.snapshot(name)
        if snapshot is None:
            return "INITIALIZING"
        value = getattr(snapshot.measurement_status, "value", snapshot.measurement_status)
        return str(value)

    def freshness(self, name) -> str:
        snapshot = self.snapshot(name)
        if snapshot is None:
            return "NO_DATA"
        value = getattr(snapshot.freshness, "value", snapshot.freshness)
        return str(value)

    def last_updated(self, name):
        measurement = self.measurement(name)
        return getattr(measurement, "completed_at", None) if measurement else None

    def error(self, name):
        snapshot = self.snapshot(name)
        if snapshot is None:
            return None
        return (
            getattr(snapshot, "measurement_error", None)
            or getattr(snapshot, "worker_error", None)
        )

    def history(self, name):
        return self._histories[name].samples()

    def service_names(self) -> tuple[str, ...]:
        return tuple(self._services)
