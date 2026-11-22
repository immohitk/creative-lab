from dataclasses import FrozenInstanceError

import pytest

from system_monitor.models import (
    DiagnosticSeverity,
    DiagnosticSnapshot,
    ServiceDiagnostic,
)


def make_service_diagnostic(
    name="cpu",
    severity=DiagnosticSeverity.HEALTHY,
):
    return ServiceDiagnostic(
        service_name=name,
        worker_state="RUNNING",
        measurement_status="AVAILABLE",
        freshness="FRESH",
        severity=severity,
        last_updated=None,
        error=None,
        consecutive_failures=0,
        sampling_interval=1.0,
        revision=1,
    )


def test_service_diagnostic_is_immutable():
    diagnostic = make_service_diagnostic()

    with pytest.raises(FrozenInstanceError):
        diagnostic.revision = 2


def test_service_diagnostic_rejects_invalid_severity():
    with pytest.raises(TypeError):
        make_service_diagnostic().__class__(
            service_name="cpu",
            worker_state="RUNNING",
            measurement_status="AVAILABLE",
            freshness="FRESH",
            severity="HEALTHY",
            last_updated=None,
            error=None,
            consecutive_failures=0,
            sampling_interval=1.0,
            revision=1,
        )


@pytest.mark.parametrize("failures", [-1, True, 1.5])
def test_service_diagnostic_rejects_invalid_failure_count(failures):
    with pytest.raises(ValueError):
        ServiceDiagnostic(
            service_name="cpu",
            worker_state="RUNNING",
            measurement_status="AVAILABLE",
            freshness="FRESH",
            severity=DiagnosticSeverity.HEALTHY,
            last_updated=None,
            error=None,
            consecutive_failures=failures,
            sampling_interval=1.0,
            revision=1,
        )


@pytest.mark.parametrize("interval", [0.1, 60.1, True])
def test_service_diagnostic_rejects_invalid_sampling_interval(interval):
    with pytest.raises((TypeError, ValueError)):
        ServiceDiagnostic(
            service_name="cpu",
            worker_state="RUNNING",
            measurement_status="AVAILABLE",
            freshness="FRESH",
            severity=DiagnosticSeverity.HEALTHY,
            last_updated=None,
            error=None,
            consecutive_failures=0,
            sampling_interval=interval,
            revision=1,
        )


def test_diagnostic_snapshot_is_immutable():
    services = {"cpu": make_service_diagnostic()}

    snapshot = DiagnosticSnapshot(
        coordinator_status="RUNNING",
        services=services,
        coordinator_error=None,
        coordinator_revision=1,
    )

    services.clear()

    assert "cpu" in snapshot.services

    with pytest.raises(TypeError):
        snapshot.services["memory"] = make_service_diagnostic("memory")

    with pytest.raises(FrozenInstanceError):
        snapshot.coordinator_revision = 2


def test_diagnostic_snapshot_counts_severities():
    snapshot = DiagnosticSnapshot(
        coordinator_status="DEGRADED",
        services={
            "cpu": make_service_diagnostic(
                "cpu", DiagnosticSeverity.HEALTHY
            ),
            "memory": make_service_diagnostic(
                "memory", DiagnosticSeverity.WARNING
            ),
            "disk": make_service_diagnostic(
                "disk", DiagnosticSeverity.ERROR
            ),
            "network": make_service_diagnostic(
                "network", DiagnosticSeverity.UNKNOWN
            ),
        },
        coordinator_error=None,
        coordinator_revision=5,
    )

    assert snapshot.healthy_count == 1
    assert snapshot.warning_count == 1
    assert snapshot.error_count == 1
    assert snapshot.unknown_count == 1
    assert snapshot.severity == DiagnosticSeverity.ERROR


def test_diagnostic_snapshot_uses_highest_severity():
    snapshot = DiagnosticSnapshot(
        coordinator_status="RUNNING",
        services={
            "cpu": make_service_diagnostic(
                "cpu", DiagnosticSeverity.HEALTHY
            ),
            "memory": make_service_diagnostic(
                "memory", DiagnosticSeverity.WARNING
            ),
        },
        coordinator_error=None,
        coordinator_revision=1,
    )

    assert snapshot.severity == DiagnosticSeverity.WARNING


def test_empty_diagnostic_snapshot_is_unknown():
    snapshot = DiagnosticSnapshot(
        coordinator_status="STOPPED",
        services={},
        coordinator_error=None,
        coordinator_revision=0,
    )

    assert snapshot.severity == DiagnosticSeverity.UNKNOWN
    assert snapshot.unknown_count == 0


def test_diagnostic_snapshot_rejects_mismatched_service_names():
    with pytest.raises(ValueError):
        DiagnosticSnapshot(
            coordinator_status="RUNNING",
            services={"memory": make_service_diagnostic("cpu")},
            coordinator_error=None,
            coordinator_revision=1,
        )