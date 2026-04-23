"""氏名イニシャル化（--mask-names）。"""

from __future__ import annotations

from dataclasses import replace

from ..models import Finding


def _mask_name(name: str) -> str:
    if not name:
        return name
    return f"{name[0]}."


class PiiMaskingFilter:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def apply(self, scored: list) -> list:
        if not self.enabled:
            return scored
        out = []
        for sf in scored:
            p = sf.primary
            new_primary = Finding(
                pattern_id=p.pattern_id,
                pattern_name=p.pattern_name,
                scope=p.scope,
                staff_id=p.staff_id,
                staff_name=_mask_name(p.staff_name),
                date=p.date,
                client_id=p.client_id,
                client_name=p.client_name,
                client_site=p.client_site,
                assignee_id=p.assignee_id,
                assignee_name=_mask_name(p.assignee_name),
                approver_statuses=p.approver_statuses,
                record_id=p.record_id,
                application_id=p.application_id,
                day_key=p.day_key,
                raw_context=p.raw_context,
            )
            sf.primary = new_primary
            out.append(sf)
        return out
