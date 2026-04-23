"""A-03: 休憩未入力（労基法34条）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_record


class A03(AnomalyRule):
    pattern_id = "A-03"
    pattern_name = "休憩未入力"

    def check(self, case, ctx):
        for p in case.punches:
            if p.clock_in is None or p.clock_out is None:
                continue
            worked = (p.clock_out - p.clock_in).total_seconds() / 60 - p.break_minutes
            if 360 < worked <= 480 and p.break_minutes < 45:
                yield make_finding_record(
                    p, case, self.pattern_id, self.pattern_name,
                    {"worked_minutes": worked, "break_minutes": p.break_minutes},
                )
            elif worked > 480 and p.break_minutes < 60:
                yield make_finding_record(
                    p, case, self.pattern_id, self.pattern_name,
                    {"worked_minutes": worked, "break_minutes": p.break_minutes},
                )
