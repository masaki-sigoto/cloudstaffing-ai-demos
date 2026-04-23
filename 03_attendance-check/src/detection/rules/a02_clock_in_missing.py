"""A-02: 出勤打刻漏れ（退勤のみ）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_record


class A02(AnomalyRule):
    pattern_id = "A-02"
    pattern_name = "出勤打刻漏れ"

    def check(self, case, ctx):
        for p in case.punches:
            if p.clock_in is None and p.clock_out is not None:
                yield make_finding_record(p, case, self.pattern_id, self.pattern_name)
