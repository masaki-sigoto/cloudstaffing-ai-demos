"""A-04: 連続24時間以上の勤務。"""

from __future__ import annotations

from datetime import timedelta

from .base import AnomalyRule
from ._helpers import make_finding_record


class A04(AnomalyRule):
    pattern_id = "A-04"
    pattern_name = "連続24時間超勤務"

    def check(self, case, ctx):
        for p in case.punches:
            if p.clock_in and p.clock_out and (p.clock_out - p.clock_in) >= timedelta(hours=24):
                raw = {"shift_span_hours": case.shift.span_hours if case.shift else None}
                yield make_finding_record(p, case, self.pattern_id, self.pattern_name, raw)
