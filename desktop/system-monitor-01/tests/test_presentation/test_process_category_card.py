
import pytest

from PySide6.QtWidgets import QApplication

from system_monitor.presentation.widgets.process_category_card import (
    ProcessCategoryCard,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_category_card_initializes_with_empty_metrics(qapp):
    card = ProcessCategoryCard("System", "#60A5FA")

    assert card.category == "System"
    assert card.count_label.text() == "0"
    assert card.cpu_label.text() == "CPU —"
    assert card.memory_label.text() == "Memory 0.0 B"


def test_category_card_updates_metrics(qapp):
    card = ProcessCategoryCard("Applications", "#A78BFA")

    card.set_metrics(
        process_count=42,
        cpu_percent=18.75,
        memory_bytes=1024 * 1024 * 512,
    )

    assert card.count_label.text() == "42"
    assert card.cpu_label.text() == "CPU 18.8%"
    assert card.memory_label.text() == "Memory 512.0 MB"


def test_category_card_formats_large_process_counts(qapp):
    card = ProcessCategoryCard("Services", "#22C55E")

    card.set_metrics(
        process_count=1234,
        cpu_percent=2.5,
        memory_bytes=1024,
    )

    assert card.count_label.text() == "1,234"


def test_category_card_preserves_unavailable_cpu(qapp):
    card = ProcessCategoryCard("Unclassified", "#F59E0B")

    card.set_metrics(
        process_count=5,
        cpu_percent=None,
        memory_bytes=2048,
    )

    assert card.cpu_label.text() == "CPU —"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"process_count": -1, "cpu_percent": 0, "memory_bytes": 0},
        {"process_count": 1, "cpu_percent": 0, "memory_bytes": -1},
        {"process_count": True, "cpu_percent": 0, "memory_bytes": 0},
        {"process_count": 1, "cpu_percent": float("nan"), "memory_bytes": 0},
    ],
)
def test_category_card_rejects_invalid_metrics(qapp, kwargs):
    card = ProcessCategoryCard("System", "#60A5FA")

    with pytest.raises((TypeError, ValueError)):
        card.set_metrics(**kwargs)


def test_category_card_rejects_empty_category(qapp):
    with pytest.raises(ValueError):
        ProcessCategoryCard("", "#60A5FA")
