"""ルール配列を順次適用する AnomalyRuleEngine。"""

from __future__ import annotations

from .rules.a01_clock_out_missing import A01
from .rules.a02_clock_in_missing import A02
from .rules.a03_break_insufficient import A03
from .rules.a04_continuous_24h import A04
from .rules.a05_multi_clock import A05
from .rules.a06_application_mismatch import A06
from .rules.a07_approval_pending_stale import A07
from .rules.a08_night_unscheduled import A08
from .rules.a09_shift_deviation import A09
from .rules.a10_duplicate_punch import A10


class AnomalyRuleEngine:
    def __init__(self, rules=None):
        self.RULES = rules or [
            A01(), A02(), A03(), A04(), A05(),
            A06(), A07(), A08(), A09(), A10(),
        ]

    def run(self, cases: list, ctx) -> tuple:
        """(findings, rule_skipped_info) を返す。"""
        rule_skipped_info = []
        active_rules = []
        for r in self.RULES:
            if r.requires_applications and not ctx.has_applications:
                rule_skipped_info.append(
                    {"pattern_id": r.pattern_id, "reason": "applications.csv missing"}
                )
                continue
            if r.requires_shifts and not ctx.has_shifts:
                rule_skipped_info.append(
                    {"pattern_id": r.pattern_id, "reason": "shifts.csv missing"}
                )
                continue
            active_rules.append(r)

        findings: list = []
        for case in cases:
            for rule in active_rules:
                for f in rule.check(case, ctx):
                    findings.append(f)
        return findings, rule_skipped_info
