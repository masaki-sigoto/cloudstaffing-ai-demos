"""A-06: 申請×実績不整合（休暇申請と打刻の矛盾／残業申請漏れ）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_day


def _pick_overtime_status(overtimes):
    priority = {"approved": 0, "pending": 1, "rejected": 2}
    if not overtimes:
        return None
    return min(overtimes, key=lambda a: priority.get(a.status, 99)).status


class A06(AnomalyRule):
    pattern_id = "A-06"
    pattern_name = "申請×実績不整合"
    requires_applications = True

    def check(self, case, ctx):
        if not ctx.has_applications:
            return
        if not case.punches:
            return

        # 分岐1: 休暇申請と打刻の矛盾
        approved_leave = next(
            (l for l in case.leaves if l.status == "approved"), None
        )
        if approved_leave and any(
            p.clock_in or p.clock_out for p in case.punches
        ):
            yield make_finding_day(
                case, self.pattern_id, "休暇申請と打刻の矛盾",
                {"branch": "leave_vs_punch", "leave_application_id": approved_leave.application_id},
            )

        # 分岐2: 残業申請漏れ
        if case.shift:
            threshold_h = case.shift.span_hours - 1.0
        else:
            threshold_h = 8.0
        threshold_min = threshold_h * 60 + 30
        total_worked_min = 0.0
        for p in case.punches:
            if p.clock_in and p.clock_out:
                total_worked_min += (
                    (p.clock_out - p.clock_in).total_seconds() / 60 - p.break_minutes
                )
        if total_worked_min > threshold_min:
            ot_status = _pick_overtime_status(case.overtimes)
            if ot_status in ("rejected", None):
                yield make_finding_day(
                    case, self.pattern_id, "残業申請漏れ",
                    {
                        "branch": "overtime_missing",
                        "worked_minutes": total_worked_min,
                        "threshold_minutes": threshold_min,
                        "ot_status": ot_status or "none",
                    },
                )
