
"""Tests for the reusable service health diagnostic card."""

from datetime import datetime

import pytest
from PySide6.QtWidgets import QApplication

from system_monitor.models import (
    DiagnosticSeverity,
    ServiceDiagnostic,
)
from system_monitor.presentation.widgets.service_health_card import (
    ServiceHealthCard,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def make_diagnostic(
    *,
    service_name="cpu",
    severity=DiagnosticSeverity.HEALTHY,
    last_updated=None,
    error=None,
    consecutive_failures=0,
):
    return ServiceDiagnostic(
        service_name=service_name,
        worker_state="RUNNING",
        measurement_status="AVAILABLE",
        freshness="FRESH",
        severity=severity,
        last_updated=last_updated,
        error=error,
        consecutive_failures=consecutive_failures,
        sampling_interval=1.0,
        revision=4,
    )


@pytest.mark.parametrize(
    ("severity", "expected_text", "expected_status"),
    [
        (DiagnosticSeverity.HEALTHY, "Healthy", "success"),
        (DiagnosticSeverity.WARNING, "Warning", "warning"),
        (DiagnosticSeverity.ERROR, "Error", "error"),
        (DiagnosticSeverity.UNKNOWN, "Unknown", "neutral"),
    ],
)
def test_card_maps_diagnostic_severity(
    qapp,
    severity,
    expected_text,
    expected_status,
):
    card = ServiceHealthCard(
        make_diagnostic(severity=severity)
    )

    assert card.status_indicator.text_label.text() == expected_text
    assert card.status_indicator.property("status") == expected_status

    card.deleteLater()


def test_card_displays_service_diagnostic_details(qapp):
    timestamp = datetime(2026, 11, 22, 16, 30, 0)

    card = ServiceHealthCard(
        make_diagnostic(
            service_name="cpu",
            last_updated=timestamp,
            consecutive_failures=2,
        )
    )

    assert card.title_label.text() == "CPU"
    assert card.worker_state_label.text() == "Worker: RUNNING"
    assert (
        card.measurement_status_label.text()
        == "Measurement: AVAILABLE"
    )
    assert card.freshness_label.text() == "Freshness: FRESH"
    assert (
        card.last_updated_label.text()
        == "Last updated: 2026-11-22 16:30:00"
    )
    assert card.failures_label.text() == "Consecutive failures: 2"
    assert (
        card.sampling_interval_label.text()
        == "Sampling interval: 1 seconds"
    )

    card.deleteLater()


def test_card_displays_fallback_for_missing_timestamp(qapp):
    card = ServiceHealthCard(make_diagnostic())

    assert card.last_updated_label.text() == (
        "Last updated: Unavailable"
    )

    card.deleteLater()


def test_card_hides_missing_error(qapp):
    card = ServiceHealthCard(make_diagnostic())

    assert card.error_label.text() == ""
    assert card.error_label.isHidden()

    card.deleteLater()


def test_card_displays_error_details(qapp):
    card = ServiceHealthCard(
        make_diagnostic(
            severity=DiagnosticSeverity.ERROR,
            error="CPU sampling failed.",
        )
    )

    assert card.error_label.text() == "Error: CPU sampling failed."
    assert not card.error_label.isHidden()

    card.deleteLater()


def test_card_updates_from_new_diagnostic(qapp):
    card = ServiceHealthCard(make_diagnostic())

    updated = make_diagnostic(
        severity=DiagnosticSeverity.WARNING,
        error="Temporary sampling delay.",
        consecutive_failures=3,
    )

    card.set_diagnostic(updated)

    assert card.diagnostic is updated
    assert card.status_indicator.text_label.text() == "Warning"
    assert card.status_indicator.property("status") == "warning"
    assert card.failures_label.text() == "Consecutive failures: 3"
    assert (
        card.error_label.text()
        == "Error: Temporary sampling delay."
    )
    assert not card.error_label.isHidden()

    card.deleteLater()


def test_card_updates_service_name(qapp):
    card = ServiceHealthCard(make_diagnostic())

    card.set_diagnostic(
        make_diagnostic(service_name="network")
    )

    assert card.title_label.text() == "Network"

    card.deleteLater()


def test_card_sets_accessibility_information(qapp):
    card = ServiceHealthCard(make_diagnostic())

    assert card.accessibleName() == "CPU service health"
    assert "CPU: Healthy." in card.accessibleDescription()
    assert "Worker RUNNING." in card.accessibleDescription()

    card.deleteLater()


def test_card_rejects_invalid_initial_diagnostic(qapp):
    with pytest.raises(TypeError):
        ServiceHealthCard(object())


def test_card_rejects_invalid_diagnostic_update(qapp):
    card = ServiceHealthCard(make_diagnostic())

    with pytest.raises(TypeError):
        card.set_diagnostic(object())

    assert card.diagnostic.severity == DiagnosticSeverity.HEALTHY

    card.deleteLater()
