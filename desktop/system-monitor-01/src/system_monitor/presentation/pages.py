"""Monitoring dashboard pages backed by MonitoringDataController."""

import heapq

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from system_monitor.presentation.widgets.history_chart import HistoryChart
from system_monitor.presentation.widgets.metric_card import MetricCard
from system_monitor.presentation.theme import colors


def _bytes(value):
    value = float(value)
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def _rate(value):
    return "—" if value is None else f"{_bytes(value)}/s"


def _status_text(controller, name):
    status = controller.status(name)
    freshness = controller.freshness(name)
    if freshness == "NO_DATA":
        result = f"{status} · NO DATA"
    elif freshness == "STALE":
        result = f"{status} · STALE DATA"
    else:
        result = f"{status} · FRESH"
    updated_at = controller.last_updated(name)
    if updated_at is not None:
        result += f" · Updated {updated_at.strftime('%H:%M:%S')} UTC"
    error = controller.error(name)
    if error is not None:
        message = getattr(error, "message", str(error))
        result += f" — {message}"
    return result


class MonitoringPage(QWidget):
    """Scrollable base page with a shared status line."""

    SERVICE = None

    def __init__(self, controller, title, description="", parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName(f"{title.lower()}_page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("page_scroll_area")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content.setObjectName("page_content")
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(20, 18, 20, 20)
        self.layout.setSpacing(20)
        self.description_label = QLabel(description)
        self.description_label.setObjectName("page_description")
        self.description_label.setWordWrap(True)
        self.layout.addWidget(self.description_label)
        self.status_label = QLabel("INITIALIZING · NO DATA")
        self.status_label.setObjectName("page_data_status")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName(f"{title} measurement status")
        self.layout.addWidget(self.status_label)
        self.scroll.setWidget(self.content)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        outer.addWidget(self.scroll)
        if self.SERVICE:
            controller.data_changed.connect(self._on_data_changed)

    def _on_data_changed(self, name):
        # Detailed pages only need work while visible. MainWindow refreshes a
        # page once when it becomes active, so hidden tables/charts stay idle.
        if name == self.SERVICE and self.isVisible():
            self.refresh()

    def _update_status(self, details=()):
        """Render status from source data so detail text never accumulates."""
        status = _status_text(self.controller, self.SERVICE)
        details = tuple(detail for detail in details if detail)
        if details:
            status += " · " + " · ".join(details)
        self.status_label.setText(status)

    @staticmethod
    def _create_table(
        headers,
        *,
        column_widths=None,
        stretch_column=None,
        left_aligned_columns=(),
    ):
        """Create a consistent, compact monitoring table."""
        table = QTableWidget(0, len(headers))
        table.setObjectName("monitoring_table")
        table.setHorizontalHeaderLabels(headers)

        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setSortingEnabled(False)
        table.setShowGrid(False)

        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)

        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setMinimumHeight(40)
        header.setStretchLastSection(stretch_column is None)
        header.setSectionResizeMode(
        QHeaderView.ResizeMode.Interactive
        )

        if column_widths:
            for index, width in enumerate(column_widths):
                if index < len(headers) and width:
                    table.setColumnWidth(index, width)

        if stretch_column is not None:
            if 0 <= stretch_column < len(headers):
                header.setSectionResizeMode(
                    stretch_column,
                    QHeaderView.ResizeMode.Stretch,
                )

        table.setProperty(
            "left_aligned_columns",
            list(left_aligned_columns),
        )

        table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        table.setMinimumHeight(180)
        table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        return table

    @staticmethod
    def _update_table(table, rows):
        """Update changed cells while preserving sorting and alignment."""
        sorting_was_enabled = table.isSortingEnabled()

        table.setUpdatesEnabled(False)
        table.setSortingEnabled(False)

        left_aligned = set(
            table.property("left_aligned_columns") or []
        )

        try:
            if table.rowCount() != len(rows):
                table.setRowCount(len(rows))

            for row_index, values in enumerate(rows):
                for column_index, value in enumerate(values):
                    value = str(value)

                    item = table.item(row_index, column_index)

                    if item is None:
                        item = QTableWidgetItem(value)
                        table.setItem(row_index, column_index, item)
                    elif item.text() != value:
                        item.setText(value)

                    if column_index in left_aligned:
                        alignment = (
                            Qt.AlignmentFlag.AlignLeft
                        |   Qt.AlignmentFlag.AlignVCenter
                        )
                    elif column_index == 0:
                        alignment = (
                            Qt.AlignmentFlag.AlignCenter
                        |   Qt.AlignmentFlag.AlignVCenter
                        )
                    else:
                        alignment = (
                            Qt.AlignmentFlag.AlignRight
                        |   Qt.AlignmentFlag.AlignVCenter
                        )

                    if item.textAlignment() != alignment:
                        item.setTextAlignment(alignment)

        finally:
            table.setSortingEnabled(sorting_was_enabled)
            table.setUpdatesEnabled(True)

    def refresh(self):
        self._update_status()


class OverviewPage(MonitoringPage):
    """System-wide live summary."""

    def __init__(self, controller, parent=None):
        super().__init__(
            controller, "Overview", "Live summary of system resource utilization", parent
        )
        grid = QGridLayout()
        self.cards = {
            "cpu": MetricCard("CPU Usage", "—", "%", "Overall processor utilization"),
            "memory": MetricCard("Memory Usage", "—", "%", "Physical memory utilization"),
            "disk": MetricCard("Disk Usage", "—", "%", "Combined volume utilization"),
            "network": MetricCard("Network Throughput", "—", "", "Combined upload and download"),
        }
        for index, card in enumerate(self.cards.values()):
            grid.addWidget(card, index // 2, index % 2)
        self.layout.addLayout(grid)
        self.layout.addStretch()
        controller.data_changed.connect(self._on_any_data_changed)
        self.refresh()

    def _on_any_data_changed(self, _name):
        if self.isVisible():
            self.refresh()

    def refresh(self):
        cpu = self.controller.measurement("cpu")
        memory = self.controller.measurement("memory")
        disk = self.controller.measurement("disk")
        network = self.controller.measurement("network")
        self.cards["cpu"].set_value(f"{cpu.overall_percent:.1f}" if cpu else "—")
        self.cards["memory"].set_value(f"{memory.percent:.1f}" if memory else "—")
        if disk and disk.volumes:
            total = sum(item.total_bytes for item in disk.volumes)
            used = sum(item.used_bytes for item in disk.volumes)
            self.cards["disk"].set_value(f"{used * 100 / total:.1f}" if total else "—")
            self.cards["disk"].set_description(f"{len(disk.volumes)} volume(s)")
        else:
            self.cards["disk"].set_value("—")
            self.cards["disk"].set_description("Volume capacity")
        if network:
            down_values = [
                item.download_bytes_per_second
                for item in network.interfaces
                if item.download_bytes_per_second is not None
            ]
            up_values = [
                item.upload_bytes_per_second
                for item in network.interfaces
                if item.upload_bytes_per_second is not None
            ]
            if down_values or up_values:
                self.cards["network"].set_value(
                    _rate(sum(down_values) + sum(up_values))
                )
            else:
                self.cards["network"].set_value("—")
        else:
            self.cards["network"].set_value("—")
        self.cards["cpu"].set_description(_status_text(self.controller, "cpu"))
        self.cards["memory"].set_description(_status_text(self.controller, "memory"))
        self.cards["disk"].set_description(_status_text(self.controller, "disk"))
        self.cards["network"].set_description(_status_text(self.controller, "network"))


class CpuPage(MonitoringPage):
    SERVICE = "cpu"

    def __init__(self, controller, parent=None):
        super().__init__(controller, "CPU", "Processor utilization and logical-core activity", parent)
        self.overall = MetricCard("Overall Usage", "—", "%")
        self.logical = MetricCard("Logical CPUs", "—")
        grid = QGridLayout()
        grid.addWidget(self.overall, 0, 0)
        grid.addWidget(self.logical, 0, 1)
        self.layout.addLayout(grid)
        self.chart = HistoryChart("CPU utilization history")
        self.layout.addWidget(self.chart)
        self.core_label = QLabel("Per-core utilization: waiting for measurements")
        self.core_label.setWordWrap(True)
        self.layout.addWidget(self.core_label)
        self.layout.addStretch()
        self.refresh()

    def refresh(self):
        super().refresh()
        measurement = self.controller.measurement("cpu")
        self.overall.set_value(f"{measurement.overall_percent:.1f}" if measurement else "—")
        self.logical.set_value(str(measurement.logical_cpu_count) if measurement else "—")
        self.core_label.setText(
            "Per-core: " + " · ".join(
                f"CPU {index + 1}: {value:.1f}%"
                for index, value in enumerate(measurement.per_cpu_percent)
            ) if measurement else "Per-core utilization is not available yet."
        )
        self.chart.set_series([("CPU", self.controller.history("cpu"), colors.STATUS_INFO)])


class MemoryPage(MonitoringPage):
    SERVICE = "memory"

    def __init__(self, controller, parent=None):
        super().__init__(controller, "Memory", "Physical memory and swap utilization", parent)
        grid = QGridLayout()
        self.cards = {
            "used": MetricCard("Used RAM", "—", ""),
            "available": MetricCard("Available RAM", "—", ""),
            "free": MetricCard("Free RAM", "—", ""),
            "swap": MetricCard("Swap Used", "—", ""),
        }
        for index, card in enumerate(self.cards.values()):
            grid.addWidget(card, index // 2, index % 2)
        self.layout.addLayout(grid)
        self.chart = HistoryChart("Memory utilization history")
        self.layout.addWidget(self.chart)
        self.layout.addStretch()
        self.refresh()

    def refresh(self):
        super().refresh()
        measurement = self.controller.measurement("memory")
        if measurement:
            self.cards["used"].set_value(_bytes(measurement.used_bytes))
            self.cards["available"].set_value(_bytes(measurement.available_bytes))
            self.cards["free"].set_value(_bytes(measurement.free_bytes))
            self.cards["swap"].set_value(
                f"{_bytes(measurement.swap_used_bytes)} ({measurement.swap_percent:.1f}%)"
            )
        else:
            for card in self.cards.values():
                card.set_value("—")
        self.chart.set_series([("Memory", self.controller.history("memory"), colors.STATUS_SUCCESS)])


class DiskPage(MonitoringPage):
    SERVICE = "disk"

    def __init__(self, controller, parent=None):
        super().__init__(controller, "Disk", "Storage capacity, volumes and disk activity availability", parent)
        self.capacity = MetricCard("Combined Capacity", "—")
        self.used = MetricCard("Combined Used", "—")
        self.free = MetricCard("Combined Free", "—")
        grid = QGridLayout()
        for index, card in enumerate((self.capacity, self.used, self.free)):
            grid.addWidget(card, 0, index)
        self.layout.addLayout(grid)
        self.chart = HistoryChart("Combined volume utilization history")
        self.layout.addWidget(self.chart)
        self.volume_table = self._create_table(
            (
                "Volume",
                "Mount point",
                "Filesystem",
                "Capacity",
                "Used",
                "Free",
                "Used %",
            ),
            column_widths=(90, 160, 110, 110, 110, 110, 90),
            stretch_column=1,
            left_aligned_columns=(0, 1, 2),
        )
        self.layout.addWidget(QLabel("Volumes and partitions"))
        self.layout.addWidget(self.volume_table)
        self.activity_label = QLabel(
            "Disk read/write activity is unavailable: the current monitoring backend "
            "does not collect disk I/O throughput."
        )
        self.activity_label.setWordWrap(True)
        self.activity_label.setObjectName("placeholder_description")
        self.layout.addWidget(QLabel("Disk activity"))
        self.layout.addWidget(self.activity_label)
        self.layout.addStretch()
        self.refresh()


    def refresh(self):
        super().refresh()
        measurement = self.controller.measurement("disk")
        volumes = measurement.volumes if measurement else ()
        if volumes:
            total = sum(item.total_bytes for item in volumes)
            used = sum(item.used_bytes for item in volumes)
            free = sum(item.free_bytes for item in volumes)
            self.capacity.set_value(_bytes(total))
            self.used.set_value(_bytes(used))
            self.free.set_value(_bytes(free))
        else:
            for card in (self.capacity, self.used, self.free):
                card.set_value("—")
        self._update_table(self.volume_table, [
            (
                volume.device, volume.mount_point, volume.filesystem or "—",
                _bytes(volume.total_bytes), _bytes(volume.used_bytes),
                _bytes(volume.free_bytes), f"{volume.percent:.1f}%",
            )
            for volume in volumes
        ])
        details = (
            [f"{len(measurement.volume_errors)} volume error(s)"]
            if measurement and measurement.volume_errors else []
        )
        self._update_status(details)
        self.chart.set_series([("Disk", self.controller.history("disk"), colors.STATUS_WARNING)])


class NetworkPage(MonitoringPage):
    SERVICE = "network"

    def __init__(self, controller, parent=None):
        super().__init__(controller, "Network", "Interface traffic and transfer rates", parent)
        self.download = MetricCard("Download", "—", "")
        self.upload = MetricCard("Upload", "—", "")
        grid = QGridLayout()
        grid.addWidget(self.download, 0, 0)
        grid.addWidget(self.upload, 0, 1)
        self.layout.addLayout(grid)
        self.chart = HistoryChart("Network throughput history", " B/s")
        self.layout.addWidget(self.chart)
        self.interface_table = self._create_table(
            ("Interface", "Received", "Sent", "Download", "Upload"),
            column_widths=(180, 130, 130, 150, 150),
            stretch_column=0,
            left_aligned_columns=(0,),
        )
        self.layout.addWidget(QLabel("Network interfaces"))
        self.layout.addWidget(self.interface_table)
        self.layout.addStretch()
        self.refresh()

    def refresh(self):
        super().refresh()
        measurement = self.controller.measurement("network")
        interfaces = measurement.interfaces if measurement else ()
        down_values = [
            item.download_bytes_per_second for item in interfaces
            if item.download_bytes_per_second is not None
        ]
        up_values = [
            item.upload_bytes_per_second for item in interfaces
            if item.upload_bytes_per_second is not None
        ]
        self.download.set_value(_rate(sum(down_values)) if down_values else "—")
        self.upload.set_value(_rate(sum(up_values)) if up_values else "—")
        self._update_table(self.interface_table, [
            (
                item.name, _bytes(item.bytes_received), _bytes(item.bytes_sent),
                _rate(item.download_bytes_per_second),
                _rate(item.upload_bytes_per_second),
            )
            for item in interfaces
        ])
        details = []
        if measurement:
            if measurement.interface_errors:
                details.append(f"{len(measurement.interface_errors)} interface error(s)")
            if measurement.baseline_only_interface_ids:
                details.append(
                    f"{len(measurement.baseline_only_interface_ids)} interface(s) awaiting rate baseline"
                )
            if measurement.counter_resets:
                details.append(f"{len(measurement.counter_resets)} counter reset(s)")
        self._update_status(details)
        self.chart.set_series([
            ("Download", self.controller.history("network_download"), colors.STATUS_INFO),
            ("Upload", self.controller.history("network_upload"), colors.STATUS_SUCCESS),
        ])


class ProcessesPage(MonitoringPage):
    SERVICE = "process"
    MAX_DISPLAYED_PROCESSES = 250

    def __init__(self, controller, parent=None):
        super().__init__(controller, "Processes", "Processes sampled by CPU and memory usage", parent)
        self.summary = QLabel("Waiting for process measurements")
        self.layout.addWidget(self.summary)
        self.process_table = self._create_table(
            ("PID", "Name", "CPU %", "Memory", "Status"),
            column_widths=(90, 300, 110, 150, 130),
            stretch_column=1,
            left_aligned_columns=(1, 4),
        )
        self.layout.addWidget(self.process_table)
        self.layout.addStretch()
        self.refresh()

    def refresh(self):
        super().refresh()
        measurement = self.controller.measurement("process")
        processes = measurement.processes if measurement else ()
        # Select the highest-memory rows without sorting the entire process list.
        displayed = heapq.nlargest(
            self.MAX_DISPLAYED_PROCESSES,
            processes,
            key=lambda process: process.memory_bytes,
        )
        if measurement:
            self.summary.setText(
                f"Showing {len(displayed)} of {len(processes)} process(es), "
                "ordered by memory usage"
            )
        else:
            self.summary.setText("Process data unavailable")
        self._update_table(self.process_table, [
            (
                str(process.pid), process.name,
                f"{process.cpu_percent:.1f}" if process.cpu_percent is not None else "—",
                _bytes(process.memory_bytes), process.status,
            )
            for process in displayed
        ])
        details = (
            [f"{len(measurement.process_errors)} process error(s)"]
            if measurement and measurement.process_errors else []
        )
        self._update_status(details)


def build_monitoring_pages(controller):
    """Return page widgets keyed by the existing navigation labels."""
    return {
        "Overview": OverviewPage(controller),
        "CPU": CpuPage(controller),
        "Memory": MemoryPage(controller),
        "Disk": DiskPage(controller),
        "Network": NetworkPage(controller),
        "Processes": ProcessesPage(controller),
    }
