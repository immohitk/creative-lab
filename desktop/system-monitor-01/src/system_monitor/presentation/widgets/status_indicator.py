
"""Reusable status indicator widget for the presentation layer."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from system_monitor.presentation.theme import spacing


class StatusIndicator(QFrame):
    """Display a compact status marker and its descriptive text."""

    VALID_STATUSES = frozenset({
        "success",
        "warning",
        "error",
        "info",
        "neutral",
    })

    def __init__(
        self,
        text: str,
        status: str,
        parent=None,
    ):
        super().__init__(parent)

        self._validate_text(text)
        self._validate_status(status)

        self._text = text
        self._status = status

        self.setObjectName("status_indicator")
        self.setAccessibleName(text)

        self._build_ui()
        self._apply_status()

    def _build_ui(self):
        """Construct the status indicator layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(spacing.STATUS_INDICATOR_SPACING)

        self.marker_label = QLabel()
        self.marker_label.setObjectName("status_indicator_marker")
        self.marker_label.setFixedSize(
            spacing.STATUS_INDICATOR_MARKER_SIZE,
            spacing.STATUS_INDICATOR_MARKER_SIZE,
        )
        self.marker_label.setAccessibleName("Status marker")
        layout.addWidget(self.marker_label)

        self.text_label = QLabel(self._text)
        self.text_label.setObjectName("status_indicator_text")
        layout.addWidget(self.text_label)

        self.marker_label.setAccessibleDescription(self._status)
        self._update_accessibility_description()

    def set_status(self, status: str):
        """Change the visual status variant."""
        self._validate_status(status)

        if status == self._status:
            return

        self._status = status
        self._apply_status()

    def set_text(self, text: str):
        """Update the displayed status text."""
        self._validate_text(text)

        self._text = text
        self.text_label.setText(text)
        self.setAccessibleName(text)
        self._update_accessibility_description()

    def _apply_status(self):
        """Apply the status property used by the shared stylesheet."""
        self.setProperty("status", self._status)

        self.marker_label.setAccessibleDescription(self._status)
        self._update_accessibility_description()

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _update_accessibility_description(self):
        """Synchronize the accessible description."""
        self.setAccessibleDescription(
            f"{self._text}: {self._status}"
        )

    @staticmethod
    def _validate_text(text: str):
        """Validate the displayed status text."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        if not text.strip():
            raise ValueError("text must be a non-empty string")

    @classmethod
    def _validate_status(cls, status: str):
        """Validate the supported visual status variant."""
        if not isinstance(status, str):
            raise TypeError("status must be a string")

        if status not in cls.VALID_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(cls.VALID_STATUSES)}"
            )
