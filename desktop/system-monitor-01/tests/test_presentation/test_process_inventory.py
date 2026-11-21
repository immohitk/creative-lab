
"""Tests for process inventory filtering and sorting."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from system_monitor.models.process_measurement import ProcessMeasurement
from system_monitor.presentation.process_inventory import (
    filter_and_sort_processes,
)


def make_process(
    pid=100,
    name="test-process",
    cpu_percent=12.5,
    memory_bytes=1024,
    status="running",
    executable_path=None,
):
    return ProcessMeasurement(
        pid=pid,
        name=name,
        cpu_percent=cpu_percent,
        memory_bytes=memory_bytes,
        status=status,
        sampled_at=datetime.now(timezone.utc),
        executable_path=executable_path,
    )


def make_classifications(processes, category="Application"):
    return {
        process.pid: SimpleNamespace(category=category)
        for process in processes
    }


def test_default_sort_is_cpu_descending():
    processes = [
        make_process(pid=1, cpu_percent=10.0),
        make_process(pid=2, cpu_percent=80.0),
        make_process(pid=3, cpu_percent=40.0),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
    )

    assert [process.pid for process in result] == [2, 3, 1]


def test_cpu_unavailable_values_are_always_last():
    processes = [
        make_process(pid=1, cpu_percent=None),
        make_process(pid=2, cpu_percent=10.0),
        make_process(pid=3, cpu_percent=None),
        make_process(pid=4, cpu_percent=50.0),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
    )

    assert [process.pid for process in result] == [4, 2, 1, 3]


def test_cpu_ties_use_memory_descending():
    processes = [
        make_process(pid=1, cpu_percent=20.0, memory_bytes=100),
        make_process(pid=2, cpu_percent=20.0, memory_bytes=500),
        make_process(pid=3, cpu_percent=20.0, memory_bytes=300),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
    )

    assert [process.pid for process in result] == [2, 3, 1]


def test_cpu_ascending_keeps_memory_descending_tie_breaker():
    processes = [
        make_process(pid=1, cpu_percent=20.0, memory_bytes=100),
        make_process(pid=2, cpu_percent=20.0, memory_bytes=500),
        make_process(pid=3, cpu_percent=10.0, memory_bytes=300),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
        descending=False,
    )

    assert [process.pid for process in result] == [3, 2, 1]


def test_pid_sort_is_numeric():
    processes = [
        make_process(pid=100),
        make_process(pid=9),
        make_process(pid=20),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
        sort_key="pid",
        descending=False,
    )

    assert [process.pid for process in result] == [9, 20, 100]


def test_name_sort_is_case_insensitive():
    processes = [
        make_process(pid=1, name="zebra"),
        make_process(pid=2, name="Apple"),
        make_process(pid=3, name="banana"),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
        sort_key="name",
        descending=False,
    )

    assert [process.name for process in result] == [
        "Apple",
        "banana",
        "zebra",
    ]


def test_category_filter_returns_only_matching_processes():
    processes = [
        make_process(pid=1),
        make_process(pid=2),
        make_process(pid=3),
    ]

    classifications = {
        1: SimpleNamespace(category="System"),
        2: SimpleNamespace(category="Application"),
        3: SimpleNamespace(category="Service"),
    }

    result = filter_and_sort_processes(
        processes,
        classifications,
        category="Application",
    )

    assert [process.pid for process in result] == [2]


def test_missing_classification_defaults_to_unclassified():
    processes = [make_process(pid=1)]

    result = filter_and_sort_processes(
        processes,
        {},
        category="Unclassified",
    )

    assert [process.pid for process in result] == [1]


def test_search_matches_process_name_case_insensitively():
    processes = [
        make_process(pid=1, name="Code.exe"),
        make_process(pid=2, name="msedge.exe"),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
        search_text="CODE",
    )

    assert [process.pid for process in result] == [1]


def test_search_matches_pid():
    processes = [
        make_process(pid=1234),
        make_process(pid=5678),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
        search_text="567",
    )

    assert [process.pid for process in result] == [5678]


def test_search_matches_executable_path():
    processes = [
        make_process(
            pid=1,
            executable_path=r"C:\Windows\System32\svchost.exe",
        ),
        make_process(
            pid=2,
            executable_path=r"C:\Program Files\App\app.exe",
        ),
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
        search_text="system32",
    )

    assert [process.pid for process in result] == [1]


def test_search_and_category_filter_can_be_combined():
    processes = [
        make_process(pid=1, name="Code.exe"),
        make_process(pid=2, name="Code Helper"),
        make_process(pid=3, name="msedge.exe"),
    ]

    classifications = {
        1: SimpleNamespace(category="Application"),
        2: SimpleNamespace(category="System"),
        3: SimpleNamespace(category="Application"),
    }

    result = filter_and_sort_processes(
        processes,
        classifications,
        search_text="code",
        category="Application",
    )

    assert [process.pid for process in result] == [1]


@pytest.mark.parametrize("sort_key", ["invalid", "path", "cpu"])
def test_invalid_sort_key_is_rejected(sort_key):
    with pytest.raises(ValueError):
        filter_and_sort_processes(
            [],
            {},
            sort_key=sort_key,
        )


def test_invalid_category_is_rejected():
    with pytest.raises(ValueError):
        filter_and_sort_processes(
            [],
            {},
            category="Unknown",
        )


def test_filtering_is_not_limited_to_250_processes():
    processes = [
        make_process(pid=1000 + index, name=f"process-{index}")
        for index in range(300)
    ]

    result = filter_and_sort_processes(
        processes,
        make_classifications(processes),
        search_text="process-299",
    )

    assert len(result) == 1
    assert result[0].pid == 1299
