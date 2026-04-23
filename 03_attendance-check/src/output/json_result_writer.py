"""result_{YYYYMM}.json と run_summary_{YYYYMM}.json を出力。"""

from __future__ import annotations

import json
from pathlib import Path


class JsonResultWriter:
    def write(
        self,
        scored: list,
        meta: dict,
        summary: dict,
        output_path: Path,
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        items = []
        for sf in scored:
            p = sf.primary
            items.append(
                {
                    "finding_key": sf.finding_key,
                    "record_id": p.record_id,
                    "application_id": p.application_id,
                    "scope": p.scope.value,
                    "date": p.date.isoformat(),
                    "staff_id": p.staff_id,
                    "staff_name": p.staff_name,
                    "client_id": p.client_id,
                    "client_name": p.client_name,
                    "client_site": p.client_site,
                    "assignee_id": p.assignee_id,
                    "assignee_name": p.assignee_name,
                    "approver_statuses": list(p.approver_statuses),
                    "pattern_id": p.pattern_id,
                    "pattern_name": p.pattern_name,
                    "additional_patterns": list(sf.additional_patterns),
                    "severity": sf.severity.value,
                    "score_breakdown": {
                        "payroll": sf.score_breakdown.payroll,
                        "billing": sf.score_breakdown.billing,
                        "legal": sf.score_breakdown.legal,
                    },
                    "recommended_action": sf.recommended_action,
                }
            )
        payload = {
            "meta": meta,
            "summary": summary,
            "items": items,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
