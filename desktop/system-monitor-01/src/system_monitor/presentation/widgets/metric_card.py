
"""Reusable metric card widget for the presentation layer."""

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from system_monitor.presentation.theme import spacing


class MetricCard(QFrame):
    """Display a metric title, value, unit and optional description."""

    def __init__(
        self,
        title: str,
        value: str | int | float,
        unit: str = "",
        description: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")

        if not isinstance(unit, str):
            raise TypeError("unit must be a string")

        self._title = title
        self._unit = unit

        self.setObjectName("metric_card")
        self.setAccessibleName(title)

        self._build_ui(value, description)

    def _build_ui(
        self,
        value: str | int | float,
        description: str | None,
    ):
        """Construct the metric card layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            spacing.METRIC_CARD_PADDING_HORIZONTAL,
            spacing.METRIC_CARD_PADDING_VERTICAL,
            spacing.METRIC_CARD_PADDING_HORIZONTAL,
            spacing.METRIC_CARD_PADDING_VERTICAL,
        )
        layout.setSpacing(spacing.METRIC_CARD_SPACING)

        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("metric_card_title")
        layout.addWidget(self.title_label)

        value_layout = QHBoxLayout()
        value_layout.setSpacing(spacing.METRIC_CARD_VALUE_SPACING)

        self.value_label = QLabel()
        self.value_label.setObjectName("metric_card_value")
        value_layout.addWidget(self.value_label)

        self.unit_label = QLabel(self._unit)
        self.unit_label.setObjectName("metric_card_unit")
        self.unit_label.setVisible(bool(self._unit))
        value_layout.addWidget(self.unit_label)

        value_layout.addStretch()
        layout.addLayout(value_layout)

        self.description_label = QLabel()
        self.description_label.setObjectName("metric_card_description")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.set_value(value)
        self.set_description(description)

    def set_value(self, value: str | int | float):
        """Update the displayed metric value."""
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise TypeError("value must be a string, integer or float")

        self.value_label.setText(str(value))
        self._update_accessible_description()

    def set_description(self, description: str | None):
        """Update the supporting description or hide it when absent."""
        if description is not None and not isinstance(description, str):
            raise TypeError("description must be a string or None")

        self.description_label.setText(description or "")
        self.description_label.setVisible(bool(description))
        self._update_accessible_description()

    def _update_accessible_description(self):
        """Keep the card's accessible description synchronized."""
        value = self.value_label.text()
        unit = self._unit
        description = self.description_label.text()

        accessible_text = f"{self._title}: {value}"

        if unit:
            accessible_text += f" {unit}"

        if description:
            accessible_text += f". {description}"

        self.setAccessibleDescription(accessible_text)
