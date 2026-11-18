"""Main application window for the system monitor presentation layer."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from system_monitor.presentation.theme import build_stylesheet


class MainWindow(QMainWindow):
    close_requested = Signal()
    """Provide the primary application window and navigation shell."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._allow_close = False

        self.setWindowTitle("Creative Lab System Monitor")
        self.setMinimumSize(1000, 650)
        self.resize(1280, 800)

        self._navigation_buttons = {}
        self._build_ui()
        self._apply_styles()
        self._navigate_to("Dashboard")

    def _build_ui(self):
        """Construct the main window layout."""
        central_widget = QWidget(self)
        central_layout = QHBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        self.content_area = self._build_content_area()

        central_layout.addWidget(self.sidebar)
        central_layout.addWidget(self.content_area, 1)

        self.setCentralWidget(central_widget)

    def _build_sidebar(self):
        """Create the left navigation sidebar."""
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 20)
        layout.setSpacing(10)

        brand = QLabel("SYSTEM MONITOR")
        brand.setObjectName("brand_label")
        layout.addWidget(brand)

        subtitle = QLabel("CREATIVE LAB")
        subtitle.setObjectName("brand_subtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(28)

        navigation_items = [
            "Dashboard",
            "Processes",
            "Performance",
            "Storage",
            "Network",
            "Diagnostics",
        ]

        for item in navigation_items:
            button = QPushButton(item)
            button.setObjectName("navigation_button")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, page=item: self._navigate_to(page)
            )
            self._navigation_buttons[item] = button
            layout.addWidget(button)

        layout.addStretch()

        version_label = QLabel("VERSION 0.1.0")
        version_label.setObjectName("version_label")
        layout.addWidget(version_label)

        return sidebar

    def _build_content_area(self):
        """Create the header and page content container."""
        container = QWidget()
        container.setObjectName("content_area")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(30, 24, 30, 28)
        layout.setSpacing(22)

        header = QHBoxLayout()

        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("page_title")
        header.addWidget(self.page_title)

        header.addStretch()

        self.application_status = QLabel("INITIALIZING")
        self.application_status.setObjectName("application_status")
        header.addWidget(self.application_status)

        layout.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.setObjectName("page_stack")

        for page_name in self._navigation_buttons:
            self.pages.addWidget(self._build_placeholder_page(page_name))

        layout.addWidget(self.pages, 1)

        return container

    def _build_placeholder_page(self, page_name):
        """Create a temporary page for the navigation shell."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel(page_name)
        heading.setObjectName("section_heading")
        page_layout.addWidget(heading)

        description = QLabel(
            "The " + page_name.lower() + " workspace is being prepared."
        )
        description.setObjectName("placeholder_description")
        description.setWordWrap(True)
        page_layout.addWidget(description)

        page_layout.addStretch()

        return page

    def _navigate_to(self, page_name):
        """Switch the visible page and update navigation selection."""
        if page_name not in self._navigation_buttons:
            return

        page_index = list(self._navigation_buttons).index(page_name)
        self.pages.setCurrentIndex(page_index)
        self.page_title.setText(page_name)

        for name, button in self._navigation_buttons.items():
            button.setChecked(name == page_name)

    def _apply_styles(self):
        """Apply the centralized application theme."""
        self.setStyleSheet(build_stylesheet())


    def allow_close(self):
        self._allow_close = True

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return

        event.ignore()
        self.close_requested.emit()
