
"""Lightweight Qt-painted history chart without an external chart dependency."""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
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

        width = self.width()
        height = self.height()

        title_pen = QPen(QColor(colors.TEXT_PRIMARY))
        painter.setPen(title_pen)
        painter.drawText(18, 25, self._title)

        non_empty = [
            (label, samples, color)
            for label, samples, color in self._series
            if samples
        ]

        # Lay out the legend using actual font measurements.
        # Additional rows are created when the available width is insufficient.
        legend_rows = []
        if non_empty:
            metrics = QFontMetrics(painter.font())
            available_width = max(1, width - 36)
            current_row = []
            current_x = 18
            row_y = 47

            for label, samples, color in non_empty:
                text_width = metrics.horizontalAdvance(label)
                item_width = 18 + 8 + text_width + 18

                if current_row and current_x + item_width > width - 18:
                    legend_rows.append(current_row)
                    current_row = []
                    current_x = 18
                    row_y += 20

                max_text_width = max(20, available_width - 26)
                display_label = metrics.elidedText(
                    label,
                    Qt.TextElideMode.ElideRight,
                    max_text_width,
                )
                display_width = metrics.horizontalAdvance(display_label)
                item_width = 18 + 8 + display_width + 18

                current_row.append(
                    (current_x, row_y, display_label, color)
                )
                current_x += item_width

            if current_row:
                legend_rows.append(current_row)

            for row in legend_rows:
                for x, y, label, color in row:
                    painter.setPen(QPen(color, 2))
                    painter.drawLine(
                        QPointF(x, y - 4),
                        QPointF(x + 14, y - 4),
                    )
                    painter.setPen(QColor(colors.TEXT_MUTED))
                    painter.drawText(x + 21, y, label)

        legend_height = len(legend_rows) * 20
        plot_top = 54 + legend_height
        plot_bottom = height - 28

        plot = QRectF(
            58,
            plot_top,
            max(1, width - 74),
            max(1, plot_bottom - plot_top),
        )

        grid_pen = QPen(
            QColor(colors.BORDER),
            1,
            Qt.PenStyle.DotLine,
        )
        painter.setPen(grid_pen)

        for index in range(5):
            y = plot.top() + plot.height() * index / 4
            painter.drawLine(
                QPointF(plot.left(), y),
                QPointF(plot.right(), y),
            )

        if not non_empty:
            painter.setPen(QColor(colors.TEXT_MUTED))
            painter.drawText(
                plot,
                Qt.AlignmentFlag.AlignCenter,
                "Waiting for measurements",
            )
            painter.end()
            return

        all_values = [
            sample.value
            for _, samples, _ in non_empty
            for sample in samples
        ]

        maximum_value = max(all_values)
        minimum_value = min(all_values)

        if maximum_value == minimum_value:
            padding = max(abs(maximum_value) * 0.1, 1.0)
        else:
            padding = (maximum_value - minimum_value) * 0.08

        minimum = max(0.0, minimum_value - padding)

        # Network traffic can contain occasional extreme spikes.
        # Cap only unusually large B/s outliers so ordinary variations
        # remain readable. The actual peak is reported in the chart header.
        scale_capped = False
        actual_peak = maximum_value

        unit = self._unit.strip().lower()

        if unit == "%":
            minimum = 0.0
            maximum = 100.0

        elif unit == "b/s" and len(all_values) >= 10:
            sorted_values = sorted(all_values)
            percentile_index = math.ceil(len(sorted_values) * 0.95) - 1
            percentile_95 = sorted_values[percentile_index]

            if percentile_95 > 0 and actual_peak > percentile_95 * 2:
                maximum = percentile_95 * 1.08
                scale_capped = True
            else:
                maximum = maximum_value + padding

        else:
            maximum = maximum_value + padding

        maximum = max(maximum, minimum + 1.0)

        if scale_capped:
            painter.setPen(QColor(colors.TEXT_MUTED))
            painter.drawText(
                QRectF(0, 7, width - 18, 20),
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter,
                f"Scale capped · peak {actual_peak:.0f}{self._unit}",
            )

        # Draw each history series.
        for label, samples, color in non_empty:
            if len(samples) < 2:
                continue

            count = len(samples)
            points = []

            for index, sample in enumerate(samples):
                x = plot.left() + (
                    plot.width() * index / max(1, count - 1)
                )

                # Clamp plotted values to the visible range.
                # Outlier clipping is disclosed in the chart header.
                visible_value = min(max(sample.value, minimum), maximum)

                y = plot.bottom() - (
                    (visible_value - minimum) / (maximum - minimum)
                ) * plot.height()

                points.append(QPointF(x, y))

            painter.setPen(QPen(color, 2))

            for first, second in zip(points, points[1:]):
                painter.drawLine(first, second)

            # Mark values clipped by the network scale cap.
            if scale_capped:
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)

                for point, sample in zip(points, samples):
                    if sample.value > maximum:
                        painter.drawEllipse(point, 3, 3)

                painter.setBrush(Qt.BrushStyle.NoBrush)

        # Axis labels.
        painter.setPen(QColor(colors.TEXT_MUTED))

        painter.drawText(
            QRectF(4, plot.top() - 8, 48, 18),
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter,
            f"{maximum:.0f}{self._unit}",
        )

        painter.drawText(
            QRectF(4, plot.bottom() - 9, 48, 18),
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter,
            f"{minimum:.0f}{self._unit}",
        )

        painter.end()
