"""A-10: 重複打刻（同一種別で5分以内）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_record


class A10(AnomalyRule):
    pattern_id = "A-10"
    pattern_name = "重複打刻"

    def check(self, case, ctx):
        # clock_in 隣接差
        ins = sorted(
            [p for p in case.punches if p.clock_in],
            key=lambda p: p.clock_in,
        )
        for a, b in zip(ins, ins[1:]):
            if (b.clock_in - a.clock_in).total_seconds() <= 300:
                yield make_finding_record(
                    b, case, self.pattern_id, self.pattern_name,
                    {"previous_record_id": a.record_id, "which": "clock_in"},
                )

        outs = sorted(
            [p for p in case.punches if p.clock_out],
            key=lambda p: p.clock_out,
        )
        for a, b in zip(outs, outs[1:]):
            if (b.clock_out - a.clock_out).total_seconds() <= 300:
                yield make_finding_record(
                    b, case, self.pattern_id, self.pattern_name,
                    {"previous_record_id": a.record_id, "which": "clock_out"},
                )
