"""派遣先事業所別チェックリスト。"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from ..models import Severity


class ClientSiteReport:
    def build(self, scored: list) -> dict:
        g: dict = defaultdict(list)
        for sf in scored:
            k = (sf.primary.client_id or "UNKNOWN", sf.primary.client_site or "unknown")
            g[k].append(sf)
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
        lines.append(f"■ 派遣先事業所別チェックリスト（{month}度）")
        lines.append(f"  対応期限: {response_deadline.isoformat()}")
        lines.append("")
        for (cid, site), findings in grouped.items():
            cname = findings[0].primary.client_name if findings else cid
            high = sum(1 for s in findings if s.severity == Severity.HIGH)
            med = sum(1 for s in findings if s.severity == Severity.MEDIUM)
            low = sum(1 for s in findings if s.severity == Severity.LOW)
            lines.append(
                f"[派遣先: {cname}（{cid}）／{site}]  対応 {len(findings)}件 "
                f"(高:{high} / 中:{med} / 低:{low})"
            )
            for sf in findings:
                p = sf.primary
                sev_lbl = {Severity.HIGH: "高", Severity.MEDIUM: "中", Severity.LOW: "低"}[sf.severity]
                aps = sorted(set(p.approver_statuses)) if p.approver_statuses else []
                aps_text = " / ".join(aps) if aps else "-"
                lines.append(
                    f"  - {p.date.isoformat()} | {p.staff_name} ({p.staff_id}) | "
                    f"{p.pattern_name} ({p.pattern_id}) [{sev_lbl}] / 承認:{aps_text}"
                )
                lines.append(f"      推奨: {sf.recommended_action}")
            lines.append("")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_path
