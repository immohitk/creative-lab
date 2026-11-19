
"""Tests for the reusable status indicator widget."""

import pytest

from system_monitor.presentation.widgets.status_indicator import StatusIndicator


@pytest.mark.parametrize(
    "status",
    ["success", "warning", "error", "info", "neutral"],
)
def test_status_indicator_initializes_with_supported_status(status):
    indicator = StatusIndicator(
        text="Monitoring",
        status=status,
    )

    assert indicator.text_label.text() == "Monitoring"
    assert indicator.property("status") == status
    assert indicator.accessibleName() == "Monitoring"
    assert indicator.accessibleDescription() == f"Monitoring: {status}"
    assert indicator.marker_label.accessibleDescription() == status

    indicator.deleteLater()


def test_status_indicator_updates_status():
    indicator = StatusIndicator(
        text="Initializing",
        status="info",
    )

    indicator.set_status("success")

    assert indicator.property("status") == "success"
    assert indicator.accessibleDescription() == "Initializing: success"
    assert indicator.marker_label.accessibleDescription() == "success"

    indicator.deleteLater()


def test_status_indicator_updates_text():
    indicator = StatusIndicator(
        text="Initializing",
        status="info",
    )

    indicator.set_text("Monitoring")

    assert indicator.text_label.text() == "Monitoring"
    assert indicator.accessibleName() == "Monitoring"
    assert indicator.accessibleDescription() == "Monitoring: info"

    indicator.deleteLater()


def test_status_indicator_rejects_unsupported_status():
    with pytest.raises(ValueError):
        StatusIndicator(text="Monitoring", status="unknown")


def test_status_indicator_rejects_non_string_status():
    with pytest.raises(TypeError):
        StatusIndicator(text="Monitoring", status=123)


def test_status_indicator_rejects_empty_text():
    with pytest.raises(ValueError):
        StatusIndicator(text=" ", status="success")


def test_status_indicator_rejects_non_string_text():
    with pytest.raises(TypeError):
        StatusIndicator(text=123, status="success")


def test_status_indicator_rejects_invalid_status_update():
    indicator = StatusIndicator(
        text="Monitoring",
        status="success",
    )

    with pytest.raises(ValueError):
        indicator.set_status("unknown")

    assert indicator.property("status") == "success"

    indicator.deleteLater()


def test_status_indicator_rejects_invalid_text_update():
    indicator = StatusIndicator(
        text="Monitoring",
        status="success",
    )

    with pytest.raises(TypeError):
        indicator.set_text(123)

    assert indicator.text_label.text() == "Monitoring"

    indicator.deleteLater()
