
"""Reusable process category summary card."""

import math

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


def _format_bytes(value: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    amount = float(value)

    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024

    return f"{amount:.1f} PB"


class ProcessCategoryCard(QFrame):
    """Display process count and resource usage for one category."""

    def __init__(
        self,
        category: str,
        accent_color: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        if not isinstance(category, str) or not category.strip():
            raise ValueError("category must be a non-empty string.")

        if not isinstance(accent_color, str) or not accent_color.strip():
            raise ValueError("accent_color must be a non-empty string.")

        self.category = category
        self.setObjectName("process_category_card")
        self.setAccessibleName(f"{category} process category")

        self._build_ui(accent_color)

        self.set_metrics(
            process_count=0,
            cpu_percent=None,
            memory_bytes=0,
        )

    def _build_ui(self, accent_color: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        heading_layout = QHBoxLayout()
        heading_layout.setSpacing(8)

        self.marker = QLabel()
        self.marker.setObjectName("process_category_marker")
        self.marker.setFixedSize(4, 18)
        self.marker.setStyleSheet(
            f"background-color: {accent_color}; border-radius: 2px;"
        )
        heading_layout.addWidget(self.marker)

        self.category_label = QLabel(self.category.upper())
        self.category_label.setObjectName("process_category_title")
        heading_layout.addWidget(self.category_label)
        heading_layout.addStretch()

        layout.addLayout(heading_layout)

        self.count_label = QLabel("0")
        self.count_label.setObjectName("process_category_count")
        layout.addWidget(self.count_label)

        resource_layout = QHBoxLayout()
        resource_layout.setSpacing(12)

        self.cpu_label = QLabel("CPU —")
        self.cpu_label.setObjectName("process_category_cpu")
        resource_layout.addWidget(self.cpu_label)

        resource_layout.addStretch()

        self.memory_label = QLabel("Memory 0 B")
        self.memory_label.setObjectName("process_category_memory")
        resource_layout.addWidget(self.memory_label)

        layout.addLayout(resource_layout)

    def set_metrics(
        self,
        *,
        process_count: int,
        cpu_percent: float | None,
        memory_bytes: int,
    ) -> None:
        """Update category count and aggregated resource usage."""
        if (
            isinstance(process_count, bool)
            or not isinstance(process_count, int)
            or process_count < 0
        ):
            raise ValueError("process_count must be a non-negative integer.")

        if cpu_percent is not None:
            if isinstance(cpu_percent, bool) or not isinstance(
                cpu_percent, (int, float)
            ):
                raise TypeError("cpu_percent must be numeric or None.")

            cpu_percent = float(cpu_percent)

            if not math.isfinite(cpu_percent) or cpu_percent < 0:
                raise ValueError(
                    "cpu_percent must be finite and non-negative."
                )

        if (
            isinstance(memory_bytes, bool)
            or not isinstance(memory_bytes, int)
            or memory_bytes < 0
        ):
            raise ValueError("memory_bytes must be a non-negative integer.")

        self.count_label.setText(f"{process_count:,}")
        self.cpu_label.setText(
            f"CPU {cpu_percent:.1f}%"
            if cpu_percent is not None
            else "CPU —"
        )
        self.memory_label.setText(
            f"Memory {_format_bytes(memory_bytes)}"
        )

        self.setAccessibleDescription(
            f"{self.category}: {process_count} processes, "
            f"CPU {cpu_percent:.1f}%"
            if cpu_percent is not None
            else f"{self.category}: {process_count} processes, CPU unavailable"
        )
