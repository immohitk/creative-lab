"""Regression tests for efficient monitoring page table updates."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

from system_monitor.presentation.pages import MonitoringPage


def test_table_update_keeps_sorting_disabled():
    table = QTableWidget(0, 2)
    table.setSortingEnabled(False)

    MonitoringPage._update_table(table, [("101", "Example"), ("202", "Other")])

    assert table.isSortingEnabled() is False
    assert table.rowCount() == 2
    assert table.item(0, 0).text() == "101"


def test_table_update_preserves_enabled_sorting_policy():
    table = QTableWidget(0, 2)
    table.setSortingEnabled(True)

    MonitoringPage._update_table(table, [("101", "Example")])

    assert table.isSortingEnabled() is True


def test_table_update_centers_new_cell_values():
    table = QTableWidget(0, 1)

    MonitoringPage._update_table(table, [("Centered",)])

    assert table.item(0, 0).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert table.item(0, 0).textAlignment() & Qt.AlignmentFlag.AlignVCenter


def test_table_height_is_calculated_once_per_update():
    class HeightTrackingTable(QTableWidget):
        def __init__(self):
            super().__init__(0, 3)
            self.minimum_height_calls = []

        def setMinimumHeight(self, height):
            self.minimum_height_calls.append(height)
            super().setMinimumHeight(height)

    table = HeightTrackingTable()

    MonitoringPage._update_table(
        table,
        [
            ("101", "Chrome", "Running"),
            ("202", "Python", "Running"),
            ("303", "Explorer", "Running"),
        ],
    )

    assert len(table.minimum_height_calls) == 1
    assert table.minimum_height_calls[0] >= 180
