"""AnomalyRule 共通 IF（docs/03_spec.md §5.5）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Iterator

from ...models import Finding, MatchedCase


@dataclass(frozen=True)
class DetectionContext:
    as_of_date: date
    holidays: object  # HolidayCalendar Protocol
    has_applications: bool
    has_shifts: bool


class AnomalyRule(ABC):
    pattern_id: str = ""
    pattern_name: str = ""
    requires_applications: bool = False
    requires_shifts: bool = False

    @abstractmethod
    def check(self, case: MatchedCase, ctx: DetectionContext) -> Iterator[Finding]:
        ...
