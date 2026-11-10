from datetime import timezone
from types import SimpleNamespace

import threading
import time
import pytest

from collections.abc import Mapping

from system_monitor.workers.network_monitoring_worker import (
    NetworkMonitoringWorker,
    NetworkWorkerError,
)


def make_worker():
    measurements = []
    measurement_failures = []
    worker_failures = []

    worker = NetworkMonitoringWorker(
        sampling_interval=1.0,
        on_measurement=measurements.append,
        on_measurement_failure=lambda code, message: (
            measurement_failures.append((code, message))
        ),
        on_worker_failure=lambda: worker_failures.append(True),
    )

    return worker, measurements, measurement_failures, worker_failures


def make_counters(
    bytes_recv=1000,
    bytes_sent=2000,
    packets_recv=10,
    packets_sent=20,
    errin=0,
    errout=0,
    dropin=0,
    dropout=0,
):
    return SimpleNamespace(
        bytes_recv=bytes_recv,
        bytes_sent=bytes_sent,
        packets_recv=packets_recv,
        packets_sent=packets_sent,
        errin=errin,
        errout=errout,
        dropin=dropin,
        dropout=dropout,
    )


def patch_provider(monkeypatch, provider):
    monkeypatch.setattr(
        "system_monitor.workers.network_monitoring_worker.psutil.net_io_counters",
        provider,
    )


def patch_monotonic(monkeypatch, values):
    iterator = iter(values)

    monkeypatch.setattr(
        "system_monitor.workers.network_monitoring_worker.time.monotonic",
        lambda: next(iterator),
    )


def test_first_sample_establishes_baseline(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_provider(
        monkeypatch,
        lambda pernic=True: {
            "Ethernet": make_counters(),
        },
    )
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert len(measurement.interfaces) == 1

    interface = measurement.interfaces[0]

    assert interface.interface_id == "Ethernet"
    assert interface.name == "Ethernet"
    assert interface.download_bytes_per_second is None
    assert interface.upload_bytes_per_second is None

    assert measurement.baseline_only_interface_ids == ("Ethernet",)
    assert measurement.is_fully_successful
    assert not measurement.is_partial


def test_second_sample_calculates_actual_traffic_rates(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            {"Ethernet": make_counters(1600, 2400)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 12.0])

    worker._collect_measurement(1.0)
    measurement = worker._collect_measurement(1.0)

    interface = measurement.interfaces[0]

    assert interface.download_bytes_per_second == 300.0
    assert interface.upload_bytes_per_second == 200.0

    assert measurement.baseline_only_interface_ids == ()


def test_unchanged_counters_produce_zero_rates(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            {"Ethernet": make_counters(1000, 2000)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0])

    worker._collect_measurement(1.0)
    measurement = worker._collect_measurement(1.0)

    interface = measurement.interfaces[0]

    assert interface.download_bytes_per_second == 0.0
    assert interface.upload_bytes_per_second == 0.0


def test_byte_counter_reset_invalidates_both_rates_and_rebaselines(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            {"Ethernet": make_counters(500, 2500)},
            {"Ethernet": make_counters(700, 2700)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0, 12.0])

    worker._collect_measurement(1.0)
    reset_measurement = worker._collect_measurement(1.0)
    recovered_measurement = worker._collect_measurement(1.0)

    reset_interface = reset_measurement.interfaces[0]

    assert reset_interface.download_bytes_per_second is None
    assert reset_interface.upload_bytes_per_second is None

    assert len(reset_measurement.counter_resets) == 1
    assert reset_measurement.counter_resets[0].interface_id == "Ethernet"
    assert reset_measurement.counter_resets[0].reset_counters == (
        "bytes_received",
    )

    recovered_interface = recovered_measurement.interfaces[0]

    assert recovered_interface.download_bytes_per_second == 200.0
    assert recovered_interface.upload_bytes_per_second == 200.0


def test_both_byte_counter_resets_are_reported(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            {"Ethernet": make_counters(500, 1000)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0])

    worker._collect_measurement(1.0)
    measurement = worker._collect_measurement(1.0)

    assert measurement.counter_resets[0].reset_counters == (
        "bytes_received",
        "bytes_sent",
    )


def test_auxiliary_counter_decrease_does_not_invalidate_byte_rates(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {
                "Ethernet": make_counters(
                    1000, 2000, packets_recv=100, errin=5
                )
            },
            {
                "Ethernet": make_counters(
                    1500, 2500, packets_recv=10, errin=1
                )
            },
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0])

    worker._collect_measurement(1.0)
    measurement = worker._collect_measurement(1.0)

    interface = measurement.interfaces[0]

    assert interface.download_bytes_per_second == 500.0
    assert interface.upload_bytes_per_second == 500.0
    assert interface.packets_received == 10
    assert interface.errors_in == 1
    assert measurement.counter_resets == ()


def test_empty_inventory_is_a_successful_measurement(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_provider(monkeypatch, lambda pernic=True: {})
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.interfaces == ()
    assert measurement.interface_errors == ()
    assert measurement.is_empty
    assert measurement.is_fully_successful
    assert not measurement.is_unavailable


def test_disappeared_interface_baseline_is_removed(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters()},
            {},
            {"Ethernet": make_counters(5000, 6000)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0, 12.0])

    worker._collect_measurement(1.0)
    empty_measurement = worker._collect_measurement(1.0)
    reappeared_measurement = worker._collect_measurement(1.0)

    assert empty_measurement.is_empty

    interface = reappeared_measurement.interfaces[0]

    assert interface.download_bytes_per_second is None
    assert interface.upload_bytes_per_second is None
    assert reappeared_measurement.baseline_only_interface_ids == (
        "Ethernet",
    )


def test_invalid_required_counter_creates_interface_error(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_provider(
        monkeypatch,
        lambda pernic=True: {
            "Ethernet": make_counters(bytes_recv=-1),
        },
    )
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.interfaces == ()
    assert len(measurement.interface_errors) == 1
    assert measurement.interface_errors[0].interface_id == "Ethernet"
    assert measurement.interface_errors[0].error_code == (
        "NETWORK_INVALID_COUNTERS"
    )
    assert measurement.is_unavailable


def test_invalid_optional_counter_creates_interface_error(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_provider(
        monkeypatch,
        lambda pernic=True: {
            "Ethernet": make_counters(packets_recv=-1),
        },
    )
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.interfaces == ()
    assert len(measurement.interface_errors) == 1
    assert measurement.interface_errors[0].error_code == (
        "NETWORK_INVALID_COUNTERS"
    )


def test_missing_optional_counters_are_supported(monkeypatch):
    worker, _, _, _ = make_worker()

    counters = SimpleNamespace(
        bytes_recv=1000,
        bytes_sent=2000,
    )

    patch_provider(
        monkeypatch,
        lambda pernic=True: {"Ethernet": counters},
    )
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    interface = measurement.interfaces[0]

    assert interface.packets_received is None
    assert interface.packets_sent is None
    assert interface.errors_in is None
    assert interface.errors_out is None
    assert interface.drops_in is None
    assert interface.drops_out is None


def test_collection_level_provider_failure_raises_worker_error(monkeypatch):
    worker, _, _, _ = make_worker()

    def failing_provider(pernic=True):
        raise RuntimeError("provider failure")

    patch_provider(monkeypatch, failing_provider)

    with pytest.raises(NetworkWorkerError) as exc_info:
        worker._collect_measurement(1.0)

    assert exc_info.value.error_code == "NETWORK_PROVIDER_FAILED"


def test_invalid_provider_result_raises_worker_error(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_provider(monkeypatch, lambda pernic=True: None)

    with pytest.raises(NetworkWorkerError) as exc_info:
        worker._collect_measurement(1.0)

    assert exc_info.value.error_code == "NETWORK_PROVIDER_INVALID"


def test_interface_names_preserve_original_case(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_provider(
        monkeypatch,
        lambda pernic=True: {
            "Wi-Fi": make_counters(),
        },
    )
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.interfaces[0].interface_id == "Wi-Fi"
    assert measurement.interfaces[0].name == "Wi-Fi"


def test_measurement_timestamps_are_utc_aware(monkeypatch):
    worker, _, _, _ = make_worker()

    patch_provider(monkeypatch, lambda pernic=True: {})
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.started_at.tzinfo is not None
    assert measurement.completed_at.tzinfo is not None
    assert measurement.started_at.utcoffset() == timezone.utc.utcoffset(
        measurement.started_at
    )
    assert measurement.completed_at.utcoffset() == timezone.utc.utcoffset(
        measurement.completed_at
    )


@pytest.mark.parametrize(
    "interval",
    [
        0,
        0.49,
        60.01,
        float("inf"),
        float("-inf"),
        float("nan"),
        True,
        "1",
    ],
)
def test_invalid_sampling_interval_is_rejected(interval):
    with pytest.raises((TypeError, ValueError)):
        NetworkMonitoringWorker(
            sampling_interval=interval,
            on_measurement=lambda measurement: None,
            on_measurement_failure=lambda code, message: None,
            on_worker_failure=lambda: None,
        )


@pytest.mark.parametrize("interval", [0.5, 1.0, 10.0, 60.0])
def test_valid_sampling_interval_is_accepted(interval):
    worker, _, _, _ = make_worker()

    worker.set_sampling_interval(interval)

    assert worker.sampling_interval == interval


def test_startup_callback_is_executed():
    started = []
    worker = NetworkMonitoringWorker(
        sampling_interval=1.0,
        on_measurement=lambda measurement: None,
        on_measurement_failure=lambda code, message: None,
        on_worker_failure=lambda: None,
        on_started=lambda: started.append(True),
    )

    worker.stop()
    worker.run()

    assert started == []


def test_worker_stops_without_collecting_after_stop(monkeypatch):
    worker, measurements, _, _ = make_worker()

    def unexpected_collection():
        pytest.fail("Collection should not occur after stop.")

    monkeypatch.setattr(worker, "_collect_measurement", unexpected_collection)

    worker.stop()
    worker.run()

    assert measurements == []


def test_wait_is_interrupted_by_stop_event():
    worker, _, _, _ = make_worker()

    result = []

    thread = threading.Thread(
        target=lambda: result.append(
            worker._wait_for_next_window(30.0)
        )
    )
    thread.start()

    time.sleep(0.05)
    worker.stop()
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert result == [worker._WaitResult.STOP] if hasattr(worker, "_WaitResult") else result[0].value == "stop"


def test_wait_is_interrupted_by_reconfiguration():
    worker, _, _, _ = make_worker()

    result = []

    thread = threading.Thread(
        target=lambda: result.append(
            worker._wait_for_next_window(30.0)
        )
    )
    thread.start()

    time.sleep(0.05)
    worker.set_sampling_interval(2.0)
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert result[0].value == "reconfigure"
    assert worker.sampling_interval == 2.0


def test_measurement_callback_exception_does_not_escape():
    worker, _, _, _ = make_worker()

    def failing_callback(measurement):
        raise RuntimeError("callback failure")

    worker._on_measurement = failing_callback

    measurement = None

    worker._deliver_measurement(measurement)


def test_measurement_failure_callback_exception_does_not_escape():
    worker, _, _, _ = make_worker()

    def failing_callback(code, message):
        raise RuntimeError("callback failure")

    worker._on_measurement_failure = failing_callback

    worker._report_measurement_failure(
        "NETWORK_TEST_ERROR",
        "Test failure.",
    )


def test_worker_failure_callback_exception_does_not_escape():
    worker, _, _, _ = make_worker()

    def failing_callback():
        raise RuntimeError("callback failure")

    worker._on_worker_failure = failing_callback

    worker._safe_callback(worker._on_worker_failure)


def test_collection_failure_preserves_existing_baseline(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            RuntimeError("provider failure"),
            {"Ethernet": make_counters(1600, 2400)},
        ]
    )

    def provider(pernic=True):
        sample = next(samples)
        if isinstance(sample, Exception):
            raise sample
        return sample

    patch_provider(monkeypatch, provider)
    patch_monotonic(monkeypatch, [10.0, 12.0])

    worker._collect_measurement(1.0)

    with pytest.raises(NetworkWorkerError):
        worker._collect_measurement(1.0)

    measurement = worker._collect_measurement(1.0)

    interface = measurement.interfaces[0]

    assert interface.download_bytes_per_second == 300.0
    assert interface.upload_bytes_per_second == 200.0


def test_interface_failure_does_not_prevent_other_interface_measurement(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    patch_provider(
        monkeypatch,
        lambda pernic=True: {
            "Ethernet": make_counters(1000, 2000),
            "Wi-Fi": make_counters(bytes_recv=-1),
        },
    )
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert len(measurement.interfaces) == 1
    assert measurement.interfaces[0].interface_id == "Ethernet"

    assert len(measurement.interface_errors) == 1
    assert measurement.interface_errors[0].interface_id == "Wi-Fi"
    assert measurement.is_partial


def test_interfaces_have_independent_baselines(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {
                "Ethernet": make_counters(1000, 2000),
                "Wi-Fi": make_counters(5000, 6000),
            },
            {
                "Ethernet": make_counters(1500, 2400),
                "Wi-Fi": make_counters(5300, 6200),
            },
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 12.0])

    worker._collect_measurement(1.0)
    measurement = worker._collect_measurement(1.0)

    interfaces = {
        interface.interface_id: interface
        for interface in measurement.interfaces
    }

    assert interfaces["Ethernet"].download_bytes_per_second == 250.0
    assert interfaces["Ethernet"].upload_bytes_per_second == 200.0

    assert interfaces["Wi-Fi"].download_bytes_per_second == 150.0
    assert interfaces["Wi-Fi"].upload_bytes_per_second == 100.0


class DuplicateInterfaceMapping(Mapping):
    """Test mapping that can expose duplicate interface entries."""

    def __init__(self, entries):
        self._entries = entries

    def __getitem__(self, key):
        for name, value in self._entries:
            if name == key:
                return value
        raise KeyError(key)

    def __iter__(self):
        return iter(dict(self._entries))

    def __len__(self):
        return len(dict(self._entries))

    def items(self):
        return self._entries


def test_duplicate_interface_after_valid_entry_creates_only_one_error(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    provider = DuplicateInterfaceMapping(
        [
            ("Ethernet", make_counters(1000, 2000)),
            ("Ethernet", make_counters(1500, 2500)),
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: provider)
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.interfaces == ()
    assert len(measurement.interface_errors) == 1
    assert measurement.interface_errors[0].interface_id == "Ethernet"
    assert measurement.interface_errors[0].error_code == (
        "NETWORK_DUPLICATE_INTERFACE"
    )
    assert "Ethernet" not in worker._baselines


def test_duplicate_interface_after_invalid_entry_creates_only_one_error(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    provider = DuplicateInterfaceMapping(
        [
            ("Ethernet", make_counters(bytes_recv=-1)),
            ("Ethernet", make_counters(1500, 2500)),
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: provider)
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.interfaces == ()
    assert len(measurement.interface_errors) == 1
    assert measurement.interface_errors[0].interface_id == "Ethernet"
    assert measurement.interface_errors[0].error_code == (
        "NETWORK_DUPLICATE_INTERFACE"
    )


def test_more_than_two_duplicate_entries_create_only_one_error(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    provider = DuplicateInterfaceMapping(
        [
            ("Ethernet", make_counters(1000, 2000)),
            ("Ethernet", make_counters(1500, 2500)),
            ("Ethernet", make_counters(2000, 3000)),
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: provider)
    patch_monotonic(monkeypatch, [10.0])

    measurement = worker._collect_measurement(1.0)

    assert measurement.interfaces == ()
    assert len(measurement.interface_errors) == 1
    assert measurement.interface_errors[0].error_code == (
        "NETWORK_DUPLICATE_INTERFACE"
    )


@pytest.mark.parametrize("elapsed", [0.0, -1.0])
def test_invalid_elapsed_time_rebaselines_without_rates(
    monkeypatch,
    elapsed,
):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            {"Ethernet": make_counters(1500, 2500)},
            {"Ethernet": make_counters(1800, 2900)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(
        monkeypatch,
        [10.0, 10.0 + elapsed, 12.0],
    )

    worker._collect_measurement(1.0)
    invalid_elapsed_measurement = worker._collect_measurement(1.0)
    recovered_measurement = worker._collect_measurement(1.0)

    invalid_interface = invalid_elapsed_measurement.interfaces[0]

    assert invalid_interface.download_bytes_per_second is None
    assert invalid_interface.upload_bytes_per_second is None
    assert invalid_elapsed_measurement.baseline_only_interface_ids == (
        "Ethernet",
    )

    recovered_interface = recovered_measurement.interfaces[0]

    expected_elapsed = 2.0 if elapsed == 0.0 else 3.0

    assert recovered_interface.download_bytes_per_second == pytest.approx(
        300.0 / expected_elapsed
    )
    assert recovered_interface.upload_bytes_per_second == pytest.approx(
        400.0 / expected_elapsed
    )


def test_invalid_interface_sample_preserves_previous_baseline(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            {"Ethernet": make_counters(bytes_recv=-1)},
            {"Ethernet": make_counters(1600, 2400)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0, 12.0])

    worker._collect_measurement(1.0)
    invalid_measurement = worker._collect_measurement(1.0)
    recovered_measurement = worker._collect_measurement(1.0)

    assert invalid_measurement.interfaces == ()
    assert len(invalid_measurement.interface_errors) == 1

    recovered_interface = recovered_measurement.interfaces[0]

    assert recovered_interface.download_bytes_per_second == 300.0
    assert recovered_interface.upload_bytes_per_second == 200.0


def test_partial_collection_preserves_other_interface_baselines(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {
                "Ethernet": make_counters(1000, 2000),
                "Wi-Fi": make_counters(5000, 6000),
            },
            {
                "Ethernet": make_counters(1200, 2200),
                "Wi-Fi": make_counters(bytes_recv=-1),
            },
            {
                "Ethernet": make_counters(1500, 2500),
                "Wi-Fi": make_counters(5600, 6800),
            },
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0, 12.0])

    worker._collect_measurement(1.0)
    partial_measurement = worker._collect_measurement(1.0)
    recovered_measurement = worker._collect_measurement(1.0)

    assert partial_measurement.is_partial
    assert len(partial_measurement.interfaces) == 1
    assert len(partial_measurement.interface_errors) == 1

    recovered_interfaces = {
        interface.interface_id: interface
        for interface in recovered_measurement.interfaces
    }

    assert recovered_interfaces["Ethernet"].download_bytes_per_second == 300.0
    assert recovered_interfaces["Ethernet"].upload_bytes_per_second == 300.0

    assert recovered_interfaces["Wi-Fi"].download_bytes_per_second == 300.0
    assert recovered_interfaces["Wi-Fi"].upload_bytes_per_second == 400.0


def test_counter_reset_is_not_reported_as_interface_error(monkeypatch):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {"Ethernet": make_counters(1000, 2000)},
            {"Ethernet": make_counters(500, 2500)},
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0])

    worker._collect_measurement(1.0)
    measurement = worker._collect_measurement(1.0)

    assert measurement.interface_errors == ()
    assert len(measurement.counter_resets) == 1
    assert measurement.is_fully_successful
    assert not measurement.is_partial


def test_normal_startup_callback_executes_exactly_once():
    started = []
    worker = None

    def on_started():
        started.append(True)
        worker.stop()

    worker = NetworkMonitoringWorker(
        sampling_interval=1.0,
        on_measurement=lambda measurement: None,
        on_measurement_failure=lambda code, message: None,
        on_worker_failure=lambda: None,
        on_started=on_started,
    )

    worker.run()

    assert started == [True]


def test_stop_takes_priority_over_reconfiguration():
    worker, _, _, _ = make_worker()

    worker._reconfigure_event.set()
    worker.stop()

    result = worker._wait_for_next_window(30.0)

    assert result.value == "stop"


def test_reconfiguration_is_consumed_without_losing_new_interval():
    worker, _, _, _ = make_worker()

    worker.set_sampling_interval(2.0)

    assert worker._reconfigure_event.is_set()

    worker._consume_reconfiguration()

    assert worker.sampling_interval == 2.0
    assert not worker._reconfigure_event.is_set()


def test_rate_overflow_preserves_baseline_and_other_interfaces(
    monkeypatch,
):
    worker, _, _, _ = make_worker()

    samples = iter(
        [
            {
                "Ethernet": make_counters(0, 0),
                "Wi-Fi": make_counters(1000, 2000),
            },
            {
                "Ethernet": make_counters(10**400, 10**400),
                "Wi-Fi": make_counters(1500, 2500),
            },
        ]
    )

    patch_provider(monkeypatch, lambda pernic=True: next(samples))
    patch_monotonic(monkeypatch, [10.0, 11.0])

    worker._collect_measurement(1.0)
    previous_ethernet_baseline = worker._baselines["Ethernet"]

    measurement = worker._collect_measurement(1.0)

    assert len(measurement.interface_errors) == 1
    assert measurement.interface_errors[0].interface_id == "Ethernet"
    assert measurement.interface_errors[0].error_code == (
        "NETWORK_INVALID_RATE"
    )

    assert worker._baselines["Ethernet"] == previous_ethernet_baseline

    assert len(measurement.interfaces) == 1
    wifi = measurement.interfaces[0]

    assert wifi.interface_id == "Wi-Fi"
    assert wifi.download_bytes_per_second == 500.0
    assert wifi.upload_bytes_per_second == 500.0
    assert measurement.is_partial


def test_worker_does_not_deliver_measurement_after_stop_during_collection(
    monkeypatch,
):
    worker, measurements, *_ = make_worker()

    monkeypatch.setattr(
        worker,
        "_wait_for_next_window",
        lambda interval: worker._WaitResult.TIMEOUT
        if hasattr(worker, "_WaitResult")
        else __import__(
            "system_monitor.workers.network_monitoring_worker",
            fromlist=["_WaitResult"],
        )._WaitResult.TIMEOUT,
    )

    def collect(interval):
        worker.stop()
        return object()

    monkeypatch.setattr(worker, "_collect_measurement", collect)

    worker.run()

    assert measurements == []


def test_worker_recovers_after_measurement_failure(monkeypatch):
    worker, measurements, failures, worker_failures = make_worker()

    wait_results = iter([
        worker._WaitResult.TIMEOUT
        if hasattr(worker, "_WaitResult")
        else __import__(
            "system_monitor.workers.network_monitoring_worker",
            fromlist=["_WaitResult"],
        )._WaitResult.TIMEOUT,
        worker._WaitResult.TIMEOUT
        if hasattr(worker, "_WaitResult")
        else __import__(
            "system_monitor.workers.network_monitoring_worker",
            fromlist=["_WaitResult"],
        )._WaitResult.TIMEOUT,
        worker._WaitResult.STOP
        if hasattr(worker, "_WaitResult")
        else __import__(
            "system_monitor.workers.network_monitoring_worker",
            fromlist=["_WaitResult"],
        )._WaitResult.STOP,
    ])

    monkeypatch.setattr(
        worker,
        "_wait_for_next_window",
        lambda interval: next(wait_results),
    )

    calls = []

    def collect(interval):
        calls.append(interval)

        if len(calls) == 1:
            raise NetworkWorkerError(
                "NETWORK_PROVIDER_FAILED",
                "Temporary network provider failure.",
            )

        return object()

    monkeypatch.setattr(worker, "_collect_measurement", collect)

    worker.run()

    assert calls == [1.0, 1.0]
    assert len(failures) == 1
    assert failures[0][0] == "NETWORK_PROVIDER_FAILED"
    assert len(measurements) == 1
    assert worker_failures == []
