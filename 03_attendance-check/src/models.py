"""共通データモデル（docs/03_spec.md §4.2）。"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Mapping, Optional


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Scope(str, Enum):
    RECORD = "record"
    DAY = "day"
    APPLICATION = "application"


@dataclass(frozen=True)
class PunchRecord:
    record_id: str
    staff_id: str
    staff_name: str
    client_id: str
    client_name: str
    client_site: str
    date: date
    clock_in: Optional[datetime]
    clock_out: Optional[datetime]
    break_minutes: int
    assignee_id: str
    assignee_name: str


@dataclass(frozen=True)
class LeaveApplication:
    application_id: str
    staff_id: str
    date: date
    type: str  # "leave" | "overtime"
    status: str  # "pending" | "approved" | "rejected"
    applied_at: datetime
    approved_at: Optional[datetime]


@dataclass(frozen=True)
class ShiftPlan:
    staff_id: str
    date: date
    scheduled_start: datetime
    scheduled_end: datetime

    @property
    def span_hours(self) -> float:
        return (self.scheduled_end - self.scheduled_start).total_seconds() / 3600.0


@dataclass
class MatchedCase:
    staff_id: str
    date: date
    client_id: str
    client_site: str
    assignee_id: str
    punches: list = field(default_factory=list)
    leaves: list = field(default_factory=list)
    overtimes: list = field(default_factory=list)
    shift: Optional[ShiftPlan] = None
    approver_statuses: list = field(default_factory=list)

    @property
    def day_key(self) -> str:
        return f"{self.staff_id}_{self.date.isoformat()}_{self.client_id}_{self.client_site}_{self.assignee_id}"

    def within_scheduled(self, client_id: str) -> bool:
        """A-05据え置き例外判定用：同一 client_id 内の実働合計が所定労働時間以内か。"""
        if not self.shift:
            scheduled_min = 8 * 60
        else:
            scheduled_min = (self.shift.span_hours - 1.0) * 60
        total = 0.0
        for p in self.punches:
            if p.client_id != client_id or not (p.clock_in and p.clock_out):
                continue
            total += (p.clock_out - p.clock_in).total_seconds() / 60 - p.break_minutes
        return total <= scheduled_min


@dataclass(frozen=True)
class Finding:
    pattern_id: str
    pattern_name: str
    scope: Scope
    staff_id: str
    staff_name: str
    date: date
    client_id: str
    client_name: str
    client_site: str
    assignee_id: str
    assignee_name: str
    approver_statuses: tuple
    record_id: Optional[str] = None
    application_id: Optional[str] = None
    day_key: str = ""
    raw_context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.day_key:
            raise ValueError("Finding.day_key は全 scope で必須")
        if self.scope == Scope.RECORD and not self.record_id:
            raise ValueError("scope=RECORD には record_id が必須")
        if self.scope == Scope.APPLICATION and not self.application_id:
            raise ValueError("scope=APPLICATION には application_id が必須")

    @property
    def finding_key(self) -> str:
        if self.pattern_id == "A-06":
            branch = str(self.raw_context.get("branch", "unknown"))
            return f"a06:{self.staff_id}:{self.date.isoformat()}:{branch}"
        if self.scope == Scope.RECORD:
            return f"record:{self.record_id}"
        if self.scope == Scope.DAY:
            return f"day:{self.day_key}"
        if self.scope == Scope.APPLICATION:
            return f"application:{self.application_id}"
        raise ValueError(f"Unknown scope: {self.scope}")


@dataclass(frozen=True)
class ScoreBreakdown:
    payroll: int
    billing: int
    legal: int


@dataclass
class ScoredFinding:
    finding_key: str
    primary: Finding
    additional_patterns: list
    severity: Severity
    score_breakdown: ScoreBreakdown
    recommended_action: str = ""


@dataclass(frozen=True)
class SkippedRecord:
    file: str
    line_no: int
    staff_id: Optional[str]
    date: Optional[str]
    reason: str
