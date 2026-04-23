"""派遣元担当者別チェックリスト。"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from ..models import Severity


def _display_name(raw: str) -> str:
    if not raw:
        return raw
    s = re.sub(r"\s+[A-Za-z0-9_\-]+$", "", raw.strip())
    return s or raw


class DispatchCoordinatorReport:
    def build(self, scored: list) -> dict:
        g: dict = defaultdict(list)
        for sf in scored:
            aid = sf.primary.assignee_id or "UNKNOWN"
            g[aid].append(sf)
        return dict(sorted(g.items(), key=lambda kv: kv[0]))

    def write(
        self,
        grouped: dict,
        output_path: Path,
        response_deadline: date,
        month: str,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        lines.append(f"■ 派遣元コーディネーター別チェックリスト（{month}度）")
        lines.append(f"  対応期限: {response_deadline.isoformat()}（月次締め日の2営業日前）")
        lines.append("")
        for aid, findings in grouped.items():
            name = _display_name(findings[0].primary.assignee_name or "")
            high = sum(1 for s in findings if s.severity == Severity.HIGH)
            med = sum(1 for s in findings if s.severity == Severity.MEDIUM)
            low = sum(1 for s in findings if s.severity == Severity.LOW)
            lines.append(
                f"[担当: {name}（{aid}）]  対応 {len(findings)}件 "
                f"(高:{high} / 中:{med} / 低:{low})"
            )
            for sf in findings:
                p = sf.primary
                sev_lbl = {Severity.HIGH: "高", Severity.MEDIUM: "中", Severity.LOW: "低"}[sf.severity]
                lines.append(
                    f"  - {p.date.isoformat()} | {p.staff_name} ({p.staff_id}) "
                    f"(派遣先: {p.client_name}/{p.client_site}) | "
                    f"{p.pattern_name} ({p.pattern_id}) [{sev_lbl}]"
                )
                lines.append(f"      推奨アクション: {sf.recommended_action}")
            lines.append("")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_path
