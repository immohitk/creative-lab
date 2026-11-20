"""Tests for bounded metric history storage."""

from datetime import datetime, timedelta, timezone

import pytest

from system_monitor.presentation.history_buffer import HistoryBuffer, HistorySample


def test_history_buffer_retains_only_latest_samples():
    history = HistoryBuffer(capacity=3)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    for index in range(5):
        history.append(start + timedelta(seconds=index), index * 10)

    assert len(history) == 3
    assert [sample.value for sample in history] == [20.0, 30.0, 40.0]


def test_history_buffer_preserves_timestamp_order():
    history = HistoryBuffer()
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    second = first + timedelta(seconds=1)

    history.append(first, 1)
    history.append(second, 2)

    assert history.samples() == (
        HistorySample(first, 1.0),
        HistorySample(second, 2.0),
    )


def test_history_buffer_ignores_duplicate_timestamp():
    history = HistoryBuffer()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assert history.append(timestamp, 1)
    assert history.append(timestamp, 2) is False
    assert len(history) == 1
    assert history.samples()[0].value == 1.0


def test_history_buffer_rejects_out_of_order_timestamp():
    history = HistoryBuffer()
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    history.append(timestamp + timedelta(seconds=1), 2)

    with pytest.raises(ValueError, match="cannot precede"):
        history.append(timestamp, 1)


@pytest.mark.parametrize("capacity", [0, -1])
def test_history_buffer_rejects_non_positive_capacity(capacity):
    with pytest.raises(ValueError, match="positive"):
        HistoryBuffer(capacity)


def test_history_buffer_rejects_naive_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        HistoryBuffer().append(datetime(2026, 1, 1), 1)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_history_buffer_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match="finite"):
        HistoryBuffer().append(datetime.now(timezone.utc), value)


def test_history_buffer_clear_removes_samples():
    history = HistoryBuffer()
    history.append(datetime.now(timezone.utc), 1)

    history.clear()

    assert len(history) == 0
    assert history.samples() == ()
