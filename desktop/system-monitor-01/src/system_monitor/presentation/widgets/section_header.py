
"""Reusable section header widget for the presentation layer."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from system_monitor.presentation.theme import spacing


class SectionHeader(QWidget):
    """Display a section title and optional description."""

    def __init__(
        self,
        title: str,
        description: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")

        self._title = title

        self.setObjectName("section_header")
        self.setAccessibleName(title)

        self._build_ui(description)

    def _build_ui(self, description: str | None):
        """Construct the section header layout."""
        if description is not None and not isinstance(description, str):
            raise TypeError("description must be a string or None")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(spacing.SECTION_HEADER_SPACING)

        self.title_label = QLabel(self._title)
        self.title_label.setObjectName("section_header_title")
        layout.addWidget(self.title_label)

        self.description_label = QLabel()
        self.description_label.setObjectName("section_header_description")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.set_description(description)

    def set_description(self, description: str | None):
        """Update the section description."""
        if description is not None and not isinstance(description, str):
            raise TypeError("description must be a string or None")

        self.description_label.setText(description or "")
        self.description_label.setVisible(bool(description))
        self._update_accessible_description()

    def _update_accessible_description(self):
        """Synchronize the accessible description."""
        self.setAccessibleDescription(
            self.description_label.text()
        )
