import threading

from PySide6.QtCore import QTimer
from PySide6.QtTest import QSignalSpy, QTest

from system_monitor.application.system_information_worker import (
    SystemInformationWorker,
)


class FakeSystemInformationService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.started = threading.Event()
        self.release = threading.Event()
        self.thread_ident = None

    def collect(self):
        self.thread_ident = threading.get_ident()
        self.started.set()

        if not self.release.wait(5):
            raise TimeoutError("Test did not release collection.")

        if self.error is not None:
            raise self.error

        return self.result


def wait_for_signal(spy, timeout_ms=5000):
    elapsed = 0

    while spy.count() == 0 and elapsed < timeout_ms:
        QTest.qWait(10)
        elapsed += 10

    return spy.count() > 0


def schedule_worker_release(service):
    assert service.started.wait(5)
    QTimer.singleShot(50, service.release.set)


def test_worker_emits_collected_profile():
    profile = object()
    service = FakeSystemInformationService(result=profile)
    worker = SystemInformationWorker(service)

    profile_spy = QSignalSpy(worker.profile_ready)
    failure_spy = QSignalSpy(worker.collection_failed)

    worker.start()
    schedule_worker_release(service)

    assert wait_for_signal(profile_spy)
    assert worker.wait(5000)

    assert profile_spy.count() == 1
    assert profile_spy.at(0)[0] is profile
    assert failure_spy.count() == 0


def test_worker_emits_failure_for_unexpected_exception():
    service = FakeSystemInformationService(
        error=RuntimeError("Simulated collection failure")
    )
    worker = SystemInformationWorker(service)

    profile_spy = QSignalSpy(worker.profile_ready)
    failure_spy = QSignalSpy(worker.collection_failed)

    worker.start()
    schedule_worker_release(service)

    assert wait_for_signal(failure_spy)
    assert worker.wait(5000)

    assert failure_spy.count() == 1
    assert failure_spy.at(0)[0] == (
        "RuntimeError: Simulated collection failure"
    )
    assert profile_spy.count() == 0


def test_worker_collects_outside_gui_thread():
    service = FakeSystemInformationService(result=object())
    gui_thread_ident = threading.get_ident()
    worker = SystemInformationWorker(service)

    profile_spy = QSignalSpy(worker.profile_ready)

    worker.start()
    schedule_worker_release(service)

    assert wait_for_signal(profile_spy)
    assert worker.wait(5000)

    assert service.thread_ident != gui_thread_ident


def test_worker_is_not_running_after_collection():
    service = FakeSystemInformationService(result=object())
    worker = SystemInformationWorker(service)

    profile_spy = QSignalSpy(worker.profile_ready)

    worker.start()
    schedule_worker_release(service)

    assert wait_for_signal(profile_spy)
    assert worker.wait(5000)
    assert not worker.isRunning()
