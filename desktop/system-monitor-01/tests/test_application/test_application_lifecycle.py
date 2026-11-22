from types import SimpleNamespace

from system_monitor.application.application import SystemMonitorApplication
from system_monitor.application import application as application_module


class FakeService:
    def __init__(self, alive=False, auto_cleanup=True):
        self.alive = alive
        self.cleanup_complete = not alive
        self.auto_cleanup = auto_cleanup
        self.stop_calls = 0

    def is_worker_thread_alive(self):
        return self.alive

    def is_cleanup_complete(self):
        return self.cleanup_complete

    def stop(self):
        self.stop_calls += 1
        if not self.alive and self.auto_cleanup:
            self.cleanup_complete = True


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


def test_shutdown_waits_until_service_cleanup_completes(qt_application):
    application = SystemMonitorApplication(argv=[])
    service = FakeService(alive=False, auto_cleanup=False)
    service.cleanup_complete = False
    application._coordinator = FakeCoordinator()
    application._services = dict(cpu=service)
    application._main_window = FakeLifecycleTarget()
    application._application = FakeLifecycleTarget()

    application._request_shutdown()

    assert service.stop_calls == 1
    assert application._shutdown_complete is False
    assert application._shutdown_timer.isActive() is True
    assert application._main_window.calls == []
    assert application._application.calls == []

    service.cleanup_complete = True
    application._check_shutdown_completion()

    assert application._shutdown_complete is True
    assert application._shutdown_timer.isActive() is False
    assert application._main_window.calls == [1, 2]
    assert application._application.calls == [3]


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



def _build_run_application(monkeypatch, *, accepted, error=None):
    application = SystemMonitorApplication(argv=[])
    calls = []
    logged_errors = []

    application._initialize = lambda: calls.append("initialize")

    application._main_window = SimpleNamespace(
        show=lambda: calls.append("show")
    )

    application._start_system_information_collection = (
        lambda: calls.append("system_information")
    )

    def start_coordinator():
        calls.append("coordinator_start")
        return SimpleNamespace(accepted=accepted, error=error)

    application._coordinator = SimpleNamespace(
        start=start_coordinator
    )

    application._application = SimpleNamespace(
        exec=lambda: calls.append("event_loop") or 7
    )

    monkeypatch.setattr(
        application_module.logger,
        "error",
        logged_errors.append,
    )

    return application, calls, logged_errors


def test_run_starts_coordinator_and_enters_event_loop(monkeypatch):
    application, calls, logged_errors = _build_run_application(
        monkeypatch,
        accepted=True,
    )

    assert application.run() == 7

    assert calls == [
        "initialize",
        "show",
        "system_information",
        "coordinator_start",
        "event_loop",
    ]
    assert logged_errors == []


def test_run_logs_rejected_coordinator_start_and_enters_event_loop(
    monkeypatch,
):
    application, calls, logged_errors = _build_run_application(
        monkeypatch,
        accepted=False,
        error="CPU service startup was rejected.",
    )

    assert application.run() == 7

    assert calls == [
        "initialize",
        "show",
        "system_information",
        "coordinator_start",
        "event_loop",
    ]
    assert logged_errors == ["CPU service startup was rejected."]


class FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, callback):
        self.connected.append(callback)


class FakeStatusLabel:
    def __init__(self):
        self.text = None

    def setText(self, value):
        self.text = value


class FakeInitializationCoordinator:
    def __init__(self):
        self.status_changed = FakeSignal()

    def get_status(self):
        return "RUNNING"


class FakeInitializationWindow:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.close_requested = FakeSignal()
        self.application_status = FakeStatusLabel()


def test_initialize_wires_diagnostic_aggregator_to_main_window(
    qt_application,
    monkeypatch,
):
    application = SystemMonitorApplication(argv=[])

    services = {
        "cpu": object(),
        "memory": object(),
        "disk": object(),
        "network": object(),
        "process": object(),
    }
    coordinator = FakeInitializationCoordinator()
    dependencies = {}

    def create_dependencies():
        application._services = services
        application._coordinator = coordinator

    class FakeDataController:
        def __init__(self, received_services, parent=None):
            dependencies["services"] = received_services
            dependencies["controller_parent"] = parent

    class FakeDiagnosticAggregator:
        def __init__(self, coordinator, data_controller):
            dependencies["aggregator_coordinator"] = coordinator
            dependencies["aggregator_controller"] = data_controller

    monkeypatch.setattr(
        application,
        "_create_dependencies",
        create_dependencies,
    )
    monkeypatch.setattr(
        application_module,
        "MonitoringDataController",
        FakeDataController,
    )
    monkeypatch.setattr(
        application_module,
        "DiagnosticAggregator",
        FakeDiagnosticAggregator,
    )
    monkeypatch.setattr(
        application_module,
        "MainWindow",
        FakeInitializationWindow,
    )

    application._initialize()

    assert dependencies["services"] is services
    assert dependencies["controller_parent"] is application
    assert dependencies["aggregator_coordinator"] is coordinator
    assert (
        dependencies["aggregator_controller"]
        is application._monitoring_data_controller
    )
    assert (
        application._main_window.kwargs["controller"]
        is application._monitoring_data_controller
    )
    assert (
        application._main_window.kwargs["diagnostic_aggregator"]
        is application._diagnostic_aggregator
    )
    assert len(coordinator.status_changed.connected) == 1
    assert len(application._main_window.close_requested.connected) == 1
