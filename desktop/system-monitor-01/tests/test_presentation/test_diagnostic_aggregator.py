from types import SimpleNamespace

import pytest

from system_monitor.models import (
    CoordinatorStatus,
    DiagnosticSeverity,
)
from system_monitor.presentation.diagnostics.diagnostic_aggregator import (
    DiagnosticAggregator,
)


SERVICE_NAMES = ("cpu", "memory", "disk", "network", "process")


class FakeCoordinator:
    def __init__(self, states=None, status=CoordinatorStatus.RUNNING):
        self.snapshot = SimpleNamespace(
            status=status,
            service_states=states or {
                name: "RUNNING" for name in SERVICE_NAMES
            },
            last_error=None,
            revision=5,
        )

    def get_snapshot(self):
        return self.snapshot


class FakeDataController:
    def __init__(self):
        self.snapshots = {
            name: SimpleNamespace(
                consecutive_failures=0,
                sampling_interval=1.0,
                revision=2,
            )
            for name in SERVICE_NAMES
        }

        self.statuses = {
            name: "AVAILABLE" for name in SERVICE_NAMES
        }

        self.freshness_values = {
            name: "FRESH" for name in SERVICE_NAMES
        }

        self.errors = {
            name: None for name in SERVICE_NAMES
        }

        self.updated = {
            name: None for name in SERVICE_NAMES
        }

    def snapshot(self, name):
        return self.snapshots[name]

    def status(self, name):
        return self.statuses[name]

    def freshness(self, name):
        return self.freshness_values[name]

    def last_updated(self, name):
        return self.updated[name]

    def error(self, name):
        return self.errors[name]


@pytest.fixture
def coordinator():
    return FakeCoordinator()


@pytest.fixture
def data_controller():
    return FakeDataController()


@pytest.fixture
def aggregator(coordinator, data_controller):
    return DiagnosticAggregator(coordinator, data_controller)


def test_all_healthy_services_produce_healthy_snapshot(aggregator):
    snapshot = aggregator.aggregate()

    assert snapshot.severity == DiagnosticSeverity.HEALTHY
    assert snapshot.healthy_count == 5
    assert snapshot.warning_count == 0
    assert snapshot.error_count == 0
    assert snapshot.unknown_count == 0


def test_failed_worker_produces_error(
    aggregator,
    coordinator,
):
    coordinator.snapshot.service_states["cpu"] = "FAILED"

    snapshot = aggregator.aggregate()

    assert snapshot.services["cpu"].severity == DiagnosticSeverity.ERROR
    assert snapshot.error_count == 1
    assert snapshot.severity == DiagnosticSeverity.ERROR


def test_unavailable_measurement_produces_error(
    aggregator,
    data_controller,
):
    data_controller.statuses["disk"] = "UNAVAILABLE"

    snapshot = aggregator.aggregate()

    assert snapshot.services["disk"].severity == DiagnosticSeverity.ERROR


def test_partial_measurement_produces_warning(
    aggregator,
    data_controller,
):
    data_controller.statuses["network"] = "PARTIAL"

    snapshot = aggregator.aggregate()

    assert snapshot.services["network"].severity == DiagnosticSeverity.WARNING


def test_stale_measurement_produces_warning(
    aggregator,
    data_controller,
):
    data_controller.freshness_values["process"] = "STALE"

    snapshot = aggregator.aggregate()

    assert snapshot.services["process"].severity == DiagnosticSeverity.WARNING


def test_stopped_worker_is_unknown(
    aggregator,
    coordinator,
):
    coordinator.snapshot.service_states["memory"] = "STOPPED"

    snapshot = aggregator.aggregate()

    assert snapshot.services["memory"].severity == DiagnosticSeverity.UNKNOWN


def test_initializing_measurement_is_unknown(
    aggregator,
    data_controller,
):
    data_controller.statuses["cpu"] = "INITIALIZING"
    data_controller.freshness_values["cpu"] = "NO_DATA"

    snapshot = aggregator.aggregate()

    assert snapshot.services["cpu"].severity == DiagnosticSeverity.UNKNOWN


def test_worker_failure_takes_precedence_over_measurement_status(
    aggregator,
    coordinator,
    data_controller,
):
    coordinator.snapshot.service_states["cpu"] = "FAILED"
    data_controller.statuses["cpu"] = "AVAILABLE"

    snapshot = aggregator.aggregate()

    assert snapshot.services["cpu"].severity == DiagnosticSeverity.ERROR


def test_aggregator_preserves_service_details(
    aggregator,
    data_controller,
):
    data_controller.statuses["cpu"] = "UNAVAILABLE"
    data_controller.errors["cpu"] = "Simulated measurement failure."
    data_controller.snapshots["cpu"].consecutive_failures = 3
    data_controller.snapshots["cpu"].sampling_interval = 2.0
    data_controller.snapshots["cpu"].revision = 9

    snapshot = aggregator.aggregate()
    cpu = snapshot.services["cpu"]

    assert cpu.error == "Simulated measurement failure."
    assert cpu.consecutive_failures == 3
    assert cpu.sampling_interval == 2.0
    assert cpu.revision == 9


def test_aggregator_preserves_coordinator_error(
    aggregator,
    coordinator,
):
    coordinator.snapshot.last_error = "Simulated coordinator failure."

    snapshot = aggregator.aggregate()

    assert snapshot.coordinator_error == "Simulated coordinator failure."


def test_aggregator_does_not_mutate_source_snapshots(
    aggregator,
    coordinator,
    data_controller,
):
    original_coordinator = (
        coordinator.snapshot.status,
        dict(coordinator.snapshot.service_states),
        coordinator.snapshot.last_error,
        coordinator.snapshot.revision,
    )

    original_snapshots = {
        name: (
            snapshot.consecutive_failures,
            snapshot.sampling_interval,
            snapshot.revision,
        )
        for name, snapshot in data_controller.snapshots.items()
    }

    original_controller_data = (
        dict(data_controller.statuses),
        dict(data_controller.freshness_values),
        dict(data_controller.errors),
        dict(data_controller.updated),
    )

    aggregator.aggregate()

    assert (
        coordinator.snapshot.status,
        dict(coordinator.snapshot.service_states),
        coordinator.snapshot.last_error,
        coordinator.snapshot.revision,
    ) == original_coordinator

    assert {
        name: (
            snapshot.consecutive_failures,
            snapshot.sampling_interval,
            snapshot.revision,
        )
        for name, snapshot in data_controller.snapshots.items()
    } == original_snapshots

    assert (
        dict(data_controller.statuses),
        dict(data_controller.freshness_values),
        dict(data_controller.errors),
        dict(data_controller.updated),
    ) == original_controller_data


def test_aggregator_includes_all_five_services(aggregator):
    snapshot = aggregator.aggregate()

    assert tuple(snapshot.services) == SERVICE_NAMES