"""Monitoring dashboard pages backed by MonitoringDataController."""

import heapq

import os

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

    QComboBox,

    QHBoxLayout,

    QLineEdit,

)

from system_monitor.presentation.widgets.history_chart import HistoryChart

from system_monitor.presentation.widgets.metric_card import MetricCard

from system_monitor.presentation.theme import colors

from system_monitor.presentation.process_classifier import ProcessClassifier

from system_monitor.presentation.process_inventory import (

    CATEGORY_FILTERS,

    SORT_KEYS,

    filter_and_sort_processes,

)

from system_monitor.presentation.widgets.process_category_card import (

    ProcessCategoryCard,

)

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

        table.setHorizontalScrollBarPolicy(

            Qt.ScrollBarPolicy.ScrollBarAsNeeded

        )

        table.setVerticalScrollBarPolicy(

            Qt.ScrollBarPolicy.ScrollBarAlwaysOff

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

            QSizePolicy.Policy.Minimum,

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

                    # Let the outer page scroll area own vertical scrolling.

                    # Expand the table to fit all its rows.

                    header_height = table.horizontalHeader().height()

                    row_height = table.verticalHeader().defaultSectionSize()

                    frame_height = table.frameWidth() * 2

                    content_height = (

                        header_height

                        + table.rowCount() * row_height

                        + frame_height

                    )

                    table.setMinimumHeight(max(180, content_height))

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

        services = ("cpu", "memory", "disk", "network")

        self.status_label.setText(

            "  |  ".join(

                f"{name.upper()}: "

                f"{self.controller.status(name)} · "

                f"{self.controller.freshness(name)}"

                for name in services

            )

        )

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

    """Process intelligence overview and resource leaders."""

    SERVICE = "process"

    MAX_DISPLAYED_PROCESSES = 250

    CATEGORIES = ("System", "Service", "Application", "Unclassified")

    CATEGORY_COLORS = {

        "System": "#60A5FA",

        "Service": "#A78BFA",

        "Application": "#22C55E",

        "Unclassified": "#94A3B8",

    }

    def __init__(self, controller, parent=None):

        super().__init__(

            controller,

            "Processes",

            "Live process intelligence · Classification and resource analysis · Read only",

            parent,

        )

        self.classifier = ProcessClassifier()
        self._cached_measurement = None
        self._cached_processes = ()
        self._cached_classifications = {}

        self.overview_cards = {

            "total": MetricCard("Total Processes", "—"),

            "cpu": MetricCard("Combined Process CPU", "—", "%"),

            "memory": MetricCard("Combined Process Memory", "—"),

            "classified": MetricCard("Classified Processes", "—"),

        }

        overview_grid = QGridLayout()

        overview_grid.setContentsMargins(0, 0, 0, 0)

        overview_grid.setHorizontalSpacing(14)

        overview_grid.setVerticalSpacing(14)

        overview_grid.setColumnStretch(0, 1)

        overview_grid.setColumnStretch(1, 1)

        for index, card in enumerate(self.overview_cards.values()):

            overview_grid.addWidget(card, index // 2, index % 2)

        self.layout.addLayout(overview_grid)

        self.category_cards = {

            category: ProcessCategoryCard(

                category,

                self.CATEGORY_COLORS[category],

            )

            for category in self.CATEGORIES

        }

        category_grid = QGridLayout()

        category_grid.setContentsMargins(0, 0, 0, 0)

        category_grid.setHorizontalSpacing(14)

        category_grid.setVerticalSpacing(14)

        for column in range(len(self.CATEGORIES)):

            category_grid.setColumnStretch(column, 1)

        for index, card in enumerate(self.category_cards.values()):

            category_grid.addWidget(card, 0, index)

        classification_heading = QLabel("PROCESS CLASSIFICATION")

        classification_heading.setObjectName("section_heading")

        self.layout.addWidget(classification_heading)

        self.layout.addLayout(category_grid)

        leaders_grid = QGridLayout()

        leaders_grid.setContentsMargins(0, 0, 0, 0)

        leaders_grid.setHorizontalSpacing(14)

        leaders_grid.setVerticalSpacing(14)

        leaders_grid.setColumnStretch(0, 1)

        leaders_grid.setColumnStretch(1, 1)

        self.cpu_leaders = self._create_leader_panel(

            "TOP CPU CONSUMERS",

            "Processes with the highest reported CPU usage",

        )

        self.memory_leaders = self._create_leader_panel(

            "TOP MEMORY CONSUMERS",

            "Processes using the most physical memory",

        )

        leaders_grid.addWidget(self.cpu_leaders["frame"], 0, 0)

        leaders_grid.addWidget(self.memory_leaders["frame"], 0, 1)

        leaders_heading = QLabel("RESOURCE LEADERS")

        leaders_heading.setObjectName("section_heading")

        self.layout.addWidget(leaders_heading)

        self.layout.addLayout(leaders_grid)

        self.application_label = QLabel(

            f"THIS APPLICATION · PID {os.getpid()} · READ ONLY"

        )

        self.application_label.setObjectName("placeholder_description")

        self.layout.addWidget(self.application_label)

        self.summary = QLabel("Waiting for process measurements")

        self.summary.setWordWrap(True)

        self.layout.addWidget(self.summary)

        self.search_input = QLineEdit()

        self.search_input.setPlaceholderText("Search process name, PID or path...")

        self.search_input.setClearButtonEnabled(True)

        self.category_filter = QComboBox()

        self.category_filter.addItems(CATEGORY_FILTERS)

        self.sort_selector = QComboBox()

        self.sort_selector.addItem("CPU", "cpu_percent")

        self.sort_selector.addItem("Memory", "memory_bytes")

        self.sort_selector.addItem("Name", "name")

        self.sort_selector.addItem("PID", "pid")

        self.sort_selector.addItem("Category", "category")

        self.sort_selector.addItem("Status", "status")

        self.sort_selector.addItem("Executable Path", "executable_path")

        self.sort_direction = QComboBox()

        self.sort_direction.addItem("Descending", True)

        self.sort_direction.addItem("Ascending", False)

        toolbar = QHBoxLayout()

        toolbar.setSpacing(10)

        toolbar.addWidget(self.search_input, 3)

        toolbar.addWidget(self.category_filter, 1)

        toolbar.addWidget(self.sort_selector, 1)

        toolbar.addWidget(self.sort_direction, 1)

        self.layout.addLayout(toolbar)

        self.search_input.textChanged.connect(self._refresh_inventory)
        self.category_filter.currentTextChanged.connect(self._refresh_inventory)
        self.sort_selector.currentIndexChanged.connect(self._refresh_inventory)
        self.sort_direction.currentIndexChanged.connect(self._refresh_inventory)

        self.process_table = self._create_table(

            (

                "PID",

                "Name",

                "Category",

                "CPU %",

                "Memory",

                "Status",

                "Executable Path",

            ),

            column_widths=(80, 220, 130, 90, 120, 110, 360),

            stretch_column=6,

            left_aligned_columns=(1, 2, 5, 6),

        )

        self.layout.addWidget(self.process_table)

        self.layout.addStretch()

        self.refresh()

    @staticmethod

    def _create_leader_panel(title, description):

        frame = QFrame()

        frame.setObjectName("process_leader_panel")

        layout = QVBoxLayout(frame)

        layout.setContentsMargins(14, 12, 14, 12)

        layout.setSpacing(8)

        heading = QLabel(title)

        heading.setObjectName("section_heading")

        subtitle = QLabel(description)

        subtitle.setObjectName("placeholder_description")

        subtitle.setWordWrap(True)

        rows = []

        for _ in range(5):

            label = QLabel("—")

            label.setObjectName("process_leader_row")

            label.setWordWrap(True)

            rows.append(label)

        layout.addWidget(heading)

        layout.addWidget(subtitle)

        for label in rows:

            layout.addWidget(label)

        return {

            "frame": frame,

            "rows": rows,

        }

    @staticmethod

    def _update_leader_panel(panel, processes, metric):

        for index, label in enumerate(panel["rows"]):

            if index >= len(processes):

                label.setText("—")

                continue

            process = processes[index]

            value = getattr(process, metric)

            if metric == "cpu_percent":

                value_text = (

                    f"{value:.1f}%"

                    if value is not None

                    else "CPU unavailable"

                )

            else:

                value_text = _bytes(value)

            label.setText(

                f"{index + 1}. {process.name}  ·  "

                f"PID {process.pid}  ·  {value_text}"

            )

    def _refresh_inventory(self):
        """Refresh only the filtered and sorted process inventory."""
        processes = self._cached_processes
        classifications = self._cached_classifications
        measurement = self._cached_measurement

        sort_key = self.sort_selector.currentData()
        sort_descending = self.sort_direction.currentData()

        filtered_processes = filter_and_sort_processes(
            processes,
            classifications,
            search_text=self.search_input.text(),
            category=self.category_filter.currentText(),
            sort_key=sort_key,
            descending=sort_descending,
        )

        displayed = filtered_processes[:self.MAX_DISPLAYED_PROCESSES]

        if measurement:
            direction_label = (
                "descending" if sort_descending else "ascending"
            )
            self.summary.setText(
                f"Showing {len(displayed)} of {len(filtered_processes)} "
                f"matching processes · Sorted by {self.sort_selector.currentText()} "
                f"({direction_label}) · {len(processes)} total processes"
            )
        else:
            self.summary.setText("Process data unavailable")

        self._update_table(
            self.process_table,
            [
                (
                    str(process.pid),
                    process.name,
                    (
                        classifications[process.pid].category
                        if classifications[process.pid].category in self.CATEGORIES
                        else "Unclassified"
                    ),
                    (
                        f"{process.cpu_percent:.1f}"
                        if process.cpu_percent is not None
                        else "—"
                    ),
                    _bytes(process.memory_bytes),
                    process.status,
                    process.executable_path or "—",
                )
                for process in displayed
            ],
        )

    def refresh(self):
        """Refresh process metrics and reuse classifications for unchanged data."""
        super().refresh()

        measurement = self.controller.measurement("process")

        # Reclassify only when a new measurement object arrives.
        if measurement is not self._cached_measurement:
            processes = measurement.processes if measurement else ()

            classifications = {
                process.pid: self.classifier.classify(process)
                for process in processes
            }

            self._cached_measurement = measurement
            self._cached_processes = processes
            self._cached_classifications = classifications

        processes = self._cached_processes
        classifications = self._cached_classifications

        grouped = {
            category: []
            for category in self.CATEGORIES
        }

        for process in processes:
            classification = classifications[process.pid]
            category = classification.category

            if category not in grouped:
                category = "Unclassified"

            grouped[category].append(process)

        total_cpu = sum(
            process.cpu_percent
            for process in processes
            if process.cpu_percent is not None
        )

        total_memory = sum(
            process.memory_bytes
            for process in processes
        )

        classified_count = (
            len(processes) - len(grouped["Unclassified"])
        )

        self.overview_cards["total"].set_value(str(len(processes)))
        self.overview_cards["cpu"].set_value(f"{total_cpu:.1f}")
        self.overview_cards["memory"].set_value(_bytes(total_memory))
        self.overview_cards["classified"].set_value(
            f"{classified_count} / {len(processes)}"
        )

        for category, card in self.category_cards.items():
            category_processes = grouped[category]

            category_cpu = sum(
                process.cpu_percent
                for process in category_processes
                if process.cpu_percent is not None
            )

            category_memory = sum(
                process.memory_bytes
                for process in category_processes
            )

            card.set_metrics(
                process_count=len(category_processes),
                cpu_percent=category_cpu,
                memory_bytes=category_memory,
            )

        cpu_processes = heapq.nlargest(
            5,
            (
                process for process in processes
                if process.cpu_percent is not None
            ),
            key=lambda process: (
                process.cpu_percent,
                process.memory_bytes,
            ),
        )

        memory_processes = heapq.nlargest(
            5,
            processes,
            key=lambda process: process.memory_bytes,
        )

        self._update_leader_panel(
            self.cpu_leaders,
            cpu_processes,
            "cpu_percent",
        )

        self._update_leader_panel(
            self.memory_leaders,
            memory_processes,
            "memory_bytes",
        )

        self._refresh_inventory()

        details = (
            [f"{len(measurement.process_errors)} process error(s)"]
            if measurement and measurement.process_errors
            else []
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
