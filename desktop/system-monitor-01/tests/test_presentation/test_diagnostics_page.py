
from datetime import datetime

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from system_monitor.models import (
    DiagnosticSeverity,
    DiagnosticSnapshot,
    ServiceDiagnostic,
)
from system_monitor.presentation.pages import DiagnosticsPage



SERVICE_NAMES = ("cpu", "memory", "disk", "network", "process")


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


def make_diagnostic(name, severity=DiagnosticSeverity.HEALTHY):
    return ServiceDiagnostic(
        service_name=name,
        worker_state="RUNNING",
        measurement_status="AVAILABLE",
        freshness="FRESH",
        severity=severity,
        last_updated=datetime(2026, 11, 22, 10, 0, 0),
        error=None,
        consecutive_failures=0,
        sampling_interval=1.0,
        revision=1,
    )


def make_snapshot(
    severities=None,
    coordinator_error=None,
):
    severities = severities or {}
    services = {
        name: make_diagnostic(
            name,
            severities.get(name, DiagnosticSeverity.HEALTHY),
        )
        for name in SERVICE_NAMES
    }

    return DiagnosticSnapshot(
        coordinator_status="RUNNING",
        services=services,
        coordinator_error=coordinator_error,
        coordinator_revision=5,
    )


class FakeDiagnosticAggregator:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot or make_snapshot()
        self.calls = 0

    def aggregate(self):
        self.calls += 1
        return self.snapshot


class FakeDataController(QObject):
    data_changed = Signal(str)


class FakeCoordinator(QObject):
    snapshot_changed = Signal(object)


@pytest.fixture
def page(qapp):
    aggregator = FakeDiagnosticAggregator()
    widget = DiagnosticsPage(aggregator)
    yield widget
    widget.deleteLater()
    qapp.processEvents()


def test_diagnostics_page_displays_initial_overall_health(page):
    assert page.overall_label.text() == "Overall health: Healthy"
    assert page.coordinator_label.text() == "Coordinator: RUNNING"


def test_diagnostics_page_creates_all_five_service_cards(page):
    assert tuple(page.service_cards) == SERVICE_NAMES

    for name in SERVICE_NAMES:
        from system_monitor.presentation.widgets.service_health_card import (
            ServiceHealthCard,
        )

        assert isinstance(page.service_cards[name], ServiceHealthCard)


def test_diagnostics_page_displays_service_counts(page):
    assert page.counts_label.text() == (
        "Healthy: 5  |  Warning: 0  |  Error: 0  |  Unknown: 0"
    )


def test_diagnostics_page_displays_highest_severity(page):
    page._diagnostic_aggregator.snapshot = make_snapshot(
        {
            "cpu": DiagnosticSeverity.WARNING,
            "disk": DiagnosticSeverity.ERROR,
        }
    )

    page.refresh()

    assert page.overall_label.text() == "Overall health: Error"
    assert page.counts_label.text() == (
        "Healthy: 3  |  Warning: 1  |  Error: 1  |  Unknown: 0"
    )


def test_refresh_updates_existing_cards_without_recreating_them(page):
    original_cards = dict(page.service_cards)

    page._diagnostic_aggregator.snapshot = make_snapshot(
        {"cpu": DiagnosticSeverity.WARNING}
    )
    page.refresh()

    assert page.service_cards["cpu"] is original_cards["cpu"]
    assert page.service_cards["cpu"].diagnostic.severity == (
        DiagnosticSeverity.WARNING
    )


def test_coordinator_error_is_displayed(page):
    page._diagnostic_aggregator.snapshot = make_snapshot(
        coordinator_error="Simulated coordinator failure."
    )

    page.refresh()

    assert not page.coordinator_error_label.isHidden()
    assert page.coordinator_error_label.text() == (
        "Coordinator error: Simulated coordinator failure."
    )


def test_coordinator_error_is_hidden_when_cleared(page):
    page._diagnostic_aggregator.snapshot = make_snapshot(
        coordinator_error="Temporary failure."
    )
    page.refresh()

    page._diagnostic_aggregator.snapshot = make_snapshot()
    page.refresh()

    assert not page.coordinator_error_label.isVisible()
    assert page.coordinator_error_label.text() == ""


def test_missing_aggregator_displays_unavailable_state(qapp):
    widget = DiagnosticsPage()

    try:
        assert widget.overall_label.text() == (
            "Overall health: Diagnostics unavailable"
        )
        assert widget.status_label.text() == (
            "No diagnostic aggregator was provided."
        )
    finally:
        widget.deleteLater()
        qapp.processEvents()


def test_missing_service_diagnostic_does_not_crash(page):
    snapshot = make_snapshot()
    snapshot = DiagnosticSnapshot(
        coordinator_status=snapshot.coordinator_status,
        services={
            name: diagnostic
            for name, diagnostic in snapshot.services.items()
            if name != "network"
        },
        coordinator_error=None,
        coordinator_revision=5,
    )
    page._diagnostic_aggregator.snapshot = snapshot

    page.refresh()

    assert page.service_cards["network"].text() == (
        "Network: Waiting for diagnostics"
    )


def test_refresh_requests_a_new_aggregate(page):
    initial_calls = page._diagnostic_aggregator.calls

    page.refresh()

    assert page._diagnostic_aggregator.calls == initial_calls + 1


def test_visible_page_refreshes_when_monitoring_data_changes(qapp):
    aggregator = FakeDiagnosticAggregator()
    controller = FakeDataController()
    coordinator = FakeCoordinator()

    widget = DiagnosticsPage(
        diagnostic_aggregator=aggregator,
        data_controller=controller,
        coordinator=coordinator,
    )

    try:
        widget.show()
        qapp.processEvents()

        initial_calls = aggregator.calls
        aggregator.snapshot = make_snapshot(
            {"cpu": DiagnosticSeverity.WARNING}
        )

        controller.data_changed.emit("cpu")

        assert aggregator.calls == initial_calls + 1
        assert widget.service_cards["cpu"].diagnostic.severity == (
            DiagnosticSeverity.WARNING
        )
    finally:
        widget.close()
        widget.deleteLater()
        qapp.processEvents()


def test_visible_page_refreshes_when_coordinator_snapshot_changes(qapp):
    aggregator = FakeDiagnosticAggregator()
    controller = FakeDataController()
    coordinator = FakeCoordinator()

    widget = DiagnosticsPage(
        diagnostic_aggregator=aggregator,
        data_controller=controller,
        coordinator=coordinator,
    )

    try:
        widget.show()
        qapp.processEvents()

        initial_calls = aggregator.calls
        aggregator.snapshot = make_snapshot(
            {"disk": DiagnosticSeverity.ERROR}
        )

        coordinator.snapshot_changed.emit(object())

        assert aggregator.calls == initial_calls + 1
        assert widget.service_cards["disk"].diagnostic.severity == (
            DiagnosticSeverity.ERROR
        )
    finally:
        widget.close()
        widget.deleteLater()
        qapp.processEvents()


def test_hidden_page_does_not_refresh_on_source_changes(qapp):
    aggregator = FakeDiagnosticAggregator()
    controller = FakeDataController()
    coordinator = FakeCoordinator()

    widget = DiagnosticsPage(
        diagnostic_aggregator=aggregator,
        data_controller=controller,
        coordinator=coordinator,
    )

    try:
        initial_calls = aggregator.calls

        controller.data_changed.emit("cpu")
        coordinator.snapshot_changed.emit(object())

        assert aggregator.calls == initial_calls
    finally:
        widget.deleteLater()
        qapp.processEvents()
