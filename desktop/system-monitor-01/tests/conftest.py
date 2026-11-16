import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qt_application():
    """Provide one widget-capable Qt application for the entire test session."""
    application = QApplication.instance() or QApplication([])
    yield application
    application.processEvents()
