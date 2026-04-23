"""A-05: 1日複数回の出退勤（scope=DAY）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_day


class A05(AnomalyRule):
    pattern_id = "A-05"
    pattern_name = "1日複数回の出退勤"

    def check(self, case, ctx):
        complete = [p for p in case.punches if p.clock_in and p.clock_out]
        if len(complete) >= 2:
            yield make_finding_day(
                case, self.pattern_id, self.pattern_name,
                {"pair_count": len(complete)},
            )
