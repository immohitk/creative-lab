from types import SimpleNamespace

from system_monitor.application.application import SystemMonitorApplication


class FakeService:
    def __init__(self, alive=False):
        self.alive = alive

    def is_worker_thread_alive(self):
        return self.alive

class FakeCoordinator:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1
        return SimpleNamespace(success=True, error=None)



def test_shutdown_waits_for_worker_and_ignores_repeated_requests(qt_application):
    application = SystemMonitorApplication(argv=[])
    coordinator = FakeCoordinator()
    application._coordinator = coordinator
    application._services = dict(cpu=FakeService(alive=True))

    application._request_shutdown()
    application._request_shutdown()

    assert coordinator.stop_calls == 1
    assert application._shutdown_requested is True
    assert application._shutdown_complete is False
    assert application._shutdown_timer.isActive()

    application._shutdown_timer.stop()


def test_shutdown_completes_after_monitoring_worker_stops(qt_application):
    application = SystemMonitorApplication(argv=[])
    service = FakeService(alive=True)
    events = []
    application._coordinator = FakeCoordinator()
    application._services = dict(cpu=service)

    application._main_window = FakeLifecycleTarget()
    application._application = FakeLifecycleTarget()

    application._request_shutdown()
    assert application._shutdown_complete is False

    service.alive = False
    application._check_shutdown_completion()

    assert application._shutdown_complete is True
    assert application._main_window.calls == [1, 2]
    assert application._application.calls == [3]
    assert application._shutdown_timer.isActive() is False

class FakeLifecycleTarget:
    def __init__(self):
        self.calls = []

    def allow_close(self):
        self.calls.append(1)

    def close(self):
        self.calls.append(2)

    def quit(self):
        self.calls.append(3)

class FakeInformationWorker:
    def __init__(self, running=True):
        self.running = running
        self.wait_called = False
        self.delete_called = False

    def isRunning(self):
        return self.running

    def wait(self):
        self.wait_called = True
        return True

    def deleteLater(self):
        self.delete_called = True


def test_shutdown_waits_for_system_information_worker(qt_application):
    application = SystemMonitorApplication(argv=[])
    information_worker = FakeInformationWorker(running=True)
    events = []
    application._coordinator = FakeCoordinator()
    application._services = dict(cpu=FakeService(alive=False))
    application._system_information_worker = information_worker
    application._main_window = FakeLifecycleTarget()
    application._application = FakeLifecycleTarget()

    application._request_shutdown()

    assert application._shutdown_complete is False
    assert application._shutdown_timer.isActive()
    assert information_worker.delete_called is False

    application._shutdown_timer.stop()
