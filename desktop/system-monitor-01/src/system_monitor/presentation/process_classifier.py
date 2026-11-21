
from dataclasses import dataclass
import ntpath
import os

from system_monitor.models.process_measurement import ProcessMeasurement

from system_monitor.presentation.process_inventory import (
    CATEGORY_FILTERS,
    SORT_KEYS,
    filter_and_sort_processes,
)


@dataclass(frozen=True, slots=True)
class ProcessClassification:
    """Classification result for one process."""

    category: str
    confidence: str
    reason: str


class ProcessClassifier:
    """Classifies processes using collected executable and service metadata."""

    SYSTEM_DIRECTORIES = (
        "System32",
        "SysWOW64",
        "Sysnative",
        "WinSxS",
        "servicing",
        "System",
        "SystemResources",
        "Boot",
    )

    def __init__(
        self,
        *,
        windows_directory: str | None = None,
        application_directories: tuple[str, ...] | None = None,
    ) -> None:
        self._windows_directory = self._normalize_directory(
            windows_directory or os.environ.get("WINDIR", r"C:\Windows")
        )

        if application_directories is None:
            application_directories = self._default_application_directories()

        self._application_directories = tuple(
            normalized
            for directory in application_directories
            if (normalized := self._normalize_directory(directory)) is not None
        )

        self._system_directories = tuple(
            self._normalize_directory(
                ntpath.join(self._windows_directory, directory)
            )
            for directory in self.SYSTEM_DIRECTORIES
        )

    @staticmethod
    def _default_application_directories() -> tuple[str, ...]:
        """Return conventional Windows application installation locations."""
        directories = (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramW6432"),
        )

        local_app_data = os.environ.get("LOCALAPPDATA")

        if local_app_data:
            directories += (
                ntpath.join(local_app_data, "Programs"),
            )

        return tuple(directory for directory in directories if directory)

    @staticmethod
    def _normalize_directory(path: str | None) -> str | None:
        if not isinstance(path, str) or not path.strip():
            return None

        normalized = ntpath.normpath(path.strip())

        if not ntpath.isabs(normalized):
            return None

        return ntpath.normcase(normalized)

    @staticmethod
    def _is_within_directory(
        path: str,
        directory: str | None,
    ) -> bool:
        if directory is None:
            return False

        try:
            return ntpath.commonpath((path, directory)) == directory
        except ValueError:
            return False

    def _matches_any_directory(
        self,
        path: str,
        directories: tuple[str | None, ...],
    ) -> bool:
        return any(
            self._is_within_directory(path, directory)
            for directory in directories
        )

    def classify(
        self,
        measurement: ProcessMeasurement,
    ) -> ProcessClassification:
        """Classify one process without performing external lookups."""
        if not isinstance(measurement, ProcessMeasurement):
            raise TypeError("measurement must be a ProcessMeasurement.")

        if measurement.service_names:
            return ProcessClassification(
                category="Service",
                confidence="Verified",
                reason="PID is associated with one or more Windows services.",
            )

        executable_path = measurement.executable_path

        normalized_path = self._normalize_directory(executable_path)

        if normalized_path is not None:
            if self._matches_any_directory(
                normalized_path,
                self._system_directories,
            ):
                return ProcessClassification(
                    category="System",
                    confidence="Verified",
                    reason="Executable is inside a recognized Windows system directory.",
                )

            if self._matches_any_directory(
                normalized_path,
                self._application_directories,
            ):
                return ProcessClassification(
                    category="Application",
                    confidence="Verified",
                    reason="Executable is inside a recognized application installation directory.",
                )

        if measurement.metadata_state == "unavailable":
            confidence = "Unavailable"
            reason = "Executable and service classification metadata are unavailable."
        else:
            confidence = "Partial"
            reason = "Available metadata does not establish a recognized process category."

        return ProcessClassification(
            category="Unclassified",
            confidence=confidence,
            reason=reason,
        )
