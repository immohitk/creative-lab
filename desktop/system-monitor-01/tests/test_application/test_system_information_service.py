from datetime import datetime, timezone

import pytest

from system_monitor.models import Availability, CategoryResult
from system_monitor.services.system_information_service import (
    SystemInformationService,
)


def make_result(category, status=Availability.AVAILABLE):
    return CategoryResult(
        category=category,
        status=status,
        data={"test": True},
        collected_at=datetime.now(timezone.utc),
    )


def patch_all_collectors(monkeypatch, failure=None):
    from system_monitor.services import system_information_service as service_module

    categories = (
        "operating_system",
        "machine",
        "processor",
        "memory",
        "storage",
        "network_interfaces",
    )

    calls = []

    for category in categories:
        collector_module = getattr(service_module, category)

        def fake_collect(category=category):
            calls.append(category)

            if category == failure:
                raise RuntimeError("Simulated collector failure")

            return make_result(category)

        monkeypatch.setattr(collector_module, "collect", fake_collect)

    return calls


def test_collect_executes_collectors_in_order(monkeypatch):
    calls = patch_all_collectors(monkeypatch)
    service = SystemInformationService()

    profile = service.collect()

    assert calls == [
        "operating_system",
        "machine",
        "processor",
        "memory",
        "storage",
        "network_interfaces",
    ]
    assert profile == service.cached_profile


def test_collector_failure_does_not_stop_subsequent_collectors(monkeypatch):
    calls = patch_all_collectors(monkeypatch, failure="processor")
    service = SystemInformationService()

    profile = service.collect()

    assert calls[-4:] == [
        "processor",
        "memory",
        "storage",
        "network_interfaces",
    ]
    assert profile.processor.status == Availability.UNAVAILABLE
    assert profile.memory.status == Availability.AVAILABLE


def test_invalid_collector_result_is_rejected(monkeypatch):
    from system_monitor.services import system_information_service as service_module

    patch_all_collectors(monkeypatch)

    monkeypatch.setattr(
        service_module.operating_system,
        "collect",
        lambda: None,
    )

    service = SystemInformationService()
    profile = service.collect()

    assert profile.operating_system.status == Availability.UNAVAILABLE
    assert "invalid result" in profile.operating_system.error


def test_successful_collection_updates_cache(monkeypatch):
    patch_all_collectors(monkeypatch)
    service = SystemInformationService()

    profile = service.collect()

    assert service.cached_profile is profile


def test_manual_refresh_updates_cached_profile(monkeypatch):
    patch_all_collectors(monkeypatch)
    service = SystemInformationService()

    first_profile = service.collect()
    second_profile = service.refresh()

    assert second_profile is not first_profile
    assert service.cached_profile is second_profile


def test_unexpected_refresh_failure_preserves_previous_profile(monkeypatch):
    patch_all_collectors(monkeypatch)
    service = SystemInformationService()

    previous_profile = service.collect()

    patch_all_collectors(monkeypatch, failure="processor")

    refreshed_profile = service.refresh()

    assert refreshed_profile is previous_profile
    assert service.cached_profile is previous_profile


def test_initial_collection_failure_does_not_cache_invalid_profile(monkeypatch):
    patch_all_collectors(monkeypatch, failure="processor")
    service = SystemInformationService()

    profile = service.collect()

    assert profile.processor.status == Availability.UNAVAILABLE
    assert service.cached_profile is None


def test_all_categories_unavailable_preserves_previous_cache(monkeypatch):
    from system_monitor.services import system_information_service as service_module

    patch_all_collectors(monkeypatch)
    service = SystemInformationService()
    previous_profile = service.collect()

    categories = (
        "operating_system",
        "machine",
        "processor",
        "memory",
        "storage",
        "network_interfaces",
    )

    for category in categories:
        module = getattr(service_module, category)
        monkeypatch.setattr(
            module,
            "collect",
            lambda category=category: make_result(
                category, Availability.UNAVAILABLE
            ),
        )

    refreshed_profile = service.refresh()

    assert refreshed_profile is previous_profile
    assert service.cached_profile is previous_profile
