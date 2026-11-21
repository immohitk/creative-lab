
from datetime import datetime, timezone

import pytest

from system_monitor.models.process_measurement import ProcessMeasurement
from system_monitor.presentation.process_classifier import ProcessClassifier


@pytest.fixture
def classifier():
    return ProcessClassifier(
        windows_directory=r"C:\Windows",
        application_directories=(
            r"C:\Program Files",
            r"C:\Program Files (x86)",
            r"C:\Users\Test\AppData\Local\Programs",
        ),
    )


def make_measurement(
    *,
    executable_path=None,
    service_names=(),
    metadata_state="unavailable",
):
    return ProcessMeasurement(
        pid=1234,
        name="example.exe",
        cpu_percent=12.5,
        memory_bytes=1024,
        status="running",
        sampled_at=datetime.now(timezone.utc),
        executable_path=executable_path,
        service_names=service_names,
        metadata_state=metadata_state,
    )


def test_classifies_windows_service_before_executable_path(classifier):
    measurement = make_measurement(
        executable_path=r"C:\Windows\System32\svchost.exe",
        service_names=("Dhcp", "Dnscache"),
        metadata_state="verified",
    )

    result = classifier.classify(measurement)

    assert result.category == "Service"
    assert result.confidence == "Verified"


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Windows\System32\svchost.exe",
        r"C:\Windows\SysWOW64\example.exe",
        r"C:\Windows\WinSxS\example.exe",
        r"C:\Windows\servicing\example.exe",
    ],
)
def test_classifies_recognized_system_directories(classifier, path):
    measurement = make_measurement(
        executable_path=path,
        metadata_state="verified",
    )

    result = classifier.classify(measurement)

    assert result.category == "System"
    assert result.confidence == "Verified"


@pytest.mark.parametrize(
    "path",
    [
        r"C:\Program Files\Example\example.exe",
        r"C:\Program Files (x86)\Example\example.exe",
        r"C:\Users\Test\AppData\Local\Programs\Example\example.exe",
    ],
)
def test_classifies_recognized_application_directories(classifier, path):
    measurement = make_measurement(
        executable_path=path,
        metadata_state="verified",
    )

    result = classifier.classify(measurement)

    assert result.category == "Application"
    assert result.confidence == "Verified"


def test_does_not_classify_path_with_similar_directory_name(classifier):
    measurement = make_measurement(
        executable_path=r"C:\Windows\System32Backup\example.exe",
        metadata_state="verified",
    )

    result = classifier.classify(measurement)

    assert result.category == "Unclassified"
    assert result.confidence == "Partial"


def test_does_not_classify_every_windows_directory_as_system(classifier):
    measurement = make_measurement(
        executable_path=r"C:\Windows\Temp\example.exe",
        metadata_state="verified",
    )

    result = classifier.classify(measurement)

    assert result.category == "Unclassified"
    assert result.confidence == "Partial"


def test_unrecognized_executable_is_unclassified(classifier):
    measurement = make_measurement(
        executable_path=r"D:\CustomTools\example.exe",
        metadata_state="verified",
    )

    result = classifier.classify(measurement)

    assert result.category == "Unclassified"
    assert result.confidence == "Partial"


def test_missing_metadata_is_unavailable(classifier):
    measurement = make_measurement()

    result = classifier.classify(measurement)

    assert result.category == "Unclassified"
    assert result.confidence == "Unavailable"


def test_partial_metadata_without_recognized_path_is_partial(classifier):
    measurement = make_measurement(
        metadata_state="partial",
    )

    result = classifier.classify(measurement)

    assert result.category == "Unclassified"
    assert result.confidence == "Partial"


def test_invalid_measurement_type_is_rejected(classifier):
    with pytest.raises(TypeError):
        classifier.classify("not a process measurement")
