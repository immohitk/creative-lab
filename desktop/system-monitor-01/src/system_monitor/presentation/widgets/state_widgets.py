"""Reusable loading, empty and error state widgets."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from system_monitor.presentation.theme import spacing


class _BaseStateWidget(QFrame):
    """Shared layout and accessibility behavior for state widgets."""

    OBJECT_NAME = "base_state_widget"
    TITLE_OBJECT_NAME = "base_state_title"
    DESCRIPTION_OBJECT_NAME = "base_state_description"

    def __init__(
        self,
        title: str,
        description: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._validate_title(title)
        self._validate_description(description)

        self.setObjectName(self.OBJECT_NAME)
        self.setAccessibleName(title)

        self._build_ui(title, description)

    def _build_ui(self, title: str, description: str | None):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(spacing.SECTION_HEADER_SPACING)

        self.title_label = QLabel(title)
        self.title_label.setObjectName(self.TITLE_OBJECT_NAME)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.description_label = QLabel()
        self.description_label.setObjectName(
            self.DESCRIPTION_OBJECT_NAME
        )
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        self.set_description(description)

    def set_description(self, description: str | None):
        """Update the optional supporting description."""
        self._validate_description(description)

        self.description_label.setText(description or "")
        self.description_label.setVisible(bool(description))

        self.setAccessibleDescription(description or "")

    @staticmethod
    def _validate_title(title: str):
        if not isinstance(title, str):
            raise TypeError("title must be a string")

        if not title.strip():
            raise ValueError("title must be a non-empty string")

    @staticmethod
    def _validate_description(description: str | None):
        if description is not None and not isinstance(description, str):
            raise TypeError("description must be a string or None")


class LoadingState(_BaseStateWidget):
    """Display a loading state."""

    OBJECT_NAME = "loading_state"
    TITLE_OBJECT_NAME = "loading_state_title"
    DESCRIPTION_OBJECT_NAME = "loading_state_description"


class EmptyState(_BaseStateWidget):
    """Display an empty state."""

    OBJECT_NAME = "empty_state"
    TITLE_OBJECT_NAME = "empty_state_title"
    DESCRIPTION_OBJECT_NAME = "empty_state_description"


class ErrorState(_BaseStateWidget):
    """Display an error state."""

    OBJECT_NAME = "error_state"
    TITLE_OBJECT_NAME = "error_state_title"
    DESCRIPTION_OBJECT_NAME = "error_state_description"
