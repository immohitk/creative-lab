from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from system_monitor.models.diagnostic_severity import DiagnosticSeverity
from system_monitor.models.service_diagnostic import ServiceDiagnostic


@dataclass(frozen=True, slots=True)
class DiagnosticSnapshot:
    coordinator_status: str
    services: Mapping[str, ServiceDiagnostic]
    coordinator_error: str | None
    coordinator_revision: int

    def __post_init__(self):
        if (
            not isinstance(self.coordinator_status, str)
            or not self.coordinator_status.strip()
        ):
            raise ValueError("coordinator_status must be a non-empty string.")

        if not isinstance(self.services, Mapping):
            raise TypeError("services must be a mapping.")

        services = dict(self.services)

        for name, diagnostic in services.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Service names must be non-empty strings.")

            if not isinstance(diagnostic, ServiceDiagnostic):
                raise TypeError(
                    "Every service entry must be a ServiceDiagnostic."
                )

            if name != diagnostic.service_name:
                raise ValueError(
                    "Service mapping keys must match diagnostic service names."
                )

        if (
            self.coordinator_error is not None
            and not isinstance(self.coordinator_error, str)
        ):
            raise TypeError("coordinator_error must be a string or None.")

        if (
            isinstance(self.coordinator_revision, bool)
            or not isinstance(self.coordinator_revision, int)
            or self.coordinator_revision < 0
        ):
            raise ValueError(
                "coordinator_revision must be a non-negative integer."
            )

        object.__setattr__(
            self,
            "services",
            MappingProxyType(services),
        )

    @property
    def severity(self) -> DiagnosticSeverity:
        service_severities = [
            diagnostic.severity
            for diagnostic in self.services.values()
        ]

        if DiagnosticSeverity.ERROR in service_severities:
            return DiagnosticSeverity.ERROR

        if self.coordinator_status == "FAILED":
            return DiagnosticSeverity.ERROR

        if DiagnosticSeverity.WARNING in service_severities:
            return DiagnosticSeverity.WARNING

        if self.coordinator_status == "DEGRADED":
            return DiagnosticSeverity.WARNING

        if DiagnosticSeverity.UNKNOWN in service_severities:
            return DiagnosticSeverity.UNKNOWN

        if self.coordinator_status in {
            "STOPPED",
            "STARTING",
            "STOPPING",
        }:
            return DiagnosticSeverity.UNKNOWN

        if self.coordinator_status != "RUNNING":
            return DiagnosticSeverity.UNKNOWN

        if not service_severities:
            return DiagnosticSeverity.UNKNOWN

        return DiagnosticSeverity.HEALTHY

    @property
    def healthy_count(self) -> int:
        return self._count(DiagnosticSeverity.HEALTHY)

    @property
    def warning_count(self) -> int:
        return self._count(DiagnosticSeverity.WARNING)

    @property
    def error_count(self) -> int:
        return self._count(DiagnosticSeverity.ERROR)

    @property
    def unknown_count(self) -> int:
        return self._count(DiagnosticSeverity.UNKNOWN)

    def _count(self, severity: DiagnosticSeverity) -> int:
        return sum(
            diagnostic.severity == severity
            for diagnostic in self.services.values()
        )