from dataclasses import dataclass
from datetime import datetime
from typing import Any

from system_monitor.models.availability import Availability


@dataclass(frozen=True)
class CategoryResult:
    category: str
    status: Availability
    data: Any
    collected_at: datetime
    error: str | None = None
