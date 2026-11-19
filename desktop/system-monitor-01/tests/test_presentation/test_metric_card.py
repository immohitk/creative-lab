
"""Tests for the reusable metric card widget."""

import pytest

from system_monitor.presentation.widgets.metric_card import MetricCard


def test_metric_card_initializes_with_expected_content():
    card = MetricCard(
        title="CPU Usage",
        value=68.4,
        unit="%",
        description="Overall processor utilization",
    )

    assert card.title_label.text() == "CPU Usage"
    assert card.value_label.text() == "68.4"
    assert card.unit_label.text() == "%"
    assert card.description_label.text() == "Overall processor utilization"
    assert card.accessibleName() == "CPU Usage"

    card.deleteLater()


def test_metric_card_supports_optional_unit():
    card = MetricCard(title="Processes", value=125)

    assert card.value_label.text() == "125"
    assert card.unit_label.text() == ""
    assert card.unit_label.isHidden()

    card.deleteLater()


def test_metric_card_hides_missing_description():
    card = MetricCard(title="Memory", value="8 GB")

    assert card.description_label.text() == ""
    assert card.description_label.isHidden()

    card.deleteLater()


def test_metric_card_updates_value():
    card = MetricCard(title="CPU Usage", value=20)

    card.set_value(75.5)

    assert card.value_label.text() == "75.5"
    assert card.accessibleDescription() == "CPU Usage: 75.5"

    card.deleteLater()


def test_metric_card_updates_description():
    card = MetricCard(title="Memory", value="8 GB")

    card.set_description("Physical memory in use")

    assert card.description_label.text() == "Physical memory in use"
    assert not card.description_label.isHidden()
    assert card.accessibleDescription() == (
        "Memory: 8 GB. Physical memory in use"
    )

    card.set_description(None)

    assert card.description_label.isHidden()

    card.deleteLater()


@pytest.mark.parametrize("invalid_value", [True, None, [], {}])
def test_metric_card_rejects_invalid_values(invalid_value):
    with pytest.raises(TypeError):
        MetricCard(title="CPU Usage", value=invalid_value)


def test_metric_card_rejects_empty_title():
    with pytest.raises(ValueError):
        MetricCard(title=" ", value=10)


def test_metric_card_rejects_invalid_description():
    card = MetricCard(title="Memory", value=10)

    with pytest.raises(TypeError):
        card.set_description(123)

    card.deleteLater()
