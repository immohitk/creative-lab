from system_monitor.models import (
    DiagnosticSeverity,
    DiagnosticSnapshot,
    ServiceDiagnostic,
)


class DiagnosticAggregator:
    """Build immutable diagnostics from existing monitoring state."""

    SERVICE_NAMES = ("cpu", "memory", "disk", "network", "process")

    def __init__(self, coordinator, data_controller):
        self._coordinator = coordinator
        self._data_controller = data_controller

    @staticmethod
    def _value(value):
        return str(getattr(value, "value", value))

    @staticmethod
    def _error_text(error):
        if error is None:
            return None
        return str(error)

    @staticmethod
    def _classify(worker_state, measurement_status, freshness):
        if worker_state == "FAILED":
            return DiagnosticSeverity.ERROR

        if measurement_status == "UNAVAILABLE":
            return DiagnosticSeverity.ERROR

        if measurement_status == "PARTIAL":
            return DiagnosticSeverity.WARNING

        if freshness == "STALE":
            return DiagnosticSeverity.WARNING

        if worker_state == "STOPPED":
            return DiagnosticSeverity.UNKNOWN

        if measurement_status == "INITIALIZING" or freshness == "NO_DATA":
            return DiagnosticSeverity.UNKNOWN

        if (
            worker_state == "RUNNING"
            and measurement_status == "AVAILABLE"
            and freshness == "FRESH"
        ):
            return DiagnosticSeverity.HEALTHY

        return DiagnosticSeverity.UNKNOWN

    def aggregate(self) -> DiagnosticSnapshot:
        coordinator_snapshot = self._coordinator.get_snapshot()

        diagnostics = {}

        for name in self.SERVICE_NAMES:
            worker_state = coordinator_snapshot.service_states.get(
                name, "UNKNOWN"
            )

            service_snapshot = self._data_controller.snapshot(name)

            measurement_status = self._data_controller.status(name)
            freshness = self._data_controller.freshness(name)

            last_updated = self._data_controller.last_updated(name)
            error = self._data_controller.error(name)

            if service_snapshot is None:
                consecutive_failures = 0
                sampling_interval = 1.0
                service_revision = 0
            else:
                consecutive_failures = service_snapshot.consecutive_failures
                sampling_interval = service_snapshot.sampling_interval
                service_revision = service_snapshot.revision

            severity = self._classify(
                worker_state=worker_state,
                measurement_status=measurement_status,
                freshness=freshness,
            )

            diagnostics[name] = ServiceDiagnostic(
                service_name=name,
                worker_state=self._value(worker_state),
                measurement_status=self._value(measurement_status),
                freshness=self._value(freshness),
                severity=severity,
                last_updated=last_updated,
                error=self._error_text(error),
                consecutive_failures=consecutive_failures,
                sampling_interval=sampling_interval,
                revision=service_revision,
            )

        return DiagnosticSnapshot(
            coordinator_status=self._value(coordinator_snapshot.status),
            services=diagnostics,
            coordinator_error=self._error_text(
                coordinator_snapshot.last_error
            ),
            coordinator_revision=coordinator_snapshot.revision,
        )