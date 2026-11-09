from dataclasses import dataclass
from datetime import datetime, timedelta
import math

from system_monitor.models.network_counter_reset import NetworkCounterReset
from system_monitor.models.network_error import NetworkError
from system_monitor.models.network_interface_measurement import (
    NetworkInterfaceMeasurement,
)


@dataclass(frozen=True, slots=True)
class NetworkMeasurement:
    interfaces: tuple[NetworkInterfaceMeasurement, ...]
    interface_errors: tuple[NetworkError, ...]
    counter_resets: tuple[NetworkCounterReset, ...]
    baseline_only_interface_ids: tuple[str, ...]
    sampling_interval: float
    started_at: datetime
    completed_at: datetime

    def __post_init__(self):
        collection_fields = (
            ("interfaces", NetworkInterfaceMeasurement),
            ("interface_errors", NetworkError),
            ("counter_resets", NetworkCounterReset),
        )

        for field_name, expected_type in collection_fields:
            value = getattr(self, field_name)

            if not isinstance(value, (tuple, list)):
                raise TypeError(f"{field_name} must be a tuple or list.")

            normalized = tuple(value)

            if any(not isinstance(item, expected_type) for item in normalized):
                raise TypeError(
                    f"Every item in {field_name} must be a "
                    f"{expected_type.__name__}."
                )

            object.__setattr__(self, field_name, normalized)

        if not isinstance(self.baseline_only_interface_ids, (tuple, list)):
            raise TypeError(
                "Baseline-only interface identities must be a tuple or list."
            )

        baseline_ids = tuple(self.baseline_only_interface_ids)

        if any(not isinstance(item, str) or not item.strip() for item in baseline_ids):
            raise ValueError(
                "Every baseline-only interface identity must be a non-empty string."
            )

        if len(baseline_ids) != len(set(baseline_ids)):
            raise ValueError("Baseline-only interface identities cannot contain duplicates.")

        interface_ids = [item.interface_id for item in self.interfaces]

        if len(interface_ids) != len(set(interface_ids)):
            raise ValueError(
                "A measurement cannot contain duplicate interface identities."
            )

        error_ids = [
            item.interface_id
            for item in self.interface_errors
            if item.interface_id is not None
        ]

        if len(error_ids) != len(set(error_ids)):
            raise ValueError("A measurement cannot contain duplicate interface errors.")

        if set(interface_ids).intersection(error_ids):
            raise ValueError(
                "An interface cannot have both a measurement and an error."
            )

        interface_map = {
            item.interface_id: item
            for item in self.interfaces
        }

        if not set(baseline_ids).issubset(interface_map):
            raise ValueError(
                "Every baseline-only identity must refer to a successful interface."
            )

        for interface_id in baseline_ids:
            interface = interface_map[interface_id]

            if (
                interface.download_bytes_per_second is not None
                or interface.upload_bytes_per_second is not None
            ):
                raise ValueError(
                    "Baseline-only interfaces must have both rates set to None."
                )

        for reset in self.counter_resets:
            if reset.interface_id not in interface_map:
                raise ValueError(
                    "Every counter reset must refer to a successfully measured interface."
                )

        if (
            isinstance(self.sampling_interval, bool)
            or not isinstance(self.sampling_interval, (int, float))
        ):
            raise TypeError("Sampling interval must be numeric.")

        interval = float(self.sampling_interval)

        if not math.isfinite(interval) or not 0.5 <= interval <= 60.0:
            raise ValueError("Sampling interval must be between 0.5 and 60 seconds.")

        self._validate_timestamp(self.started_at, "Start")
        self._validate_timestamp(self.completed_at, "Completion")

        if self.completed_at < self.started_at:
            raise ValueError("Completion timestamp cannot precede start timestamp.")

        object.__setattr__(self, "baseline_only_interface_ids", baseline_ids)
        object.__setattr__(self, "sampling_interval", interval)

    @staticmethod
    def _validate_timestamp(value, field_name):
        if not isinstance(value, datetime):
            raise TypeError(f"{field_name} timestamp must be a datetime.")

        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError(f"{field_name} timestamp must be UTC-aware.")

    @property
    def is_partial(self) -> bool:
        return bool(self.interfaces and self.interface_errors)

    @property
    def is_fully_successful(self) -> bool:
        return not self.interface_errors

    @property
    def is_empty(self) -> bool:
        return not self.interfaces and not self.interface_errors

    @property
    def is_unavailable(self) -> bool:
        return not self.interfaces and bool(self.interface_errors)

    @property
    def has_baseline_only_interfaces(self) -> bool:
        return bool(self.baseline_only_interface_ids)
