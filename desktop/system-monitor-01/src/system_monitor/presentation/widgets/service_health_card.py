
"""Reusable service health diagnostic card."""

from datetime import datetime

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from system_monitor.models import (
    DiagnosticSeverity,
    ServiceDiagnostic,
)
from system_monitor.presentation.theme import spacing
from system_monitor.presentation.widgets.status_indicator import (
    StatusIndicator,
)


class ServiceHealthCard(QFrame):
    """Display the diagnostic health and runtime details of one service."""

    SEVERITY_PRESENTATION = {
        DiagnosticSeverity.HEALTHY: ("Healthy", "success"),
        DiagnosticSeverity.WARNING: ("Warning", "warning"),
        DiagnosticSeverity.ERROR: ("Error", "error"),
        DiagnosticSeverity.UNKNOWN: ("Unknown", "neutral"),
    }

    SERVICE_LABELS = {
        "cpu": "CPU",
        "memory": "Memory",
        "disk": "Disk",
        "network": "Network",
        "process": "Processes",
    }

    def __init__(
        self,
        diagnostic: ServiceDiagnostic,
        parent=None,
    ):
        super().__init__(parent)

        self._validate_diagnostic(diagnostic)
        self._diagnostic = diagnostic

        service_label = self._service_label(diagnostic.service_name)

        self.setObjectName("service_health_card")
        self.setAccessibleName(f"{service_label} service health")

        self._build_ui()
        self.set_diagnostic(diagnostic)

    @staticmethod
    def _validate_diagnostic(diagnostic):
        if not isinstance(diagnostic, ServiceDiagnostic):
            raise TypeError(
                "diagnostic must be a ServiceDiagnostic."
            )

    @classmethod
    def _service_label(cls, service_name):
        return cls.SERVICE_LABELS.get(
            service_name.lower(),
            service_name.replace("_", " ").title(),
        )

    @staticmethod
    def _format_timestamp(value):
        if value is None:
            return "Unavailable"

        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")

        return str(value)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            spacing.SERVICE_HEALTH_CARD_PADDING_HORIZONTAL,
            spacing.SERVICE_HEALTH_CARD_PADDING_VERTICAL,
            spacing.SERVICE_HEALTH_CARD_PADDING_HORIZONTAL,
            spacing.SERVICE_HEALTH_CARD_PADDING_VERTICAL,
        )
        layout.setSpacing(spacing.SERVICE_HEALTH_CARD_SPACING)

        self.title_label = QLabel()
        self.title_label.setObjectName("service_health_title")
        layout.addWidget(self.title_label)

        self.status_indicator = StatusIndicator(
            text="Unknown",
            status="neutral",
        )
        layout.addWidget(self.status_indicator)

        self.worker_state_label = QLabel()
        self.worker_state_label.setObjectName(
            "service_health_detail"
        )
        layout.addWidget(self.worker_state_label)

        self.measurement_status_label = QLabel()
        self.measurement_status_label.setObjectName(
            "service_health_detail"
        )
        layout.addWidget(self.measurement_status_label)

        self.freshness_label = QLabel()
        self.freshness_label.setObjectName(
            "service_health_detail"
        )
        layout.addWidget(self.freshness_label)

        self.last_updated_label = QLabel()
        self.last_updated_label.setObjectName(
            "service_health_detail"
        )
        layout.addWidget(self.last_updated_label)

        self.failures_label = QLabel()
        self.failures_label.setObjectName(
            "service_health_detail"
        )
        layout.addWidget(self.failures_label)

        self.sampling_interval_label = QLabel()
        self.sampling_interval_label.setObjectName(
            "service_health_detail"
        )
        layout.addWidget(self.sampling_interval_label)

        self.error_label = QLabel()
        self.error_label.setObjectName("service_health_error")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

    def set_diagnostic(self, diagnostic: ServiceDiagnostic):
        """Update the card from a new immutable service diagnostic."""
        self._validate_diagnostic(diagnostic)
        self._diagnostic = diagnostic

        service_label = self._service_label(
            diagnostic.service_name
        )
        severity_text, status_variant = self.SEVERITY_PRESENTATION[
            diagnostic.severity
        ]

        self.title_label.setText(service_label)
        self.status_indicator.set_text(severity_text)
        self.status_indicator.set_status(status_variant)

        self.worker_state_label.setText(
            f"Worker: {diagnostic.worker_state}"
        )
        self.measurement_status_label.setText(
            f"Measurement: {diagnostic.measurement_status}"
        )
        self.freshness_label.setText(
            f"Freshness: {diagnostic.freshness}"
        )
        self.last_updated_label.setText(
            f"Last updated: "
            f"{self._format_timestamp(diagnostic.last_updated)}"
        )
        self.failures_label.setText(
            f"Consecutive failures: "
            f"{diagnostic.consecutive_failures}"
        )
        self.sampling_interval_label.setText(
            f"Sampling interval: "
            f"{diagnostic.sampling_interval:g} seconds"
        )

        error_text = diagnostic.error or ""
        self.error_label.setText(
            f"Error: {error_text}" if error_text else ""
        )
        self.error_label.setVisible(bool(error_text))

        self.setAccessibleDescription(
            f"{service_label}: {severity_text}. "
            f"Worker {diagnostic.worker_state}. "
            f"Measurement {diagnostic.measurement_status}. "
            f"Freshness {diagnostic.freshness}."
        )

    @property
    def diagnostic(self) -> ServiceDiagnostic:
        """Return the diagnostic currently displayed by the card."""
        return self._diagnostic
