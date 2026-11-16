"""Background worker for initial system information collection."""

import logging

from PySide6.QtCore import QThread, Signal

from system_monitor.services.system_information_service import (
    SystemInformationService,
)


logger = logging.getLogger(__name__)


class SystemInformationWorker(QThread):
    """Collect system information outside the GUI thread."""

    profile_ready = Signal(object)
    collection_failed = Signal(str)

    def __init__(self, service=None, parent=None):
        super().__init__(parent)
        self._service = service or SystemInformationService()

    def run(self):
        try:
            profile = self._service.collect()
        except Exception as exc:
            logger.exception("System information collection failed.")
            self.collection_failed.emit(
                f"{type(exc).__name__}: {exc}"
            )
            return

        self.profile_ready.emit(profile)
