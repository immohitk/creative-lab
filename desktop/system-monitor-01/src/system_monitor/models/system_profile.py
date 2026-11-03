from dataclasses import dataclass
from datetime import datetime

from system_monitor.models.category_result import CategoryResult


@dataclass(frozen=True)
class SystemProfile:
    collected_at: datetime
    operating_system: CategoryResult
    machine: CategoryResult
    processor: CategoryResult
    memory: CategoryResult
    storage: CategoryResult
    network_interfaces: CategoryResult
