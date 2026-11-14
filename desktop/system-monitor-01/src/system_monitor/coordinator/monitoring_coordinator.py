from PySide6.QtCore import QObject, QThread, Signal

from system_monitor.models import (
    CoordinatorSnapshot,
    CoordinatorStatus,
    CoordinatorStartResult,
    CoordinatorStopResult,
    CoordinatorConfigurationResult,
)


class MonitoringCoordinator(QObject):
    """Coordinates the lifecycle of the five monitoring services."""

    snapshot_changed = Signal(object)
    status_changed = Signal(object)

    SERVICE_NAMES = ("cpu", "memory", "disk", "network", "process")

    ACTIVE_STATES = {"RUNNING"}
    FAILED_STATES = {"FAILED"}

    def __init__(
        self,
        cpu_service,
        memory_service,
        disk_service,
        network_service,
        process_service,
        parent=None,
    ):
        super().__init__(parent)

        self._owner_thread = QThread.currentThread()

        self._services = {
            "cpu": cpu_service,
            "memory": memory_service,
            "disk": disk_service,
            "network": network_service,
            "process": process_service,
        }

        self._validate_services()

        self._lifecycle_intent = None
        self._last_error = None
        self._revision = 0

        self._service_states = {
            name: self._state_value(service.get_worker_state())
            for name, service in self._services.items()
        }

        for name, service in self._services.items():
            service.worker_state_changed.connect(
                self._handle_service_state_changed
            )

        self._snapshot = self._build_snapshot()

    @staticmethod
    def _state_value(state):
        return state.value if hasattr(state, "value") else str(state)

    def _refresh_service_states(self):
        errors = []

        for name, service in self._services.items():
            try:
                state = service.get_worker_state()
            except Exception as exc:
                errors.append(
                    f"{name}: unable to read worker state: {exc}"
                )
                continue

            self._service_states[name] = self._state_value(state)

        return errors

    def _validate_services(self):
        for name, service in self._services.items():
            if not isinstance(service, QObject):
                raise TypeError(f"{name} service must be a QObject.")

            if service.thread() != self._owner_thread:
                raise ValueError(
                    f"{name} service must share the coordinator's Qt thread."
                )

            for method in (
                "start",
                "stop",
                "get_worker_state",
                "get_sampling_interval",
                "set_sampling_interval",
            ):
                if not callable(getattr(service, method, None)):
                    raise TypeError(
                        f"{name} service must provide {method}()."
                    )

            if not hasattr(service, "worker_state_changed"):
                raise TypeError(
                    f"{name} service must expose worker_state_changed."
                )

    def _derive_status(self):
        states = list(self._service_states.values())

        if self._lifecycle_intent == "stop":
            if all(state == "STOPPED" for state in states):
                return CoordinatorStatus.STOPPED

            if all(state in {"STOPPED", "FAILED"} for state in states):
                return CoordinatorStatus.FAILED

            if any(state == "FAILED" for state in states):
                return CoordinatorStatus.DEGRADED

            if any(state == "RUNNING" for state in states):
                return CoordinatorStatus.DEGRADED

            return CoordinatorStatus.STOPPING

        if self._lifecycle_intent == "start":
            if all(state == "RUNNING" for state in states):
                return CoordinatorStatus.RUNNING

            if any(state == "STARTING" for state in states):
                return CoordinatorStatus.STARTING

            running = sum(state == "RUNNING" for state in states)
            failed = sum(state == "FAILED" for state in states)

            if running:
                return CoordinatorStatus.DEGRADED

            if failed:
                return CoordinatorStatus.FAILED

            return CoordinatorStatus.STOPPED

        if all(state == "STOPPED" for state in states):
            return CoordinatorStatus.STOPPED

        if all(state == "RUNNING" for state in states):
            return CoordinatorStatus.RUNNING

        if any(state == "STOPPING" for state in states):
            return CoordinatorStatus.STOPPING

        if any(state == "STARTING" for state in states):
            return CoordinatorStatus.STARTING

        running = sum(state == "RUNNING" for state in states)
        failed = sum(state == "FAILED" for state in states)

        if running and any(state != "RUNNING" for state in states):
            return CoordinatorStatus.DEGRADED

        if running:
            return CoordinatorStatus.RUNNING

        if failed:
            return CoordinatorStatus.FAILED

        return CoordinatorStatus.STOPPED

    def _build_snapshot(self):
        status = self._derive_status()

        active_count = sum(
            state in self.ACTIVE_STATES
            for state in self._service_states.values()
        )

        failed_count = sum(
            state in self.FAILED_STATES
            for state in self._service_states.values()
        )

        return CoordinatorSnapshot(
            status=status,
            service_states=self._service_states,
            active_service_count=active_count,
            failed_service_count=failed_count,
            last_error=self._last_error,
            revision=self._revision,
        )

    def _refresh_snapshot(self):
        previous_status = self._snapshot.status
        self._revision += 1
        self._snapshot = self._build_snapshot()

        self.snapshot_changed.emit(self._snapshot)

        if self._snapshot.status != previous_status:
            self.status_changed.emit(self._snapshot.status)

        return self._snapshot

    def _handle_service_state_changed(self, _state):
        if QThread.currentThread() != self._owner_thread:
            return

        state_errors = self._refresh_service_states()

        if state_errors:
            self._last_error = "; ".join(state_errors)

        states = list(self._service_states.values())

        if self._lifecycle_intent == "start":
            if all(state in {"RUNNING", "FAILED", "STOPPED"} for state in states):
                self._lifecycle_intent = None

        elif self._lifecycle_intent == "stop":
            if all(state in {"STOPPED", "FAILED"} for state in states):
                self._lifecycle_intent = None

        self._refresh_snapshot()

    def get_snapshot(self):
        return self._snapshot

    def get_status(self):
        return self._snapshot.status

    def get_service_states(self):
        return dict(self._snapshot.service_states)

    def start(self):
        """Request startup of all services without waiting for workers."""
        if QThread.currentThread() != self._owner_thread:
            raise RuntimeError(
                "Coordinator operations must run on its owning Qt thread."
            )

        if self._snapshot.status == CoordinatorStatus.STOPPING:
            return CoordinatorStartResult(
                accepted=False,
                status=self._snapshot.status,
                error="Cannot start monitoring while shutdown is in progress.",
            )

        if self._snapshot.status in {
            CoordinatorStatus.STARTING,
            CoordinatorStatus.RUNNING,
        }:
            return CoordinatorStartResult(
                accepted=True,
                status=self._snapshot.status,
            )

        self._lifecycle_intent = "start"
        self._last_error = None

        operation_errors = []

        for name, service in self._services.items():
            try:
                result = service.start()

                if not result.accepted:
                    operation_errors.append(
                        f"{name}: startup request was rejected."
                    )
            except Exception as exc:
                operation_errors.append(f"{name}: {exc}")

        state_errors = self._refresh_service_states()
        errors = operation_errors + state_errors

        self._last_error = "; ".join(errors) if errors else None

        states = list(self._service_states.values())

        if all(state in {"RUNNING", "FAILED", "STOPPED"} for state in states):
            self._lifecycle_intent = None

        snapshot = self._refresh_snapshot()

        return CoordinatorStartResult(
            accepted=not operation_errors,
            status=snapshot.status,
            error=self._last_error,
        )

    def stop(self):
        """Request shutdown of all services without blocking."""
        if QThread.currentThread() != self._owner_thread:
            raise RuntimeError(
                "Coordinator operations must run on its owning Qt thread."
            )

        self._lifecycle_intent = "stop"
        operation_errors = []

        for name, service in self._services.items():
            try:
                result = service.stop()

                if not result.success:
                    result_state = self._state_value(result.worker_state)

                    if result_state != "STOPPING":
                        operation_errors.append(
                            f"{name}: shutdown request failed "
                            f"with state {result_state}."
                        )
            except Exception as exc:
                operation_errors.append(f"{name}: {exc}")

        state_errors = self._refresh_service_states()
        errors = operation_errors + state_errors

        self._last_error = "; ".join(errors) if errors else None

        if all(
            state == "STOPPED"
            for state in self._service_states.values()
        ):
            self._lifecycle_intent = None

        snapshot = self._refresh_snapshot()

        return CoordinatorStopResult(
            success=not operation_errors,
            status=snapshot.status,
            error=self._last_error,
        )

    def set_sampling_interval(self, seconds):
        """Apply a sampling interval to all monitoring services."""
        if QThread.currentThread() != self._owner_thread:
            raise RuntimeError(
                "Coordinator operations must run on its owning Qt thread."
            )

        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
        ):
            raise TypeError("Sampling interval must be numeric.")

        import math

        if not math.isfinite(seconds) or not 0.5 <= seconds <= 60.0:
            raise ValueError(
                "Sampling interval must be between 0.5 and 60 seconds."
            )

        results = []
        errors = []

        for name, service in self._services.items():
            try:
                result = service.set_sampling_interval(seconds)
                results.append(result)

                if not result.accepted:
                    errors.append(
                        f"{name}: configuration request was rejected."
                    )
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        error = "; ".join(errors) if errors else None
        self._last_error = error

        self._refresh_snapshot()

        return CoordinatorConfigurationResult(
            accepted=not errors,
            sampling_interval=float(seconds),
            status=self._snapshot.status,
            error=error,
        )

def test_stop_handles_worker_state_read_failure(
    coordinator,
    services,
):
    for service in services.values():
        service.set_state("RUNNING")

    services["cpu"].state_read_error = True

    result = coordinator.stop()

    assert result.success is True
    assert result.status == CoordinatorStatus.STOPPING

    assert all(
        services[name].state == "STOPPING"
        for name in ("memory", "disk", "network", "process")
    )

    assert "cpu" in coordinator.get_snapshot().last_error
