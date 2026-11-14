import pytest

from PySide6.QtCore import QObject, Signal, QCoreApplication

from system_monitor.coordinator.monitoring_coordinator import (
    MonitoringCoordinator,
)
from system_monitor.models import CoordinatorStatus


@pytest.fixture
def qt_app():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


class FakeService(QObject):
    worker_state_changed = Signal(object)

    def __init__(self):
        super().__init__()
        self.state = "STOPPED"
        self.state_read_error = False
        self.interval = 1.0
        self.start_accepted = True
        self.stop_success = True
        self.configuration_accepted = True

    def get_worker_state(self):
        if self.state_read_error:
            raise RuntimeError("Simulated worker state read failure.")

        return self.state

    def start(self):
        if self.start_accepted:
            self.set_state("STARTING")

        return type(
            "StartResult",
            (),
            {
                "accepted": self.start_accepted,
                "worker_state": self.state,
            },
        )()

    def stop(self):
        if self.stop_success:
            self.set_state("STOPPING")

        return type(
            "StopResult",
            (),
            {
                "success": False,
                "worker_state": self.state,
                "error": None,
            },
        )()

    def get_sampling_interval(self):
        return self.interval

    def set_sampling_interval(self, seconds):
        if self.configuration_accepted:
            self.interval = float(seconds)

        return type(
            "ConfigurationResult",
            (),
            {
                "accepted": self.configuration_accepted,
                "sampling_interval": self.interval,
                "worker_state": self.state,
            },
        )()

    def set_state(self, state):
        self.state = state
        self.worker_state_changed.emit(state)


@pytest.fixture
def services(qt_app):
    return {
        name: FakeService()
        for name in ("cpu", "memory", "disk", "network", "process")
    }


@pytest.fixture
def coordinator(services):
    return MonitoringCoordinator(
        cpu_service=services["cpu"],
        memory_service=services["memory"],
        disk_service=services["disk"],
        network_service=services["network"],
        process_service=services["process"],
    )


def test_initial_state(coordinator):
    snapshot = coordinator.get_snapshot()

    assert snapshot.status == CoordinatorStatus.STOPPED
    assert snapshot.active_service_count == 0
    assert snapshot.failed_service_count == 0
    assert snapshot.revision == 0


def test_start_requests_all_services(coordinator, services):
    result = coordinator.start()

    assert result.accepted is True
    assert result.status == CoordinatorStatus.STARTING

    assert all(
        service.state == "STARTING"
        for service in services.values()
    )


def test_coordinator_becomes_running_when_all_services_run(
    coordinator,
    services,
):
    coordinator.start()

    for service in services.values():
        service.set_state("RUNNING")

    snapshot = coordinator.get_snapshot()

    assert snapshot.status == CoordinatorStatus.RUNNING
    assert snapshot.active_service_count == 5
    assert snapshot.failed_service_count == 0


def test_one_failed_service_degrades_coordinator(
    coordinator,
    services,
):
    coordinator.start()

    for name, service in services.items():
        service.set_state(
            "FAILED" if name == "cpu" else "RUNNING"
        )

    snapshot = coordinator.get_snapshot()

    assert snapshot.status == CoordinatorStatus.DEGRADED
    assert coordinator._lifecycle_intent is None
    assert snapshot.active_service_count == 4
    assert snapshot.failed_service_count == 1
    assert snapshot.service_states["cpu"] == "FAILED"


def test_start_failure_does_not_stop_other_services(
    coordinator,
    services,
):
    services["cpu"].start_accepted = False

    result = coordinator.start()

    assert result.accepted is False
    assert services["cpu"].state == "STOPPED"

    assert all(
        services[name].state == "STARTING"
        for name in ("memory", "disk", "network", "process")
    )


def test_stop_requests_all_services(coordinator, services):
    for service in services.values():
        service.set_state("RUNNING")

    result = coordinator.stop()

    assert result.success is True
    assert result.status == CoordinatorStatus.STOPPING

    assert all(
        service.state == "STOPPING"
        for service in services.values()
    )


def test_coordinator_becomes_stopped_after_all_services_stop(
    coordinator,
    services,
):
    for service in services.values():
        service.set_state("RUNNING")

    coordinator.stop()

    for service in services.values():
        service.set_state("STOPPED")

    assert coordinator.get_status() == CoordinatorStatus.STOPPED


def test_sampling_interval_updates_all_services(
    coordinator,
    services,
):
    result = coordinator.set_sampling_interval(2.0)

    assert result.accepted is True
    assert result.sampling_interval == 2.0

    assert all(
        service.interval == 2.0
        for service in services.values()
    )


def test_sampling_interval_rejects_invalid_values(coordinator):
    with pytest.raises((TypeError, ValueError)):
        coordinator.set_sampling_interval(0.1)

    with pytest.raises((TypeError, ValueError)):
        coordinator.set_sampling_interval(True)


def test_snapshot_revision_increases_after_state_change(
    coordinator,
    services,
):
    initial_revision = coordinator.get_snapshot().revision

    services["cpu"].set_state("RUNNING")

    assert (
        coordinator.get_snapshot().revision
        > initial_revision
    )


def test_snapshot_changed_signal_is_emitted(
    coordinator,
    services,
):
    received = []
    coordinator.snapshot_changed.connect(received.append)

    services["cpu"].set_state("RUNNING")

    assert len(received) == 1
    assert received[0].service_states["cpu"] == "RUNNING"


def test_invalid_service_dependency_is_rejected(qt_app):
    services = [FakeService() for _ in range(4)]

    with pytest.raises(TypeError):
        MonitoringCoordinator(
            cpu_service=services[0],
            memory_service=services[1],
            disk_service=services[2],
            network_service=services[3],
            process_service=object(),
        )

def test_rejected_startup_does_not_leave_start_intent_stuck(
    coordinator,
    services,
):
    services["cpu"].start_accepted = False

    coordinator.start()

    for name, service in services.items():
        if name != "cpu":
            service.set_state("RUNNING")

    snapshot = coordinator.get_snapshot()

    assert snapshot.status == CoordinatorStatus.DEGRADED
    assert coordinator._lifecycle_intent is None


def test_failed_service_recovery_updates_coordinator(
    coordinator,
    services,
):
    coordinator.start()

    for name, service in services.items():
        service.set_state(
            "FAILED" if name == "cpu" else "RUNNING"
        )

    assert coordinator.get_status() == CoordinatorStatus.DEGRADED

    services["cpu"].set_state("RUNNING")

    assert coordinator.get_status() == CoordinatorStatus.RUNNING


def test_partial_configuration_failure_is_reported(
    coordinator,
    services,
):
    services["cpu"].configuration_accepted = False

    result = coordinator.set_sampling_interval(2.0)

    assert result.accepted is False
    assert result.error is not None

    assert services["cpu"].interval == 1.0

    assert all(
        services[name].interval == 2.0
        for name in ("memory", "disk", "network", "process")
    )


def test_repeated_start_does_not_duplicate_start_requests(
    coordinator,
    services,
):
    first = coordinator.start()
    second = coordinator.start()

    assert first.accepted is True
    assert second.accepted is True

    assert all(
        service.state == "STARTING"
        for service in services.values()
    )




def test_partial_shutdown_failure_degrades_coordinator(
    coordinator,
    services,
):
    for service in services.values():
        service.set_state("RUNNING")

    coordinator.stop()

    services["cpu"].set_state("FAILED")

    assert coordinator.get_status() == CoordinatorStatus.DEGRADED

    for name, service in services.items():
        if name != "cpu":
            service.set_state("STOPPED")

    assert coordinator.get_status() == CoordinatorStatus.FAILED


def test_all_shutdown_failures_clear_stop_intent(
    coordinator,
    services,
):
    for service in services.values():
        service.set_state("RUNNING")

    coordinator.stop()

    for service in services.values():
        service.set_state("FAILED")

    assert coordinator.get_status() == CoordinatorStatus.FAILED
    assert coordinator._lifecycle_intent is None


def test_stop_exception_is_reported_without_blocking_other_services(
    coordinator,
    services,
):
    for service in services.values():
        service.set_state("RUNNING")

    def raise_stop_error():
        raise RuntimeError("Simulated shutdown exception")

    services["cpu"].stop = raise_stop_error

    result = coordinator.stop()

    assert result.success is False
    assert "cpu" in result.error
    assert "Simulated shutdown exception" in result.error
    assert result.status == CoordinatorStatus.DEGRADED

    assert all(
        services[name].state == "STOPPING"
        for name in ("memory", "disk", "network", "process")
    )


def test_start_exception_is_reported_without_blocking_other_services(
    coordinator,
    services,
):
    def raise_start_error():
        raise RuntimeError("Simulated startup exception")

    services["cpu"].start = raise_start_error

    result = coordinator.start()

    assert result.accepted is False
    assert "cpu" in result.error
    assert "Simulated startup exception" in result.error
    assert result.status == CoordinatorStatus.STARTING

    assert services["cpu"].state == "STOPPED"

    assert all(
        services[name].state == "STARTING"
        for name in ("memory", "disk", "network", "process")
    )
def test_coordinator_accepts_real_monitoring_services(qt_app):
    from system_monitor.services.cpu_monitoring_service import (
        CpuMonitoringService,
    )
    from system_monitor.services.memory_monitoring_service import (
        MemoryMonitoringService,
    )
    from system_monitor.services.disk_monitoring_service import (
        DiskMonitoringService,
    )
    from system_monitor.services.network_monitoring_service import (
        NetworkMonitoringService,
    )
    from system_monitor.services.process_monitoring_service import (
        ProcessMonitoringService,
    )

    services = {
        "cpu": CpuMonitoringService(),
        "memory": MemoryMonitoringService(),
        "disk": DiskMonitoringService(),
        "network": NetworkMonitoringService(),
        "process": ProcessMonitoringService(),
    }

    coordinator = MonitoringCoordinator(
        cpu_service=services["cpu"],
        memory_service=services["memory"],
        disk_service=services["disk"],
        network_service=services["network"],
        process_service=services["process"],
    )

    snapshot = coordinator.get_snapshot()

    assert snapshot.status == CoordinatorStatus.STOPPED
    assert snapshot.active_service_count == 0
    assert snapshot.failed_service_count == 0

    assert coordinator.get_service_states() == {
        name: "STOPPED" for name in services
    }

    assert {
        name: service.get_sampling_interval()
        for name, service in services.items()
    } == {
        "cpu": 1.0,
        "memory": 1.0,
        "disk": 1.0,
        "network": 1.0,
        "process": 2.0,
    }

def test_start_is_rejected_while_coordinator_is_stopping(
    coordinator,
    services,
):
    for service in services.values():
        service.set_state("RUNNING")

    stop_result = coordinator.stop()

    assert stop_result.status == CoordinatorStatus.STOPPING

    start_result = coordinator.start()

    assert start_result.accepted is False
    assert start_result.status == CoordinatorStatus.STOPPING

    assert all(
        service.state == "STOPPING"
        for service in services.values()
    )

def test_start_handles_worker_state_read_failure(
    coordinator,
    services,
):
    services["cpu"].state_read_error = True

    result = coordinator.start()

    assert result.accepted is True
    assert result.status == CoordinatorStatus.DEGRADED

    assert all(
        services[name].state == "STARTING"
        for name in ("memory", "disk", "network", "process")
    )

def test_start_handles_worker_state_read_failure(
    coordinator,
    services,
):
    services["cpu"].state_read_error = True

    result = coordinator.start()

    assert result.accepted is True
    assert result.status == CoordinatorStatus.STARTING
    assert "cpu" in coordinator.get_snapshot().last_error

    assert all(
        services[name].state == "STARTING"
        for name in ("memory", "disk", "network", "process")
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
