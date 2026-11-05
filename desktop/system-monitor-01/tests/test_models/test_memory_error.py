from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from system_monitor.models import MemoryError


def make_error(**overrides):
    values = {
        "error_code": "MEMORY_MEASUREMENT_FAILED",
        "message": "Memory measurement is temporarily unavailable.",
        "occurred_at": datetime.now(timezone.utc),
        "consecutive_failures": 1,
    }
    values.update(overrides)

    return MemoryError(**values)


def test_valid_error_is_created():
    error = make_error()

    assert error.error_code == "MEMORY_MEASUREMENT_FAILED"
    assert error.message == "Memory measurement is temporarily unavailable."
    assert error.consecutive_failures == 1


@pytest.mark.parametrize("value", ["", " ", None, 123])
def test_invalid_error_code_is_rejected(value):
    with pytest.raises(ValueError):
        make_error(error_code=value)


@pytest.mark.parametrize("value", ["", " ", None, 123])
def test_invalid_error_message_is_rejected(value):
    with pytest.raises(ValueError):
        make_error(message=value)


def test_timestamp_must_be_datetime():
    with pytest.raises(TypeError):
        make_error(occurred_at="2026-11-04T00:00:00Z")


def test_timestamp_must_be_timezone_aware():
    with pytest.raises(ValueError):
        make_error(occurred_at=datetime.now())


def test_timestamp_must_be_utc():
    with pytest.raises(ValueError):
        make_error(
            occurred_at=datetime.now(timezone.utc).astimezone()
        ) if datetime.now().astimezone().utcoffset() != timezone.utc.utcoffset(None) else None


@pytest.mark.parametrize("value", [-1, True, 1.5, "1"])
def test_invalid_consecutive_failure_count_is_rejected(value):
    with pytest.raises(ValueError):
        make_error(consecutive_failures=value)


def test_error_fields_are_immutable():
    error = make_error()

    with pytest.raises(FrozenInstanceError):
        error.message = "Changed message."
