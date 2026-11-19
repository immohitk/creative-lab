"""Tests for reusable presentation state widgets."""

import pytest

from system_monitor.presentation.widgets.state_widgets import (
    EmptyState,
    ErrorState,
    LoadingState,
)


@pytest.mark.parametrize(
    "widget_class, expected_name",
    [
        (LoadingState, "loading_state"),
        (EmptyState, "empty_state"),
        (ErrorState, "error_state"),
    ],
)
def test_state_widget_initializes(widget_class, expected_name):
    widget = widget_class(
        title="State title",
        description="State description",
    )

    assert widget.objectName() == expected_name
    assert widget.title_label.text() == "State title"
    assert widget.description_label.text() == "State description"
    assert widget.accessibleName() == "State title"
    assert widget.accessibleDescription() == "State description"

    widget.deleteLater()


@pytest.mark.parametrize(
    "widget_class",
    [LoadingState, EmptyState, ErrorState],
)
def test_state_widget_supports_missing_description(widget_class):
    widget = widget_class(title="State title")

    assert widget.description_label.text() == ""
    assert widget.description_label.isHidden()

    widget.deleteLater()


@pytest.mark.parametrize(
    "widget_class",
    [LoadingState, EmptyState, ErrorState],
)
def test_state_widget_updates_description(widget_class):
    widget = widget_class(title="State title")

    widget.set_description("Updated description")

    assert widget.description_label.text() == "Updated description"
    assert widget.accessibleDescription() == "Updated description"

    widget.deleteLater()


@pytest.mark.parametrize(
    "widget_class",
    [LoadingState, EmptyState, ErrorState],
)
def test_state_widget_rejects_empty_title(widget_class):
    with pytest.raises(ValueError):
        widget_class(title=" ")


@pytest.mark.parametrize(
    "widget_class",
    [LoadingState, EmptyState, ErrorState],
)
def test_state_widget_rejects_non_string_title(widget_class):
    with pytest.raises(TypeError):
        widget_class(title=123)


@pytest.mark.parametrize(
    "widget_class",
    [LoadingState, EmptyState, ErrorState],
)
def test_state_widget_rejects_invalid_description(widget_class):
    with pytest.raises(TypeError):
        widget_class(
            title="State title",
            description=123,
        )


@pytest.mark.parametrize(
    "widget_class",
    [LoadingState, EmptyState, ErrorState],
)
def test_state_widget_rejects_invalid_description_update(widget_class):
    widget = widget_class(title="State title")

    with pytest.raises(TypeError):
        widget.set_description(123)

    assert widget.description_label.text() == ""

    widget.deleteLater()
