from system_monitor import __main__ as entrypoint


def test_main_runs_application_and_returns_exit_code(monkeypatch):
    calls = []

    class FakeApplication:
        def run(self):
            calls.append("run")
            return 7

    monkeypatch.setattr(
        entrypoint,
        "SystemMonitorApplication",
        FakeApplication,
    )

    assert entrypoint.main() == 7
    assert calls == ["run"]
