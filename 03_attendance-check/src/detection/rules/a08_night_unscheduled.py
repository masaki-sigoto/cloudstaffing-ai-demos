"""A-08: 深夜打刻（シフト外）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_day


def _is_night(dt) -> bool:
    return dt.hour >= 22 or dt.hour < 5


class A08(AnomalyRule):
    pattern_id = "A-08"
    pattern_name = "深夜打刻（シフト外）"
    requires_shifts = True

    def check(self, case, ctx):
        if not ctx.has_shifts:
            return
        if not case.shift:
            return
        for p in case.punches:
            for t in (p.clock_in, p.clock_out):
                if t is None:
                    continue
                if not _is_night(t):
                    continue
                if case.shift.scheduled_start <= t <= case.shift.scheduled_end:
                    continue
                yield make_finding_day(
                    case, self.pattern_id, self.pattern_name,
                    {"night_punch_at": t.isoformat()},
                )
                return  # 1日1件で足りる
