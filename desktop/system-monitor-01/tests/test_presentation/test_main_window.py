
"""Tests for the main system monitor window."""

import pytest

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QFrame

from system_monitor.presentation.main_window import (
    ALL_PAGES,
    PRIMARY_NAVIGATION,
    SECONDARY_NAVIGATION,
    MainWindow,
)
from system_monitor.presentation.theme import build_stylesheet


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
    assert main_window.windowTitle() == "CL System Monitor"


def test_main_window_applies_centralized_theme(main_window):
    assert main_window.styleSheet() == build_stylesheet()


def test_main_window_creates_all_navigation_items(main_window):
    assert set(main_window._navigation_buttons) == set(ALL_PAGES)
    assert len(main_window._navigation_buttons) == 7


def test_main_window_defines_six_primary_destinations():
    assert PRIMARY_NAVIGATION == (
        "Overview",
        "CPU",
        "Memory",
        "Disk",
        "Network",
        "Processes",
    )


def test_main_window_defines_diagnostics_as_secondary_navigation():
    assert SECONDARY_NAVIGATION == ("Diagnostics",)


def test_main_window_creates_seven_page_containers(main_window):
    assert main_window.pages.count() == 7
    assert set(main_window._page_indices) == set(ALL_PAGES)


def test_main_window_uses_explicit_page_index_mapping(main_window):
    expected_mapping = {
        "Overview": 0,
        "CPU": 1,
        "Memory": 2,
        "Disk": 3,
        "Network": 4,
        "Processes": 5,
        "Diagnostics": 6,
    }

    assert main_window._page_indices == expected_mapping


def test_overview_is_selected_by_default(main_window):
    assert main_window.page_title.text() == "Overview"
    assert main_window.pages.currentIndex() == 0
    assert main_window._navigation_buttons["Overview"].isChecked()


@pytest.mark.parametrize(
    ("page_name", "expected_index"),
    [
        ("Overview", 0),
        ("CPU", 1),
        ("Memory", 2),
        ("Disk", 3),
        ("Network", 4),
        ("Processes", 5),
        ("Diagnostics", 6),
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


def test_diagnostics_has_separate_navigation_container(main_window):
    separator = main_window.sidebar.findChild(
        QFrame,
        "navigation_separator",
    )

    assert separator is not None
    assert main_window._navigation_buttons["Diagnostics"] is not None


def test_navigation_buttons_have_accessible_names(main_window):
    for page_name, button in main_window._navigation_buttons.items():
        assert button.accessibleName() == page_name
        assert button.accessibleDescription() == (
            f"Navigate to the {page_name} page"
        )


def test_navigation_buttons_support_keyboard_focus(main_window, qapp):
    main_window.show()
    qapp.processEvents()

    button = main_window._navigation_buttons["CPU"]
    button.setFocus()
    qapp.processEvents()

    assert button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert button.hasFocus()


def test_navigation_buttons_support_keyboard_activation(main_window, qapp):
    main_window.show()
    qapp.processEvents()

    button = main_window._navigation_buttons["Memory"]
    button.setFocus()
    qapp.processEvents()

    QTest.keyClick(button, Qt.Key.Key_Space)

    assert main_window.page_title.text() == "Memory"
    assert main_window.pages.currentIndex() == 2
    assert button.isChecked()


def test_main_window_has_expected_minimum_size(main_window):
    assert main_window.minimumWidth() == 1000
    assert main_window.minimumHeight() == 650


def test_main_window_resizes_without_losing_content(main_window, qapp):
    main_window.show()
    main_window.resize(1100, 700)
    qapp.processEvents()

    assert main_window.width() == 1100
    assert main_window.height() == 700
    assert main_window.sidebar.width() == 220
    assert main_window.content_area.width() > 0
    assert main_window.pages.isVisible()


def test_main_window_rejects_close_until_shutdown_is_allowed(
    main_window,
    qapp,
):
    main_window.show()
    qapp.processEvents()

    close_spy = QSignalSpy(main_window.close_requested)

    assert main_window.close() is False
    assert close_spy.count() == 1

    main_window.allow_close()

    assert main_window.close() is True


def test_main_window_accepts_optional_diagnostic_aggregator(qapp):
    aggregator = object()

    window = MainWindow(
        diagnostic_aggregator=aggregator,
    )

    try:
        assert window._diagnostic_aggregator is aggregator
        assert window._controller is None
        assert window.pages.count() == 7
    finally:
        window.allow_close()
        window.close()
        window.deleteLater()

def test_main_window_forwards_coordinator_to_monitoring_pages(
    qapp,
    monkeypatch,
):
    from system_monitor.presentation import pages

    controller = object()
    aggregator = object()
    coordinator = object()
    captured = {}

    def fake_build_monitoring_pages(
        received_controller,
        received_aggregator,
        received_coordinator,
    ):
        captured["controller"] = received_controller
        captured["aggregator"] = received_aggregator
        captured["coordinator"] = received_coordinator
        return {}

    monkeypatch.setattr(
        pages,
        "build_monitoring_pages",
        fake_build_monitoring_pages,
    )

    window = MainWindow(
        controller=controller,
        diagnostic_aggregator=aggregator,
        coordinator=coordinator,
    )

    try:
        assert window._coordinator is coordinator
        assert captured["controller"] is controller
        assert captured["aggregator"] is aggregator
        assert captured["coordinator"] is coordinator
    finally:
        window.allow_close()
        window.close()
        window.deleteLater()
        qapp.processEvents()

def test_repeated_rapid_navigation_preserves_page_state(main_window, qapp):
    main_window.show()
    qapp.processEvents()

    for _ in range(50):
        for page_name in ALL_PAGES:
            main_window._navigation_buttons[page_name].click()

    qapp.processEvents()

    final_page = ALL_PAGES[-1]

    assert main_window.pages.count() == len(ALL_PAGES)
    assert main_window.pages.currentIndex() == (
        main_window._page_indices[final_page]
    )
    assert main_window.page_title.text() == final_page

    selected_buttons = [
        name
        for name, button in main_window._navigation_buttons.items()
        if button.isChecked()
    ]
    assert selected_buttons == [final_page]

    for page_name, page in main_window.page_widgets.items():
        assert page.isVisible() == (page_name == final_page)
