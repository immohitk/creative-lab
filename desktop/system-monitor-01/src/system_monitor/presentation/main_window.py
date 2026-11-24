
"""Main application window for the system monitor presentation layer."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from system_monitor.presentation.theme import build_stylesheet


PRIMARY_NAVIGATION = (
    "Overview",
    "CPU",
    "Memory",
    "Disk",
    "Network",
    "Processes",
)

SECONDARY_NAVIGATION = ("Diagnostics",)
ALL_PAGES = PRIMARY_NAVIGATION + SECONDARY_NAVIGATION


class MainWindow(QMainWindow):
    """Provide the primary application window and navigation shell."""

    close_requested = Signal()

    def __init__(
        self,
        parent=None,
        controller=None,
        diagnostic_aggregator=None,
        coordinator=None,
    ):
        super().__init__(parent)

        self._controller = controller
        self._diagnostic_aggregator = diagnostic_aggregator
        self._coordinator = coordinator
        self.page_widgets = {}
        self._allow_close = False
        self._navigation_buttons = {}
        self._page_indices = {}

        self.setWindowTitle("CL System Monitor")
        self.setWindowIcon(QApplication.windowIcon())

        self.setMinimumSize(1000, 650)
        self._configure_initial_geometry()
        self._build_ui()
        self._apply_styles()
        self._navigate_to("Overview")

    def _configure_initial_geometry(self):
        """Set a screen-aware initial window size and position."""
        screen = QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None

        if available is None:
            self.resize(1160, 720)
            return

        initial_width = min(1160, available.width() - 40)
        initial_height = min(720, available.height() - 40)

        initial_width = max(self.minimumWidth(), initial_width)
        initial_height = max(self.minimumHeight(), initial_height)

        self.resize(initial_width, initial_height)

        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

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

        for page_name in PRIMARY_NAVIGATION:
            self._add_navigation_button(layout, page_name)

        layout.addStretch()

        separator = QFrame()
        separator.setObjectName("navigation_separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        layout.addWidget(separator)

        for page_name in SECONDARY_NAVIGATION:
            self._add_navigation_button(layout, page_name)

        version_label = QLabel("VERSION 0.1.0")
        version_label.setObjectName("version_label")
        layout.addWidget(version_label)

        return sidebar

    def _add_navigation_button(self, layout, page_name):
        """Create and register an accessible navigation button."""
        button = QPushButton(page_name)
        button.setObjectName("navigation_button")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setCheckable(True)
        button.setAccessibleName(page_name)
        button.setAccessibleDescription(
            f"Navigate to the {page_name} page"
        )

        button.clicked.connect(
            lambda checked=False, page=page_name: self._navigate_to(page)
        )

        self._navigation_buttons[page_name] = button
        layout.addWidget(button)

    def _build_content_area(self):
        """Create the header and page content container."""
        container = QWidget()
        container.setObjectName("content_area")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(18)

        header = QHBoxLayout()

        self.page_title = QLabel("Overview")
        self.page_title.setObjectName("page_title")
        self.page_title.setAccessibleName("Current page")

        header.addWidget(self.page_title)
        header.addStretch()

        self.application_status = QLabel("INITIALIZING")
        self.application_status.setObjectName("application_status")
        self.application_status.setAccessibleName(
            "Application status: initializing"
        )

        header.addWidget(self.application_status)
        layout.addLayout(header)

        self.pages = QStackedWidget()
        self.pages.setObjectName("page_stack")

        monitoring_pages = {}

        if self._controller is not None:
            from system_monitor.presentation.pages import (
                build_monitoring_pages,
            )

            monitoring_pages = build_monitoring_pages(
                self._controller,
                self._diagnostic_aggregator,
                self._coordinator,
            )

        for page_name in ALL_PAGES:
            page = monitoring_pages.get(page_name)

            if page is None:
                page = self._build_placeholder_page(page_name)

            self.page_widgets[page_name] = page
            self._page_indices[page_name] = self.pages.addWidget(page)

        layout.addWidget(self.pages, 1)

        return container

    def _build_placeholder_page(self, page_name):
        """Create a temporary page for the navigation shell."""
        page = QWidget()
        page.setObjectName(f"{page_name.lower()}_page")

        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel(page_name)
        heading.setObjectName("section_heading")
        page_layout.addWidget(heading)

        description = QLabel(
            f"The {page_name.lower()} workspace is being prepared."
        )
        description.setObjectName("placeholder_description")
        description.setWordWrap(True)

        page_layout.addWidget(description)
        page_layout.addStretch()

        return page

    def _navigate_to(self, page_name):
        """Switch the visible page and update navigation selection."""
        if page_name not in self._page_indices:
            return

        self.pages.setCurrentIndex(self._page_indices[page_name])
        self.page_title.setText(page_name)

        active_page = self.page_widgets[page_name]
        refresh = getattr(active_page, "refresh", None)

        if callable(refresh):
            refresh()

        for name, button in self._navigation_buttons.items():
            button.setChecked(name == page_name)

    def _apply_styles(self):
        """Apply the centralized application theme."""
        self.setStyleSheet(build_stylesheet())

    def allow_close(self):
        """Allow the application window to close during shutdown."""
        self._allow_close = True

    def closeEvent(self, event):
        """Protect the application from closing before shutdown approval."""
        if self._allow_close:
            event.accept()
            return

        event.ignore()
        self.close_requested.emit()
