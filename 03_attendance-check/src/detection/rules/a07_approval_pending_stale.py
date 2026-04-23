"""A-07: 派遣先承認待ち滞留（申請単位）。"""

from __future__ import annotations

from .base import AnomalyRule
from ._helpers import make_finding_application


class A07(AnomalyRule):
    pattern_id = "A-07"
    pattern_name = "派遣先承認待ち滞留"
    requires_applications = True

    def check(self, case, ctx):
        if not ctx.has_applications:
            return
        targets = [
            a for a in (list(case.leaves) + list(case.overtimes)) if a.status == "pending"
        ]
        for a in targets:
            bd = ctx.holidays.business_days_between(a.applied_at.date(), ctx.as_of_date)
            if bd >= 3:
                yield make_finding_application(
                    case, a, self.pattern_id, self.pattern_name,
                    {
                        "application_id": a.application_id,
                        "applied_at": a.applied_at.isoformat(),
                        "business_days_elapsed": bd,
                        "application_type": a.type,
                    },
                )
