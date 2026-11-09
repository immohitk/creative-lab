from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from system_monitor.models.network_error import NetworkError
from system_monitor.models.network_measurement import NetworkMeasurement
from system_monitor.models.network_state import NetworkStateSnapshot
from system_monitor.models.network_operation_result import (
    NetworkStartResult,
    NetworkStopResult,
    NetworkConfigurationResult,
)

import pytest

from system_monitor.models.network_interface_measurement import (
    NetworkInterfaceMeasurement,
)
from system_monitor.models.network_counter_reset import NetworkCounterReset
from system_monitor.models.network_status import (
    NetworkWorkerState,
    NetworkMeasurementStatus,
    NetworkMeasurementFreshness,
)


def make_interface_measurement(**overrides):
    now = datetime.now(timezone.utc)

    values = {
        "interface_id": "Ethernet",
        "name": "Ethernet",
        "bytes_received": 10000,
        "bytes_sent": 5000,
        "packets_received": 100,
        "packets_sent": 80,
        "errors_in": 0,
        "errors_out": 0,
        "drops_in": 0,
        "drops_out": 0,
        "download_bytes_per_second": 1024.5,
        "upload_bytes_per_second": 512.25,
        "sampled_at": now,
    }
    values.update(overrides)

    return NetworkInterfaceMeasurement(**values)


def make_counter_reset(**overrides):
    now = datetime.now(timezone.utc)

    values = {
        "interface_id": "Ethernet",
        "occurred_at": now,
        "reset_counters": ("bytes_received",),
    }
    values.update(overrides)

    return NetworkCounterReset(**values)


def test_valid_interface_measurement_is_created():
    measurement = make_interface_measurement()

    assert measurement.interface_id == "Ethernet"
    assert measurement.name == "Ethernet"
    assert measurement.bytes_received == 10000
    assert measurement.bytes_sent == 5000
    assert measurement.download_bytes_per_second == 1024.5
    assert measurement.upload_bytes_per_second == 512.25


def test_interface_measurement_is_immutable():
    measurement = make_interface_measurement()

    with pytest.raises(FrozenInstanceError):
        measurement.bytes_received = 20000


def test_interface_identity_must_match_name():
    with pytest.raises(ValueError):
        make_interface_measurement(interface_id="ethernet")


@pytest.mark.parametrize(
    "field_name",
    ["bytes_received", "bytes_sent"],
)
@pytest.mark.parametrize(
    "value",
    [True, -1, 1.5, "100"],
)
def test_invalid_required_counters_are_rejected(field_name, value):
    with pytest.raises((TypeError, ValueError)):
        make_interface_measurement(**{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    [
        "packets_received",
        "packets_sent",
        "errors_in",
        "errors_out",
        "drops_in",
        "drops_out",
    ],
)
@pytest.mark.parametrize(
    "value",
    [True, -1, 1.5, "100"],
)
def test_invalid_optional_counters_are_rejected(field_name, value):
    with pytest.raises((TypeError, ValueError)):
        make_interface_measurement(**{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    ["bytes_received", "bytes_sent"],
)
def test_required_counters_cannot_be_none(field_name):
    with pytest.raises(TypeError):
        make_interface_measurement(**{field_name: None})


def test_optional_counters_accept_none():
    measurement = make_interface_measurement(
        packets_received=None,
        packets_sent=None,
        errors_in=None,
        errors_out=None,
        drops_in=None,
        drops_out=None,
    )

    assert measurement.packets_received is None
    assert measurement.drops_out is None


@pytest.mark.parametrize(
    "field_name",
    ["download_bytes_per_second", "upload_bytes_per_second"],
)
@pytest.mark.parametrize(
    "value",
    [True, -1, float("nan"), float("inf"), float("-inf"), "100"],
)
def test_invalid_network_rates_are_rejected(field_name, value):
    with pytest.raises((TypeError, ValueError)):
        make_interface_measurement(**{field_name: value})


def test_network_rates_are_not_rounded():
    measurement = make_interface_measurement(
        download_bytes_per_second=1024.123456789,
        upload_bytes_per_second=512.987654321,
    )

    assert measurement.download_bytes_per_second == 1024.123456789
    assert measurement.upload_bytes_per_second == 512.987654321


def test_network_rates_accept_none_for_baseline():
    measurement = make_interface_measurement(
        download_bytes_per_second=None,
        upload_bytes_per_second=None,
    )

    assert measurement.download_bytes_per_second is None
    assert measurement.upload_bytes_per_second is None


def test_sample_timestamp_must_be_utc_aware():
    with pytest.raises(ValueError):
        make_interface_measurement(sampled_at=datetime.now())


def test_valid_counter_reset_is_created():
    reset = make_counter_reset()

    assert reset.interface_id == "Ethernet"
    assert reset.reset_counters == ("bytes_received",)


def test_counter_reset_accepts_both_byte_counters():
    reset = make_counter_reset(
        reset_counters=["bytes_received", "bytes_sent"]
    )

    assert reset.reset_counters == ("bytes_received", "bytes_sent")


def test_counter_reset_normalizes_list_to_tuple():
    counters = ["bytes_received"]
    reset = make_counter_reset(reset_counters=counters)

    counters.append("bytes_sent")

    assert reset.reset_counters == ("bytes_received",)
    assert isinstance(reset.reset_counters, tuple)


@pytest.mark.parametrize(
    "counters",
    [
        (),
        ("packets_received",),
        ("bytes_received", "bytes_received"),
        ("bytes_received", "unknown_counter"),
    ],
)
def test_invalid_reset_counter_collections_are_rejected(counters):
    with pytest.raises((TypeError, ValueError)):
        make_counter_reset(reset_counters=counters)


def test_counter_reset_timestamp_must_be_utc_aware():
    with pytest.raises(ValueError):
        make_counter_reset(occurred_at=datetime.now())


def test_status_enums_have_expected_values():
    assert NetworkWorkerState.STOPPED.value == "STOPPED"
    assert NetworkWorkerState.STARTING.value == "STARTING"
    assert NetworkWorkerState.RUNNING.value == "RUNNING"
    assert NetworkWorkerState.STOPPING.value == "STOPPING"
    assert NetworkWorkerState.FAILED.value == "FAILED"

    assert NetworkMeasurementStatus.INITIALIZING.value == "INITIALIZING"
    assert NetworkMeasurementStatus.AVAILABLE.value == "AVAILABLE"
    assert NetworkMeasurementStatus.PARTIAL.value == "PARTIAL"
    assert NetworkMeasurementStatus.UNAVAILABLE.value == "UNAVAILABLE"

    assert NetworkMeasurementFreshness.NO_DATA.value == "NO_DATA"
    assert NetworkMeasurementFreshness.FRESH.value == "FRESH"
    assert NetworkMeasurementFreshness.STALE.value == "STALE"


def make_network_error(**overrides):
    now = datetime.now(timezone.utc)

    values = {
        "error_code": "INTERFACE_COLLECTION_FAILED",
        "message": "Unable to collect interface counters.",
        "occurred_at": now,
        "consecutive_failures": 1,
        "interface_id": "Ethernet",
    }
    values.update(overrides)

    return NetworkError(**values)


def make_network_measurement(**overrides):
    now = datetime.now(timezone.utc)

    values = {
        "interfaces": (make_interface_measurement(),),
        "interface_errors": (),
        "counter_resets": (),
        "baseline_only_interface_ids": (),
        "sampling_interval": 1.0,
        "started_at": now,
        "completed_at": now + timedelta(milliseconds=100),
    }
    values.update(overrides)

    return NetworkMeasurement(**values)


def test_valid_network_error_is_created():
    error = make_network_error()

    assert error.error_code == "INTERFACE_COLLECTION_FAILED"
    assert error.interface_id == "Ethernet"
    assert error.consecutive_failures == 1


def test_network_error_allows_collection_level_failure():
    error = make_network_error(interface_id=None)

    assert error.interface_id is None


def test_network_error_rejects_invalid_failure_count():
    with pytest.raises((TypeError, ValueError)):
        make_network_error(consecutive_failures=True)

    with pytest.raises(ValueError):
        make_network_error(consecutive_failures=-1)


def test_network_error_requires_utc_timestamp():
    with pytest.raises(ValueError):
        make_network_error(occurred_at=datetime.now())


def test_network_error_is_immutable():
    error = make_network_error()

    with pytest.raises(FrozenInstanceError):
        error.message = "Changed message."


def test_valid_network_measurement_is_created():
    measurement = make_network_measurement()

    assert len(measurement.interfaces) == 1
    assert measurement.is_fully_successful
    assert not measurement.is_partial
    assert not measurement.is_empty
    assert not measurement.is_unavailable


def test_network_measurement_normalizes_collections_to_tuples():
    interfaces = [make_interface_measurement()]

    measurement = make_network_measurement(interfaces=interfaces)

    interfaces.clear()

    assert len(measurement.interfaces) == 1
    assert isinstance(measurement.interfaces, tuple)


def test_empty_interface_inventory_is_fully_successful():
    measurement = make_network_measurement(interfaces=())

    assert measurement.is_empty
    assert measurement.is_fully_successful
    assert not measurement.is_unavailable


def test_unavailable_measurement_has_errors_but_no_interfaces():
    error = make_network_error()

    measurement = make_network_measurement(
        interfaces=(),
        interface_errors=(error,),
    )

    assert measurement.is_unavailable
    assert not measurement.is_fully_successful
    assert not measurement.is_partial


def test_partial_measurement_has_interfaces_and_errors():
    error = make_network_error(interface_id="Wi-Fi")

    measurement = make_network_measurement(
        interfaces=(make_interface_measurement(),),
        interface_errors=(error,),
    )

    assert measurement.is_partial
    assert not measurement.is_fully_successful
    assert not measurement.is_empty


def test_duplicate_interface_identities_are_rejected():
    first = make_interface_measurement()
    second = make_interface_measurement(
        bytes_received=20000,
        bytes_sent=10000,
    )

    with pytest.raises(ValueError):
        make_network_measurement(interfaces=(first, second))


def test_interface_cannot_have_measurement_and_error():
    error = make_network_error(interface_id="Ethernet")

    with pytest.raises(ValueError):
        make_network_measurement(interface_errors=(error,))


def test_duplicate_interface_errors_are_rejected():
    first = make_network_error()
    second = make_network_error(message="Another failure.")

    with pytest.raises(ValueError):
        make_network_measurement(
            interfaces=(),
            interface_errors=(first, second),
        )


def test_baseline_only_measurement_is_valid():
    interface = make_interface_measurement(
        download_bytes_per_second=None,
        upload_bytes_per_second=None,
    )

    measurement = make_network_measurement(
        interfaces=(interface,),
        baseline_only_interface_ids=("Ethernet",),
    )

    assert measurement.has_baseline_only_interfaces
    assert measurement.baseline_only_interface_ids == ("Ethernet",)
    assert measurement.is_fully_successful


def test_baseline_only_identity_must_refer_to_successful_interface():
    with pytest.raises(ValueError):
        make_network_measurement(
            baseline_only_interface_ids=("Wi-Fi",),
        )


def test_baseline_only_interface_must_have_both_rates_none():
    interface = make_interface_measurement(
        download_bytes_per_second=None,
        upload_bytes_per_second=100.0,
    )

    with pytest.raises(ValueError):
        make_network_measurement(
            interfaces=(interface,),
            baseline_only_interface_ids=("Ethernet",),
        )


def test_baseline_only_identities_must_be_unique():
    interface = make_interface_measurement(
        download_bytes_per_second=None,
        upload_bytes_per_second=None,
    )

    with pytest.raises(ValueError):
        make_network_measurement(
            interfaces=(interface,),
            baseline_only_interface_ids=("Ethernet", "Ethernet"),
        )


def test_counter_reset_must_reference_successful_interface():
    reset = make_counter_reset(interface_id="Wi-Fi")

    with pytest.raises(ValueError):
        make_network_measurement(counter_resets=(reset,))


def test_counter_reset_does_not_make_measurement_partial():
    reset = make_counter_reset(
        reset_counters=("bytes_received", "bytes_sent"),
    )

    measurement = make_network_measurement(counter_resets=(reset,))

    assert measurement.is_fully_successful
    assert not measurement.is_partial


def test_invalid_network_measurement_interval_is_rejected():
    with pytest.raises((TypeError, ValueError)):
        make_network_measurement(sampling_interval=True)

    with pytest.raises(ValueError):
        make_network_measurement(sampling_interval=60.1)


def test_completion_cannot_precede_start():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValueError):
        make_network_measurement(
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )


def test_network_measurement_is_immutable():
    measurement = make_network_measurement()

    with pytest.raises(FrozenInstanceError):
        measurement.sampling_interval = 2.0


def test_valid_network_start_result():
    result = NetworkStartResult(
        accepted=True,
        worker_state=NetworkWorkerState.STARTING,
    )

    assert result.accepted is True
    assert result.worker_state == NetworkWorkerState.STARTING
    assert result.error is None


def test_network_start_result_rejects_invalid_values():
    with pytest.raises(TypeError):
        NetworkStartResult(
            accepted=1,
            worker_state=NetworkWorkerState.STARTING,
        )

    with pytest.raises(TypeError):
        NetworkStartResult(
            accepted=True,
            worker_state="STARTING",
        )

    with pytest.raises(TypeError):
        NetworkStartResult(
            accepted=True,
            worker_state=NetworkWorkerState.STARTING,
            error="failure",
        )


def test_valid_network_stop_result():
    result = NetworkStopResult(
        success=True,
        worker_state=NetworkWorkerState.STOPPED,
    )

    assert result.success is True
    assert result.worker_state == NetworkWorkerState.STOPPED
    assert result.error is None


def test_network_stop_result_rejects_invalid_values():
    with pytest.raises(TypeError):
        NetworkStopResult(
            success=1,
            worker_state=NetworkWorkerState.STOPPED,
        )

    with pytest.raises(TypeError):
        NetworkStopResult(
            success=True,
            worker_state="STOPPED",
        )


def test_valid_network_configuration_result():
    result = NetworkConfigurationResult(
        accepted=True,
        sampling_interval=2,
        worker_state=NetworkWorkerState.RUNNING,
    )

    assert result.accepted is True
    assert result.sampling_interval == 2.0
    assert result.worker_state == NetworkWorkerState.RUNNING


def test_network_configuration_normalizes_interval_to_float():
    result = NetworkConfigurationResult(
        accepted=True,
        sampling_interval=1,
        worker_state=NetworkWorkerState.RUNNING,
    )

    assert result.sampling_interval == 1.0
    assert isinstance(result.sampling_interval, float)


@pytest.mark.parametrize(
    "interval",
    [True, False, 0, -1, 0.49, 60.01, float("nan"), float("inf"), float("-inf")],
)
def test_network_configuration_rejects_invalid_intervals(interval):
    with pytest.raises((TypeError, ValueError)):
        NetworkConfigurationResult(
            accepted=True,
            sampling_interval=interval,
            worker_state=NetworkWorkerState.RUNNING,
        )


def test_network_configuration_accepts_interval_boundaries():
    minimum = NetworkConfigurationResult(
        accepted=True,
        sampling_interval=0.5,
        worker_state=NetworkWorkerState.RUNNING,
    )

    maximum = NetworkConfigurationResult(
        accepted=True,
        sampling_interval=60.0,
        worker_state=NetworkWorkerState.RUNNING,
    )

    assert minimum.sampling_interval == 0.5
    assert maximum.sampling_interval == 60.0


def test_network_operation_results_are_immutable():
    result = NetworkStartResult(
        accepted=True,
        worker_state=NetworkWorkerState.STARTING,
    )

    with pytest.raises(FrozenInstanceError):
        result.accepted = False


def make_network_state(**overrides):
    values = {
        "worker_state": NetworkWorkerState.STOPPED,
        "measurement_status": NetworkMeasurementStatus.INITIALIZING,
        "latest_measurement": None,
        "last_successful_measurement": None,
        "last_successful_monotonic": None,
        "measurement_error": None,
        "worker_error": None,
        "consecutive_failures": 0,
        "sampling_interval": 1.0,
        "revision": 0,
    }
    values.update(overrides)

    return NetworkStateSnapshot(**values)


def test_initial_network_state_has_no_data():
    state = make_network_state()

    assert state.freshness == NetworkMeasurementFreshness.NO_DATA
    assert state.latest_measurement is None
    assert state.last_successful_measurement is None


def test_initializing_state_allows_baseline_only_measurement():
    interface = make_interface_measurement(
        download_bytes_per_second=None,
        upload_bytes_per_second=None,
    )
    measurement = make_network_measurement(
        interfaces=(interface,),
        baseline_only_interface_ids=("Ethernet",),
    )

    state = make_network_state(
        latest_measurement=measurement,
        last_successful_measurement=measurement,
        last_successful_monotonic=100.0,
    )

    assert state.measurement_status == NetworkMeasurementStatus.INITIALIZING
    assert state.latest_measurement is measurement
    assert state.last_successful_measurement is measurement
    assert state.freshness == NetworkMeasurementFreshness.STALE


def test_initializing_state_rejects_non_baseline_measurement():
    measurement = make_network_measurement()

    with pytest.raises(ValueError):
        make_network_state(latest_measurement=measurement)


def test_initializing_state_rejects_partial_measurement():
    measurement = make_network_measurement(
        interface_errors=(make_network_error(interface_id="Wi-Fi"),),
    )

    with pytest.raises(ValueError):
        make_network_state(latest_measurement=measurement)


def test_available_state_requires_fully_successful_measurement():
    measurement = make_network_measurement()

    state = make_network_state(
        measurement_status=NetworkMeasurementStatus.AVAILABLE,
        latest_measurement=measurement,
        last_successful_measurement=measurement,
        last_successful_monotonic=100.0,
    )

    assert state.freshness == NetworkMeasurementFreshness.FRESH


def test_available_state_rejects_missing_measurement():
    with pytest.raises(ValueError):
        make_network_state(
            measurement_status=NetworkMeasurementStatus.AVAILABLE,
        )


def test_partial_state_requires_partial_measurement():
    measurement = make_network_measurement(
        interface_errors=(make_network_error(interface_id="Wi-Fi"),),
    )

    state = make_network_state(
        measurement_status=NetworkMeasurementStatus.PARTIAL,
        latest_measurement=measurement,
    )

    assert state.freshness == NetworkMeasurementFreshness.NO_DATA


def test_partial_state_rejects_fully_successful_measurement():
    measurement = make_network_measurement()

    with pytest.raises(ValueError):
        make_network_state(
            measurement_status=NetworkMeasurementStatus.PARTIAL,
            latest_measurement=measurement,
        )


def test_unavailable_state_accepts_unavailable_measurement():
    measurement = make_network_measurement(
        interfaces=(),
        interface_errors=(make_network_error(interface_id=None),),
    )

    state = make_network_state(
        measurement_status=NetworkMeasurementStatus.UNAVAILABLE,
        latest_measurement=measurement,
    )

    assert state.measurement_status == NetworkMeasurementStatus.UNAVAILABLE


def test_unavailable_state_rejects_successful_measurement():
    measurement = make_network_measurement()

    with pytest.raises(ValueError):
        make_network_state(
            measurement_status=NetworkMeasurementStatus.UNAVAILABLE,
            latest_measurement=measurement,
        )


def test_last_successful_measurement_requires_monotonic_reference():
    measurement = make_network_measurement()

    with pytest.raises(ValueError):
        make_network_state(
            last_successful_measurement=measurement,
        )

    with pytest.raises(ValueError):
        make_network_state(
            last_successful_monotonic=100.0,
        )


def test_last_successful_measurement_must_be_fully_successful():
    measurement = make_network_measurement(
        interface_errors=(make_network_error(interface_id="Wi-Fi"),),
    )

    with pytest.raises(ValueError):
        make_network_state(
            last_successful_measurement=measurement,
            last_successful_monotonic=100.0,
        )


def test_partial_state_preserves_stale_successful_data():
    successful = make_network_measurement()
    partial = make_network_measurement(
        interface_errors=(make_network_error(interface_id="Wi-Fi"),),
    )

    state = make_network_state(
        measurement_status=NetworkMeasurementStatus.PARTIAL,
        latest_measurement=partial,
        last_successful_measurement=successful,
        last_successful_monotonic=100.0,
    )

    assert state.latest_measurement is partial
    assert state.last_successful_measurement is successful
    assert state.freshness == NetworkMeasurementFreshness.STALE


def test_empty_successful_measurement_is_available_and_fresh():
    measurement = make_network_measurement(interfaces=())

    state = make_network_state(
        measurement_status=NetworkMeasurementStatus.AVAILABLE,
        latest_measurement=measurement,
        last_successful_measurement=measurement,
        last_successful_monotonic=100.0,
    )

    assert state.freshness == NetworkMeasurementFreshness.FRESH


def test_last_successful_age_uses_monotonic_reference():
    state = make_network_state(
        last_successful_measurement=make_network_measurement(),
        last_successful_monotonic=100.0,
    )

    assert state.last_successful_age(105.0) == 5.0
    assert state.last_successful_age(99.0) == 0.0


@pytest.mark.parametrize(
    "value",
    [True, -1, 1.5],
)
def test_invalid_consecutive_failures_are_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        make_network_state(consecutive_failures=value)


@pytest.mark.parametrize(
    "value",
    [True, -1, 1.5],
)
def test_invalid_revision_is_rejected(value):
    with pytest.raises((TypeError, ValueError)):
        make_network_state(revision=value)


def test_network_state_snapshot_is_immutable():
    state = make_network_state()

    with pytest.raises(FrozenInstanceError):
        state.revision = 1
