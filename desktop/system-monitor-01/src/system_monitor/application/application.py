"""Application bootstrap and lifecycle management."""

import logging
import sys

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from system_monitor.application.system_information_worker import (
    SystemInformationWorker,
)
from system_monitor.coordinator.monitoring_coordinator import (
    MonitoringCoordinator,
)
from system_monitor.presentation.main_window import MainWindow
from system_monitor.services.cpu_monitoring_service import (
    CpuMonitoringService,
)
from system_monitor.services.disk_monitoring_service import (
    DiskMonitoringService,
)
from system_monitor.services.memory_monitoring_service import (
    MemoryMonitoringService,
)
from system_monitor.services.network_monitoring_service import (
    NetworkMonitoringService,
)
from system_monitor.services.process_monitoring_service import (
    ProcessMonitoringService,
)


logger = logging.getLogger(__name__)


class SystemMonitorApplication(QObject):
    """Own application startup, runtime coordination and shutdown."""

    SHUTDOWN_POLL_INTERVAL_MS = 100

    def __init__(self, argv=None):
        super().__init__()
        self._argv = list(sys.argv if argv is None else argv)
        self._application = None
        self._services = {}
        self._coordinator = None
        self._system_information_worker = None
        self._system_profile = None
        self._system_information_error = None
        self._main_window = None

        self._shutdown_requested = False
        self._shutdown_complete = False

        self._shutdown_timer = QTimer()
        self._shutdown_timer.setInterval(
            self.SHUTDOWN_POLL_INTERVAL_MS
        )
        self._shutdown_timer.timeout.connect(
            self._check_shutdown_completion
        )

    @property
    def main_window(self):
        """Return the main application window."""
        return self._main_window

    @property
    def coordinator(self):
        """Return the monitoring coordinator."""
        return self._coordinator

    @property
    def services(self):
        """Return a read-only copy of the monitoring services mapping."""
        return dict(self._services)


    def _create_dependencies(self):
        """Construct monitoring services and their coordinator."""
        self._services = {
            "cpu": CpuMonitoringService(sampling_interval=1.0),
            "memory": MemoryMonitoringService(sampling_interval=1.0),
            "disk": DiskMonitoringService(sampling_interval=1.0),
            "network": NetworkMonitoringService(sampling_interval=1.0),
            "process": ProcessMonitoringService(sampling_interval=2.0),
        }

        self._coordinator = MonitoringCoordinator(
            cpu_service=self._services["cpu"],
            memory_service=self._services["memory"],
            disk_service=self._services["disk"],
            network_service=self._services["network"],
            process_service=self._services["process"],
        )


    def _initialize(self):
        """Initialize Qt, monitoring dependencies and the main window."""
        self._application = QApplication.instance()

        if self._application is None:
            self._application = QApplication(self._argv)

        self._application.setQuitOnLastWindowClosed(False)

        self._create_dependencies()
        self._main_window = MainWindow()
        self._main_window.close_requested.connect(
            self._request_shutdown
        )

        self._coordinator.status_changed.connect(
            self._handle_coordinator_status_changed
        )
        self._handle_coordinator_status_changed(
            self._coordinator.get_status()
        )


    def _start_system_information_collection(self):
        """Collect the initial system profile outside the GUI thread."""
        self._system_information_worker = SystemInformationWorker()

        self._system_information_worker.profile_ready.connect(
            self._handle_system_information_ready
        )
        self._system_information_worker.collection_failed.connect(
            self._handle_system_information_failure
        )
        self._system_information_worker.finished.connect(
            self._handle_system_information_finished
        )

        self._system_information_worker.start()

    def _handle_system_information_ready(self, profile):
        """Store the system profile collected by the background worker."""
        self._system_profile = profile
        self._system_information_error = None

    def _handle_system_information_failure(self, error):
        """Record an initial system information collection failure."""
        self._system_information_error = error
        logger.error("System information collection failed: %s", error)

    def _handle_system_information_finished(self):
        """Release the completed system information worker safely."""
        worker = self._system_information_worker
        if worker is None:
            return
        worker.wait()
        worker.deleteLater()
        self._system_information_worker = None
        self._check_shutdown_completion()

    def _handle_coordinator_status_changed(self, status):
        """Update the window status label from coordinator status."""
        status_value = getattr(status, "value", status)
        labels = {
            "STOPPED": "STOPPED",
            "STARTING": "INITIALIZING",
            "RUNNING": "MONITORING",
            "DEGRADED": "DEGRADED",
            "STOPPING": "SHUTTING DOWN",
            "FAILED": "ERROR",
        }
        if self._main_window is not None:
            self._main_window.application_status.setText(
                labels.get(status_value, status_value)
            )

    def _request_shutdown(self):
        if self._shutdown_requested:
            return

        self._shutdown_requested = True
        result = self._coordinator.stop()
        if not result.success and result.error:
            logger.warning(result.error)

        self._shutdown_timer.start()
        self._check_shutdown_completion()
    def _check_shutdown_completion(self):
        if not self._shutdown_requested or self._shutdown_complete:
            return

        for service in self._services.values():
            if service.is_worker_thread_alive():
                return

            if not service.is_cleanup_complete():
                service.stop()
                if not service.is_cleanup_complete():
                    return

        worker = self._system_information_worker
        if worker is not None:
            if worker.isRunning():
                return
            worker.wait()
            worker.deleteLater()
            self._system_information_worker = None

        self._shutdown_timer.stop()
        self._shutdown_complete = True

        if self._main_window is not None:
            self._main_window.allow_close()
            self._main_window.close()

        if self._application is not None:
            self._application.quit()
    def run(self):
        self._initialize()
        self._main_window.show()

        self._start_system_information_collection()

        result = self._coordinator.start()
        if not result.accepted:
            logger.error(result.error)

        return self._application.exec()
