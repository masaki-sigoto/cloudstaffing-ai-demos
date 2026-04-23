"""stdout サマリ表示。"""

from __future__ import annotations

import re

from ..models import Severity


def _display_name(raw: str) -> str:
    if not raw:
        return raw
    s = re.sub(r"\s+[A-Za-z0-9_\-]+$", "", raw.strip())
    return s or raw

_ANSI_RED = "\033[31m"
_ANSI_YEL = "\033[33m"
_ANSI_BLU = "\033[34m"
_ANSI_RESET = "\033[0m"
_ANSI_BOLD = "\033[1m"


def _sev_label(sev: Severity, no_color: bool) -> str:
    m = {Severity.HIGH: "高", Severity.MEDIUM: "中", Severity.LOW: "低"}
    if no_color:
        return m[sev]
    color = {Severity.HIGH: _ANSI_RED, Severity.MEDIUM: _ANSI_YEL, Severity.LOW: _ANSI_BLU}[sev]
    return f"{color}{m[sev]}{_ANSI_RESET}"


class SummaryRenderer:
    def render(
        self,
        scored: list,
        total_records: int,
        total_records_filtered: int,
        month: str,
        no_color: bool,
        filters: dict | None = None,
    ) -> str:
        high = sum(1 for s in scored if s.severity == Severity.HIGH)
        med = sum(1 for s in scored if s.severity == Severity.MEDIUM)
        low = sum(1 for s in scored if s.severity == Severity.LOW)
        flagged = high + med + low

        lines = []
        lines.append("================================================")
        lines.append(f"  勤怠チェック結果サマリ ({month} / 締め前)")
        lines.append("  派遣元: クロスリンクスタッフ株式会社（デモ）")
        lines.append("================================================")
        filt = ""
        if filters:
            parts = [f"{k}={v}" for k, v in filters.items()]
            if parts:
                filt = f"  ※ 絞込条件: {', '.join(parts)}\n"
        if total_records_filtered != total_records:
            lines.append(
                f"  全 {total_records} 件（フィルタ後 {total_records_filtered} 件）→ 要確認 {flagged} 件"
            )
        else:
            lines.append(f"  全 {total_records} 件 → 要確認 {flagged} 件")
        lines.append(
            f"    [{_sev_label(Severity.HIGH, no_color)}] {high} 件 / "
            f"[{_sev_label(Severity.MEDIUM, no_color)}] {med} 件 / "
            f"[{_sev_label(Severity.LOW, no_color)}] {low} 件"
        )
        lines.append("================================================")
        if filt:
            lines.append(filt.rstrip("\n"))

        # 重要度別一覧
        for sev, label in (
            (Severity.HIGH, "高"),
            (Severity.MEDIUM, "中"),
            (Severity.LOW, "低"),
        ):
            group = [s for s in scored if s.severity == sev]
            if not group:
                continue
            lines.append("")
            lines.append(f"▼ 重要度[{_sev_label(sev, no_color)}] {label} ({len(group)}件)")
            for i, sf in enumerate(group, start=1):
                p = sf.primary
                aps = sorted(set(p.approver_statuses)) if p.approver_statuses else []
                aps_text = " / ".join(aps) if aps else "-"
                lines.append(
                    f"  [{i}] {p.date.isoformat()} | {p.staff_name} ({p.staff_id})  "
                    f"(派遣先: {p.client_name} / {p.client_site})"
                )
                add = f"＋{','.join(sf.additional_patterns)}" if sf.additional_patterns else ""
                lines.append(
                    f"      パターン: {p.pattern_id} {p.pattern_name}{add}"
                )
                lines.append(f"      派遣先承認: {aps_text}")
                lines.append(f"      推奨アクション: {sf.recommended_action}")
                lines.append(
                    f"      担当コーディネーター: {_display_name(p.assignee_name) or p.assignee_id}"
                )

        return "\n".join(lines)
