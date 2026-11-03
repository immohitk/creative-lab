import logging
from datetime import datetime, timezone

from system_monitor.collectors import (
    machine,
    memory,
    network_interfaces,
    operating_system,
    processor,
    storage,
)
from system_monitor.models import (
    Availability,
    CategoryResult,
    SystemProfile,
)


logger = logging.getLogger(__name__)


class SystemInformationService:
    def __init__(self):
        self._cached_profile: SystemProfile | None = None

    @property
    def cached_profile(self) -> SystemProfile | None:
        return self._cached_profile

    def collect(self) -> SystemProfile:
        previous_profile = self._cached_profile
        collected_at = datetime.now(timezone.utc)
        unexpected_failure = False

        collectors = (
            ("operating_system", operating_system.collect),
            ("machine", machine.collect),
            ("processor", processor.collect),
            ("memory", memory.collect),
            ("storage", storage.collect),
            ("network_interfaces", network_interfaces.collect),
        )

        results = {}

        for category, collector in collectors:
            try:
                result = collector()

                if not isinstance(result, CategoryResult):
                    raise TypeError(
                        f"{category} collector returned an invalid result."
                    )

                if result.category != category:
                    raise ValueError(
                        f"{category} collector returned category "
                        f"'{result.category}'."
                    )

            except Exception as exc:
                unexpected_failure = True
                logger.exception(
                    "Unexpected failure in %s collector.",
                    category,
                )

                result = CategoryResult(
                    category=category,
                    status=Availability.UNAVAILABLE,
                    data=None,
                    collected_at=datetime.now(timezone.utc),
                    error=f"{type(exc).__name__}: {exc}",
                )

            results[category] = result

        profile = SystemProfile(
            collected_at=collected_at,
            operating_system=results["operating_system"],
            machine=results["machine"],
            processor=results["processor"],
            memory=results["memory"],
            storage=results["storage"],
            network_interfaces=results["network_interfaces"],
        )

        if unexpected_failure:
            if previous_profile is not None:
                return previous_profile

            return profile

        if all(
            result.status == Availability.UNAVAILABLE
            for result in results.values()
        ):
            if previous_profile is not None:
                return previous_profile

            return profile

        self._cached_profile = profile
        return profile

    def refresh(self) -> SystemProfile:
        return self.collect()
