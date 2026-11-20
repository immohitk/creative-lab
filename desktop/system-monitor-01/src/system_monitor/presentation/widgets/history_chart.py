"""Lightweight Qt-painted history chart without an external chart dependency."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame

from system_monitor.presentation.theme import colors


class HistoryChart(QFrame):
    """Render one or more bounded numeric histories."""

    def __init__(self, title: str, unit: str = "%", parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._series = []
        self.setObjectName("history_chart")
        self.setMinimumHeight(190)
        self.setAccessibleName(title)

    def set_series(self, series):
        """Set series as (label, samples, color) tuples."""
        self._series = [
            (str(label), tuple(samples), QColor(color))
            for label, samples, color in series
        ]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(colors.SURFACE))

        title_pen = QPen(QColor(colors.TEXT_PRIMARY))
        painter.setPen(title_pen)
        painter.drawText(18, 25, self._title)

        plot = QRectF(48, 42, max(1, self.width() - 68), max(1, self.height() - 72))
        grid_pen = QPen(QColor(colors.BORDER), 1, Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for index in range(5):
            y = plot.top() + plot.height() * index / 4
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        non_empty = [(label, samples, color) for label, samples, color in self._series if samples]
        if not non_empty:
            painter.setPen(QColor(colors.TEXT_MUTED))
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "Waiting for measurements")
            painter.end()
            return

        all_values = [sample.value for _, samples, _ in non_empty for sample in samples]
        maximum = max(all_values)
        minimum = min(all_values)
        if maximum == minimum:
            padding = max(abs(maximum) * 0.1, 1.0)
        else:
            padding = (maximum - minimum) * 0.08

        # These charts currently display non-negative utilization and traffic
        # measurements. Keep the lower axis bound meaningful for those metrics.
        minimum = max(0.0, minimum - padding)
        maximum = max(maximum + padding, minimum + 1.0)

        legend_x = int(plot.right()) - 12
        for index, (label, samples, color) in enumerate(reversed(non_empty)):
            painter.setPen(QPen(color, 2))
            painter.drawText(legend_x - 110 - index * 100, 25, label)
            if len(samples) < 2:
                continue
            count = len(samples)
            points = []
            for index, sample in enumerate(samples):
                x = plot.left() + plot.width() * index / max(1, count - 1)
                y = plot.bottom() - (
                    (sample.value - minimum) / (maximum - minimum)
                ) * plot.height()
                points.append(QPointF(x, y))
            painter.setPen(QPen(color, 2))
            for first, second in zip(points, points[1:]):
                painter.drawLine(first, second)

        painter.setPen(QColor(colors.TEXT_MUTED))
        painter.drawText(8, int(plot.top() + 4), f"{maximum:.0f}{self._unit}")
        painter.drawText(8, int(plot.bottom()), f"{minimum:.0f}{self._unit}")
        painter.end()
