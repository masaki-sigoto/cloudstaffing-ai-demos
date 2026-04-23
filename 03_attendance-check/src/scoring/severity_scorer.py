"""3軸スコアテーブル＋例外条件の重要度判定。"""

from __future__ import annotations

from collections import defaultdict

from ..models import ScoreBreakdown, ScoredFinding, Severity

SCORE_TABLE = {
    "A-01": ScoreBreakdown(3, 3, 2),
    "A-02": ScoreBreakdown(3, 3, 2),
    "A-03": ScoreBreakdown(2, 1, 2),
    "A-04": ScoreBreakdown(2, 2, 3),
    "A-05": ScoreBreakdown(1, 1, 1),
    "A-06": ScoreBreakdown(3, 3, 2),
    "A-07": ScoreBreakdown(1, 2, 1),
    "A-08": ScoreBreakdown(2, 1, 2),
    "A-09": ScoreBreakdown(2, 2, 1),
    "A-10": ScoreBreakdown(3, 3, 1),
}


class SeverityScorer:
    def score(self, findings: list, case_index: dict) -> list:
        buckets = defaultdict(list)
        for f in findings:
            buckets[f.finding_key].append(f)

        scored = []
        for key, group in buckets.items():
            case = case_index.get(group[0].day_key)
            per_scores = [self._resolve_score(f, case) for f in group]
            max_score = max(per_scores)
            severity = {3: Severity.HIGH, 2: Severity.MEDIUM, 1: Severity.LOW}[
                max_score
            ]
            primary = self._pick_primary(group, per_scores)
            additional = [f.pattern_id for f in group if f is not primary]
            scored.append(
                ScoredFinding(
                    finding_key=key,
                    primary=primary,
                    additional_patterns=additional,
                    severity=severity,
                    score_breakdown=SCORE_TABLE[primary.pattern_id],
                )
            )
        return sorted(scored, key=self._sort_key)

    def _pick_primary(self, group, per_scores):
        paired = list(zip(group, per_scores))
        paired.sort(
            key=lambda item: (
                -item[1],
                item[0].pattern_id,
                item[0].record_id or "",
                item[0].application_id or "",
            )
        )
        return paired[0][0]

    def _resolve_score(self, f, case) -> int:
        base = SCORE_TABLE[f.pattern_id]
        raw = max(base.payroll, base.billing, base.legal)
        # A-04 降格: シフト span_hours >= 24
        if f.pattern_id == "A-04" and case and case.shift and case.shift.span_hours >= 24:
            return 2
        # A-05 据え置き
        if f.pattern_id == "A-05" and case:
            cid = f.client_id if case.punches else ""
            if case.within_scheduled(cid):
                return 1
        return raw

    def _sort_key(self, sf):
        sev_rank = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
        return (
            sev_rank[sf.severity],
            sf.primary.date,
            sf.primary.staff_id,
            sf.primary.pattern_id,
        )
