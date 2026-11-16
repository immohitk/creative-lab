"""Tests for the main system monitor window."""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QSignalSpy

from system_monitor.presentation.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    """Provide one QApplication instance for the test session."""
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def main_window(qapp):
    """Create and clean up a main window for each test."""
    window = MainWindow()
    yield window
    window.allow_close()
    window.close()
    window.deleteLater()


def test_main_window_initializes_with_expected_title(main_window):
    assert main_window.windowTitle() == "Creative Lab System Monitor"


def test_main_window_creates_all_navigation_items(main_window):
    expected_items = {
        "Dashboard",
        "Processes",
        "Performance",
        "Storage",
        "Network",
        "Diagnostics",
    }

    assert set(main_window._navigation_buttons) == expected_items
    assert len(main_window._navigation_buttons) == 6


def test_dashboard_is_selected_by_default(main_window):
    assert main_window.page_title.text() == "Dashboard"
    assert main_window.pages.currentIndex() == 0
    assert main_window._navigation_buttons["Dashboard"].isChecked()


@pytest.mark.parametrize(
    ("page_name", "expected_index"),
    [
        ("Processes", 1),
        ("Performance", 2),
        ("Storage", 3),
        ("Network", 4),
        ("Diagnostics", 5),
    ],
)
def test_navigation_switches_pages(
    main_window,
    page_name,
    expected_index,
):
    main_window._navigation_buttons[page_name].click()

    assert main_window.pages.currentIndex() == expected_index
    assert main_window.page_title.text() == page_name
    assert main_window._navigation_buttons[page_name].isChecked()


def test_navigation_keeps_only_one_page_selected(main_window):
    main_window._navigation_buttons["Network"].click()

    selected_buttons = [
        name
        for name, button in main_window._navigation_buttons.items()
        if button.isChecked()
    ]

    assert selected_buttons == ["Network"]


def test_main_window_has_expected_minimum_size(main_window):
    assert main_window.minimumWidth() == 1000
    assert main_window.minimumHeight() == 650


def test_main_window_rejects_close_until_shutdown_is_allowed(main_window):
    close_spy = QSignalSpy(main_window.close_requested)
    main_window.show()

    assert main_window.close() is False
    assert close_spy.count() == 1

    main_window.allow_close()

    assert main_window.close() is True
