"""A-01: 退勤打刻漏れ（出勤のみ）。scope=RECORD。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_record


class A01(AnomalyRule):
    pattern_id = "A-01"
    pattern_name = "退勤打刻漏れ"

    def check(self, case, ctx):
        for p in case.punches:
            if p.clock_in is not None and p.clock_out is None:
                yield make_finding_record(p, case, self.pattern_id, self.pattern_name)
