from dataclasses import FrozenInstanceError

import pytest

from system_monitor.models import (
    CoordinatorStatus,
    CoordinatorSnapshot,
    CoordinatorStartResult,
    CoordinatorStopResult,
    CoordinatorConfigurationResult,
)


def test_coordinator_status_values():
    assert CoordinatorStatus.STOPPED.value == "STOPPED"
    assert CoordinatorStatus.STARTING.value == "STARTING"
    assert CoordinatorStatus.RUNNING.value == "RUNNING"
    assert CoordinatorStatus.DEGRADED.value == "DEGRADED"
    assert CoordinatorStatus.STOPPING.value == "STOPPING"
    assert CoordinatorStatus.FAILED.value == "FAILED"


def test_coordinator_snapshot_is_immutable():
    snapshot = CoordinatorSnapshot(
        status=CoordinatorStatus.STOPPED,
        service_states={"cpu": "STOPPED"},
        active_service_count=0,
        failed_service_count=0,
        last_error=None,
        revision=0,
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.revision = 1


def test_coordinator_snapshot_copies_and_freezes_service_states():
    states = {"cpu": "RUNNING"}

    snapshot = CoordinatorSnapshot(
        status=CoordinatorStatus.RUNNING,
        service_states=states,
        active_service_count=1,
        failed_service_count=0,
        last_error=None,
        revision=1,
    )

    states["cpu"] = "FAILED"

    assert snapshot.service_states["cpu"] == "RUNNING"

    with pytest.raises(TypeError):
        snapshot.service_states["cpu"] = "FAILED"


@pytest.mark.parametrize(
    "active, failed",
    [
        (-1, 0),
        (0, -1),
        (True, 0),
        (0, True),
        (2, 0),
        (0, 2),
        (1, 1),
    ],
)
def test_coordinator_snapshot_rejects_invalid_service_counts(active, failed):
    with pytest.raises(ValueError):
        CoordinatorSnapshot(
            status=CoordinatorStatus.STOPPED,
            service_states={"cpu": "STOPPED"},
            active_service_count=active,
            failed_service_count=failed,
            last_error=None,
            revision=0,
        )


def test_coordinator_snapshot_rejects_invalid_revision():
    with pytest.raises(ValueError):
        CoordinatorSnapshot(
            status=CoordinatorStatus.STOPPED,
            service_states={},
            active_service_count=0,
            failed_service_count=0,
            last_error=None,
            revision=-1,
        )


def test_coordinator_start_result():
    result = CoordinatorStartResult(
        accepted=True,
        status=CoordinatorStatus.STARTING,
    )

    assert result.accepted is True
    assert result.status == CoordinatorStatus.STARTING


def test_coordinator_stop_result():
    result = CoordinatorStopResult(
        success=True,
        status=CoordinatorStatus.STOPPED,
    )

    assert result.success is True
    assert result.status == CoordinatorStatus.STOPPED


def test_coordinator_configuration_result():
    result = CoordinatorConfigurationResult(
        accepted=True,
        sampling_interval=2.0,
        status=CoordinatorStatus.RUNNING,
    )

    assert result.accepted is True
    assert result.sampling_interval == 2.0


@pytest.mark.parametrize("interval", [0.1, 60.1, True, float("inf")])
def test_coordinator_configuration_rejects_invalid_interval(interval):
    with pytest.raises((TypeError, ValueError)):
        CoordinatorConfigurationResult(
            accepted=False,
            sampling_interval=interval,
            status=CoordinatorStatus.STOPPED,
        )
