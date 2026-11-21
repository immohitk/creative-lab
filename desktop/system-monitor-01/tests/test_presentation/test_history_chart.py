"""Tests for the custom-painted HistoryChart widget."""

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QPainter

import system_monitor.presentation.widgets.history_chart as chart_module
from system_monitor.presentation.widgets.history_chart import HistoryChart


class PainterSpy:
    """Record chart painting operations without rendering to the screen."""

    RenderHint = QPainter.RenderHint

    def __init__(self, widget):
        self.widget = widget
        self.texts = []
        self.lines = []
        self.ellipses = []

    def setRenderHint(self, *args):
        pass

    def fillRect(self, *args):
        pass

    def setPen(self, *args):
        pass

    def setBrush(self, *args):
        pass

    def font(self):
        return self.widget.font()

    def drawText(self, *args):
        self.texts.append(args)

    def drawLine(self, *args):
        self.lines.append(args)

    def drawEllipse(self, *args):
        self.ellipses.append(args)

    def end(self):
        pass

    @property
    def text_values(self):
        return [
            args[-1]
            for args in self.texts
            if args and isinstance(args[-1], str)
        ]


@pytest.fixture
def chart(monkeypatch):
    """Create a chart with a recording painter."""
    widget = HistoryChart("Test History")
    widget.resize(480, 300)

    painter = PainterSpy(widget)

    class PainterFactory:
        RenderHint = QPainter.RenderHint

        def __new__(cls, *_args):
            return painter

    monkeypatch.setattr(
        chart_module,
        "QPainter",
        PainterFactory,
    )

    yield widget, painter

    widget.deleteLater()


def make_samples(values):
    """Create sample objects compatible with HistoryChart."""
    return tuple(
        SimpleNamespace(value=float(value))
        for value in values
    )


def test_empty_history_displays_waiting_message(chart):
    widget, painter = chart

    widget.set_series([
        ("CPU", (), "#60A5FA"),
    ])

    widget.paintEvent(None)

    assert "Test History" in painter.text_values
    assert "Waiting for measurements" in painter.text_values
    assert not painter.ellipses


def test_single_sample_renders_without_error(chart):
    widget, painter = chart

    widget.set_series([
        ("CPU", make_samples([45]), "#60A5FA"),
    ])

    widget.paintEvent(None)

    assert "Test History" in painter.text_values
    assert "Waiting for measurements" not in painter.text_values


def test_multiple_series_render_their_data_lines(chart):
    widget, painter = chart

    widget.set_series([
        ("CPU", make_samples([20, 40]), "#60A5FA"),
        ("Memory", make_samples([30, 50]), "#22C55E"),
    ])

    widget.paintEvent(None)

    # Five grid lines, two legend markers and two data lines.
    assert len(painter.lines) == 9


def test_percentage_chart_uses_fixed_zero_to_one_hundred_scale(chart):
    widget, painter = chart

    widget.set_series([
        ("CPU", make_samples([15, 45, 80]), "#60A5FA"),
    ])

    widget.paintEvent(None)

    assert "100%" in painter.text_values
    assert "0%" in painter.text_values


def test_network_outlier_caps_scale_and_marks_spike(chart):
    widget, painter = chart

    values = [100] * 19 + [1000]

    widget._unit = "B/s"
    widget.set_series([
        ("Download", make_samples(values), "#60A5FA"),
    ])

    widget.paintEvent(None)

    assert any(
        isinstance(text, str)
        and "Scale capped" in text
        and "1000" in text
        for text in painter.text_values
    )

    # The extreme sample should be marked as clipped.
    assert len(painter.ellipses) == 1


def test_normal_network_data_does_not_trigger_scale_cap(chart):
    widget, painter = chart

    values = list(range(100, 120))

    widget._unit = "B/s"
    widget.set_series([
        ("Upload", make_samples(values), "#22C55E"),
    ])

    widget.paintEvent(None)

    assert not any(
        isinstance(text, str) and "Scale capped" in text
        for text in painter.text_values
    )

    assert not painter.ellipses


def test_narrow_chart_wraps_legend_into_multiple_rows(chart):
    widget, painter = chart
    widget.resize(240, 300)

    widget.set_series([
        ("CPU utilization history", make_samples([10, 20]), "#60A5FA"),
        ("Memory utilization history", make_samples([30, 40]), "#22C55E"),
        ("Network utilization history", make_samples([50, 60]), "#A78BFA"),
    ])

    widget.paintEvent(None)

    legend_positions = [
        args[1]
        for args in painter.texts
        if len(args) == 3
        and isinstance(args[2], str)
        and "utilization history" in args[2]
    ]

    assert len(legend_positions) == 3
    assert len(set(legend_positions)) > 1
