from dataclasses import dataclass

from system_monitor.models.diagnostic_severity import DiagnosticSeverity


@dataclass(frozen=True, slots=True)
class ServiceDiagnostic:
    service_name: str
    worker_state: str
    measurement_status: str
    freshness: str
    severity: DiagnosticSeverity
    last_updated: object | None
    error: str | None
    consecutive_failures: int
    sampling_interval: float
    revision: int

    def __post_init__(self):
        for field_name in (
            "service_name",
            "worker_state",
            "measurement_status",
            "freshness",
        ):
            value = getattr(self, field_name)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")

        if not isinstance(self.severity, DiagnosticSeverity):
            raise TypeError("severity must be a DiagnosticSeverity.")

        if self.error is not None and not isinstance(self.error, str):
            raise TypeError("error must be a string or None.")

        if (
            isinstance(self.consecutive_failures, bool)
            or not isinstance(self.consecutive_failures, int)
            or self.consecutive_failures < 0
        ):
            raise ValueError(
                "consecutive_failures must be a non-negative integer."
            )

        if (
            isinstance(self.sampling_interval, bool)
            or not isinstance(self.sampling_interval, (int, float))
        ):
            raise TypeError("sampling_interval must be numeric.")

        interval = float(self.sampling_interval)

        if not 0.5 <= interval <= 60.0:
            raise ValueError(
                "sampling_interval must be between 0.5 and 60 seconds."
            )

        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 0
        ):
            raise ValueError("revision must be a non-negative integer.")

        object.__setattr__(self, "sampling_interval", interval)