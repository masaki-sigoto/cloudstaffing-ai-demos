"""A-09: シフトとの大幅乖離（±60分超）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_record


class A09(AnomalyRule):
    pattern_id = "A-09"
    pattern_name = "シフトとの大幅乖離"
    requires_shifts = True

    def check(self, case, ctx):
        if not ctx.has_shifts or case.shift is None:
            return
        emitted: set = set()
        for p in case.punches:
            if p.clock_in is not None:
                diff = abs((p.clock_in - case.shift.scheduled_start).total_seconds())
                if diff > 3600 and p.record_id not in emitted:
                    yield make_finding_record(
                        p, case, self.pattern_id, self.pattern_name,
                        {"deviation_seconds": diff, "which": "clock_in"},
                    )
                    emitted.add(p.record_id)
                    continue
            if p.clock_out is not None:
                diff = abs((p.clock_out - case.shift.scheduled_end).total_seconds())
                if diff > 3600 and p.record_id not in emitted:
                    yield make_finding_record(
                        p, case, self.pattern_id, self.pattern_name,
                        {"deviation_seconds": diff, "which": "clock_out"},
                    )
                    emitted.add(p.record_id)
