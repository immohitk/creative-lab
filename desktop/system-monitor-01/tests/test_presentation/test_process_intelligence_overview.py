
"""Tests for the Process Intelligence overview page."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from system_monitor.models.process_measurement import ProcessMeasurement
from system_monitor.presentation.pages import ProcessesPage
from system_monitor.presentation.process_classifier import ProcessClassifier


@pytest.fixture(scope="session")
def qapp():
    """Provide one QApplication instance for presentation tests."""
    application = QApplication.instance() or QApplication([])
    yield application


class FakeController(QObject):
    """Minimal controller implementation for ProcessesPage tests."""

    data_changed = Signal(str)

    def __init__(self, measurement):
        super().__init__()
        self._measurement = measurement

    def measurement(self, name):
        assert name == "process"
        return self._measurement

    def status(self, name):
        return "RUNNING"

    def freshness(self, name):
        return "FRESH"

    def last_updated(self, name):
        return None

    def error(self, name):
        return None


def make_process(
    pid=100,
    name="test-process",
    cpu_percent=12.5,
    memory_bytes=1024 * 1024,
    executable_path=None,
):
    """Create a valid process measurement."""
    return ProcessMeasurement(
        pid=pid,
        name=name,
        cpu_percent=cpu_percent,
        memory_bytes=memory_bytes,
        status="running",
        sampled_at=datetime.now(timezone.utc),
        executable_path=executable_path,
    )


def make_measurement(processes=()):
    """Create a lightweight process measurement snapshot."""
    return SimpleNamespace(
        processes=tuple(processes),
        process_errors=(),
    )


@pytest.fixture
def category_map(monkeypatch):
    """Control classification results without testing the classifier here."""
    categories = {}

    def fake_classify(self, process):
        category = categories.get(process.pid, "Unclassified")
        return SimpleNamespace(category=category)

    monkeypatch.setattr(
        ProcessClassifier,
        "classify",
        fake_classify,
    )

    return categories


@pytest.fixture
def page_factory(qapp, category_map):
    """Create and clean up a ProcessesPage instance."""

    pages = []

    def create(processes=(), measurement_available=True):
        measurement = (
            make_measurement(processes)
            if measurement_available
            else None
        )

        controller = FakeController(measurement)
        page = ProcessesPage(controller)

        pages.append((page, controller))
        return page

    yield create

    for page, controller in pages:
        page.close()
        page.deleteLater()
        controller.deleteLater()

    qapp.processEvents()


def test_page_creates_all_category_cards(page_factory):
    page = page_factory()

    assert set(page.category_cards) == {
        "System",
        "Service",
        "Application",
        "Unclassified",
    }


def test_empty_measurement_shows_zero_processes(page_factory):
    page = page_factory()

    assert page.overview_cards["total"].value_label.text() == "0"
    assert page.overview_cards["classified"].value_label.text() == "0 / 0"


def test_system_process_contributes_to_system_category(
    page_factory,
    category_map,
):
    process = make_process(pid=101, name="system-process")
    category_map[101] = "System"

    page = page_factory([process])

    assert page.category_cards["System"].count_label.text() == "1"
    assert page.category_cards["Unclassified"].count_label.text() == "0"


def test_unclassified_process_remains_unclassified(
    page_factory,
    category_map,
):
    process = make_process(pid=102, name="unknown-process")
    category_map[102] = "Unclassified"

    page = page_factory([process])

    assert page.category_cards["Unclassified"].count_label.text() == "1"
    assert page.overview_cards["classified"].value_label.text() == "0 / 1"


def test_combined_cpu_excludes_unavailable_values(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=201, cpu_percent=10.0),
        make_process(pid=202, cpu_percent=None),
        make_process(pid=203, cpu_percent=25.5),
    ]

    for process in processes:
        category_map[process.pid] = "Application"

    page = page_factory(processes)

    assert page.overview_cards["cpu"].value_label.text() == "35.5"


def test_combined_memory_sums_process_memory(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=301, memory_bytes=1024),
        make_process(pid=302, memory_bytes=2048),
        make_process(pid=303, memory_bytes=4096),
    ]

    for process in processes:
        category_map[process.pid] = "Application"

    page = page_factory(processes)

    assert page.overview_cards["memory"].value_label.text() == "7.0 KB"


def test_cpu_leaders_exclude_unavailable_cpu_values(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=401, name="known-cpu", cpu_percent=20.0),
        make_process(pid=402, name="unknown-cpu", cpu_percent=None),
        make_process(pid=403, name="highest-cpu", cpu_percent=50.0),
    ]

    for process in processes:
        category_map[process.pid] = "Application"

    page = page_factory(processes)

    rows = page.cpu_leaders["rows"]

    assert "highest-cpu" in rows[0].text()
    assert "known-cpu" in rows[1].text()
    assert "unknown-cpu" not in rows[0].text()
    assert "unknown-cpu" not in rows[1].text()


def test_memory_leaders_are_ordered_by_memory_usage(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=501, name="small", memory_bytes=1024),
        make_process(pid=502, name="large", memory_bytes=8192),
        make_process(pid=503, name="medium", memory_bytes=4096),
    ]

    for process in processes:
        category_map[process.pid] = "Application"

    page = page_factory(processes)

    rows = page.memory_leaders["rows"]

    assert "large" in rows[0].text()
    assert "medium" in rows[1].text()
    assert "small" in rows[2].text()


def test_application_identity_displays_current_pid(page_factory):
    page = page_factory()

    assert str(__import__("os").getpid()) in page.application_label.text()
    assert "THIS APPLICATION" in page.application_label.text()


def test_process_inventory_is_capped_at_maximum(
    page_factory,
    category_map,
):
    processes = [
        make_process(
            pid=1000 + index,
            name=f"process-{index}",
            memory_bytes=index * 1024,
        )
        for index in range(300)
    ]

    for process in processes:
        category_map[process.pid] = "Application"

    page = page_factory(processes)

    assert page.process_table.rowCount() == page.MAX_DISPLAYED_PROCESSES
    assert page.MAX_DISPLAYED_PROCESSES == 250


def table_process_names(page):
    """Return process names currently displayed in the inventory."""
    return [
        page.process_table.item(row, 1).text()
        for row in range(page.process_table.rowCount())
    ]


def test_inventory_defaults_to_cpu_descending(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=601, name="low", cpu_percent=10.0),
        make_process(pid=602, name="high", cpu_percent=80.0),
        make_process(pid=603, name="medium", cpu_percent=40.0),
        make_process(pid=604, name="unavailable", cpu_percent=None),
    ]

    page = page_factory(processes)

    assert table_process_names(page) == [
        "high",
        "medium",
        "low",
        "unavailable",
    ]


def test_inventory_supports_cpu_ascending(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=611, name="high", cpu_percent=80.0),
        make_process(pid=612, name="low", cpu_percent=10.0),
        make_process(pid=613, name="medium", cpu_percent=40.0),
    ]

    page = page_factory(processes)

    page.sort_direction.setCurrentIndex(1)

    assert table_process_names(page) == [
        "low",
        "medium",
        "high",
    ]


def test_inventory_supports_memory_descending(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=621, name="small", memory_bytes=1024),
        make_process(pid=622, name="large", memory_bytes=8192),
        make_process(pid=623, name="medium", memory_bytes=4096),
    ]

    page = page_factory(processes)

    page.sort_selector.setCurrentIndex(
        page.sort_selector.findData("memory_bytes")
    )

    assert table_process_names(page) == [
        "large",
        "medium",
        "small",
    ]


def test_inventory_search_matches_process_name(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=631, name="chrome"),
        make_process(pid=632, name="explorer"),
        make_process(pid=633, name="notepad"),
    ]

    page = page_factory(processes)

    page.search_input.setText("chrome")
    QTest.qWait(200)

    assert table_process_names(page) == ["chrome"]


def test_inventory_search_matches_pid(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=641, name="first"),
        make_process(pid=642, name="second"),
        make_process(pid=643, name="third"),
    ]

    page = page_factory(processes)

    page.search_input.setText("642")
    QTest.qWait(200)

    assert table_process_names(page) == ["second"]


def test_inventory_search_matches_executable_path(
    page_factory,
    category_map,
):
    processes = [
        make_process(
            pid=651,
            name="first",
            executable_path=r"C:\Program Files\AppOne\app.exe",
        ),
        make_process(
            pid=652,
            name="second",
            executable_path=r"C:\Windows\System32\second.exe",
        ),
    ]

    page = page_factory(processes)

    page.search_input.setText("AppOne")
    QTest.qWait(200)

    assert table_process_names(page) == ["first"]


def test_inventory_category_filter_shows_selected_category(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=661, name="system-process"),
        make_process(pid=662, name="application-process"),
        make_process(pid=663, name="service-process"),
    ]

    category_map.update({
        661: "System",
        662: "Application",
        663: "Service",
    })

    page = page_factory(processes)

    page.category_filter.setCurrentText("Application")

    assert table_process_names(page) == ["application-process"]


def test_inventory_combines_search_and_category_filter(
    page_factory,
    category_map,
):
    processes = [
        make_process(pid=671, name="chrome-helper"),
        make_process(pid=672, name="chrome-main"),
        make_process(pid=673, name="chrome-service"),
    ]

    category_map.update({
        671: "Application",
        672: "Application",
        673: "Service",
    })

    page = page_factory(processes)

    page.category_filter.setCurrentText("Application")
    page.search_input.setText("chrome")
    QTest.qWait(200)

    assert set(table_process_names(page)) == {
        "chrome-helper",
        "chrome-main",
    }


def test_inventory_refresh_uses_latest_measurement(
    page_factory,
    category_map,
):
    first = make_process(pid=681, name="first")
    second = make_process(pid=682, name="second")

    page = page_factory([first])

    assert table_process_names(page) == ["first"]

    page.controller._measurement = make_measurement([second])
    page.refresh()

    assert table_process_names(page) == ["second"]



def test_process_inventory_has_seven_expected_columns(page_factory):
    page = page_factory()

    assert page.process_table.columnCount() == 7
    assert [
        page.process_table.horizontalHeaderItem(column).text()
        for column in range(page.process_table.columnCount())
    ] == [
        "PID",
        "Name",
        "Category",
        "CPU %",
        "Memory",
        "Status",
        "Executable Path",
    ]


def test_inventory_displays_process_category(
    page_factory,
    category_map,
):
    process = make_process(pid=701, name="system-process")
    category_map[701] = "System"

    page = page_factory([process])

    assert page.process_table.item(0, 2).text() == "System"


def test_inventory_falls_back_to_unclassified_for_unknown_category(
    page_factory,
    category_map,
):
    process = make_process(pid=702, name="unknown-category")
    category_map[702] = "Unexpected Category"

    page = page_factory([process])

    assert page.process_table.item(0, 2).text() == "Unclassified"


def test_inventory_displays_executable_path(page_factory):
    executable_path = r"C:\Program Files\AppOne\app.exe"
    process = make_process(
        pid=703,
        name="app-one",
        executable_path=executable_path,
    )

    page = page_factory([process])

    assert page.process_table.item(0, 6).text() == executable_path


def test_inventory_displays_placeholder_for_missing_executable_path(
    page_factory,
):
    process = make_process(
        pid=704,
        name="path-unavailable",
        executable_path=None,
    )

    page = page_factory([process])

    assert page.process_table.item(0, 6).text() == "—"

def test_process_search_debounces_rapid_typing(page_factory, monkeypatch):
    refresh_calls = []
    original_refresh = ProcessesPage._refresh_inventory

    def tracked_refresh(page):
        refresh_calls.append(page.search_input.text())
        original_refresh(page)

    monkeypatch.setattr(
        ProcessesPage,
        "_refresh_inventory",
        tracked_refresh,
    )

    page = page_factory([
        make_process(pid=801, name="chrome"),
        make_process(pid=802, name="firefox"),
    ])
    refresh_calls.clear()

    page.search_input.setText("c")
    QTest.qWait(40)
    page.search_input.setText("ch")
    QTest.qWait(40)
    page.search_input.setText("chrome")

    assert refresh_calls == []

    QTest.qWait(200)

    assert refresh_calls == ["chrome"]
    assert table_process_names(page) == ["chrome"]


@pytest.mark.parametrize("control", ["category", "sort"])
def test_category_and_sort_changes_cancel_pending_search(
    page_factory,
    category_map,
    monkeypatch,
    control,
):
    category_map.update({
        811: "Application",
        812: "Application",
    })

    refresh_calls = []
    original_refresh = ProcessesPage._refresh_inventory

    def tracked_refresh(page):
        refresh_calls.append(page.search_input.text())
        original_refresh(page)

    monkeypatch.setattr(
        ProcessesPage,
        "_refresh_inventory",
        tracked_refresh,
    )

    page = page_factory([
        make_process(pid=811, name="app-alpha"),
        make_process(pid=812, name="app-beta"),
    ])
    refresh_calls.clear()

    page.search_input.setText("app")
    assert page._search_timer.isActive()

    if control == "category":
        page.category_filter.setCurrentText("Application")
    else:
        page.sort_selector.setCurrentIndex(1)

    assert not page._search_timer.isActive()
    assert refresh_calls == ["app"]

    QTest.qWait(200)

    assert refresh_calls == ["app"]
