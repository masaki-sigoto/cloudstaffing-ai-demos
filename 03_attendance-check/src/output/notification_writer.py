"""担当者別通知ファイル out/notifications/{assignee_id}_{slug}.txt。"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ..models import Severity


def _display_name(raw: str) -> str:
    """通知本文・チェックリスト表示用: 末尾の半角英数 slug を削ぎ、日本語部分のみ残す。"""
    if not raw:
        return raw
    s = re.sub(r"\s+[A-Za-z0-9_\-]+$", "", raw.strip())
    return s or raw


class NotificationWriter:
    @staticmethod
    def sanitize_slug(name: str) -> str:
        s = re.sub(r"[^A-Za-z0-9-]", "", name or "")
        return s or "unknown"

    def write(
        self,
        grouped: dict,
        response_deadline: date,
        output_dir: Path,
        month: str,
    ) -> list:
        output_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for aid, findings in grouped.items():
            raw_name = findings[0].primary.assignee_name if findings else ""
            slug = self.sanitize_slug(raw_name)
            display = _display_name(raw_name)
            path = output_dir / f"{aid}_{slug}.txt"
            lines = []
            lines.append(f"宛先: {display} 様（派遣元コーディネーター）")
            lines.append(
                f"件名: [要対応] {month}度 スタッフ勤怠チェック結果"
                f"（担当スタッフ {len(findings)}件 / 月次締め前）"
            )
            lines.append("")
            lines.append("お疲れさまです。月次締め前勤怠チェックが完了しました。")
            lines.append("以下レコードについて、派遣先承認者・スタッフ本人と調整のうえ、")
            lines.append("締め対応期限までに処理をお願いします。")
            lines.append("")

            for sev, title in (
                (Severity.HIGH, "■ 重要度[高]"),
                (Severity.MEDIUM, "■ 重要度[中]"),
                (Severity.LOW, "■ 重要度[低]"),
            ):
                group = [s for s in findings if s.severity == sev]
                if not group:
                    continue
                note = " （給与・請求直撃リスク）" if sev == Severity.HIGH else ""
                lines.append(f"{title} {len(group)}件{note}")
                for sf in group:
                    p = sf.primary
                    lines.append(
                        f"  - {p.date.isoformat()} {p.staff_name} "
                        f"(派遣先: {p.client_name} / {p.client_site}): {p.pattern_name}"
                    )
                    lines.append(f"      → {sf.recommended_action}")
                lines.append("")

            lines.append(
                f"対応期限: {response_deadline.isoformat()}（月次締め日の2営業日前）"
            )
            lines.append("詳細は out/checklist/ 配下のチェックリストをご参照ください。")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            written.append(path)
        return written
