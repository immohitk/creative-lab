
"""Tests for the reusable section header widget."""

import pytest

from system_monitor.presentation.widgets.section_header import SectionHeader


def test_section_header_initializes_with_expected_content():
    header = SectionHeader(
        title="Processor Information",
        description="Logical processor utilization",
    )

    assert header.title_label.text() == "Processor Information"
    assert header.description_label.text() == "Logical processor utilization"
    assert header.accessibleName() == "Processor Information"
    assert header.accessibleDescription() == "Logical processor utilization"

    header.deleteLater()


def test_section_header_supports_optional_description():
    header = SectionHeader(title="Memory Information")

    assert header.title_label.text() == "Memory Information"
    assert header.description_label.text() == ""
    assert header.description_label.isHidden()

    header.deleteLater()


def test_section_header_updates_description():
    header = SectionHeader(title="Disk Information")

    header.set_description("Storage capacity and volumes")

    assert header.description_label.text() == "Storage capacity and volumes"
    assert not header.description_label.isHidden()
    assert header.accessibleDescription() == "Storage capacity and volumes"

    header.set_description(None)

    assert header.description_label.isHidden()
    assert header.accessibleDescription() == ""

    header.deleteLater()


def test_section_header_rejects_empty_title():
    with pytest.raises(ValueError):
        SectionHeader(title=" ")


def test_section_header_rejects_invalid_description():
    with pytest.raises(TypeError):
        SectionHeader(
            title="Network Information",
            description=123,
        )


def test_section_header_rejects_invalid_description_update():
    header = SectionHeader(title="CPU Information")

    with pytest.raises(TypeError):
        header.set_description(123)

    header.deleteLater()
