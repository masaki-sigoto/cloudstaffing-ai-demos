"""Billing report generator (spec §4.7, §5.18)."""
from __future__ import annotations
import csv
from datetime import datetime
from pathlib import Path
from typing import Literal

from ..io.loader import LoadedTimesheet
from ..mapping.inferencer import HeaderMapping
from ..quality.policy import PolicyOutcome


class BillingReportGenerator:
    def generate(
        self,
        input_path: Path,
        output_path: Path,
        loaded: LoadedTimesheet,
        mapping: HeaderMapping,
        outcome: PolicyOutcome,
        policy,
        report_path: Path,
        format: Literal["md", "csv"] = "md",
    ) -> None:
        report_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "csv":
            with report_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(["source_row_no", "column", "raw_value", "reason"])
                for cell in outcome.ledger.cells:
                    writer.writerow([cell.source_row_no, cell.column, cell.raw_value, cell.reason])
            return

        # Markdown
        c = outcome.counters
        pol = str(getattr(policy, "value", policy))
        if pol == "drop":
            rel = (
                f"drop ポリシー `input=output+dropped` → "
                f"{c.input_rows} = {c.output_rows} + {c.dropped_rows} "
                f"{'✓' if c.input_rows == c.output_rows + c.dropped_rows else '✗'}"
            )
        elif pol == "keep":
            rel = (
                f"keep ポリシー `input=output` → {c.input_rows} = {c.output_rows} "
                f"{'✓' if c.input_rows == c.output_rows else '✗'}"
            )
        else:
            rel = f"fail ポリシー（review_rows={c.review_rows}）"

        lines: list[str] = []
        lines.append(f"# 変換レポート: {input_path.name}")
        lines.append("")
        lines.append(f"- 実行日時: {datetime.now().isoformat(timespec='seconds')}")
        lines.append(f"- 入力ファイル: {input_path}")
        lines.append(f"- 出力ファイル: {output_path}")
        lines.append(f"- 文字コード: {loaded.encoding}")
        lines.append(f"- ポリシー: {pol}")
        lines.append("")
        lines.append("## 件数サマリ")
        lines.append(f"- input_rows: {c.input_rows}")
        lines.append(f"- output_rows: {c.output_rows}")
        lines.append(f"- dropped_rows: {c.dropped_rows}")
        lines.append(f"- review_rows: {c.review_rows}")
        lines.append(f"- 関係式チェック: {rel}")
        lines.append("")
        lines.append("## ヘッダーマッピング結果")
        lines.append("| canonical | source | confidence | needs_review |")
        lines.append("|---|---|---|---|")
        for canonical, src in mapping.source_headers.items():
            conf = mapping.confidence.get(canonical, 0.0)
            nr = canonical in mapping.needs_review_columns
            lines.append(f"| {canonical} | {src} | {conf:.2f} | {str(nr).lower()} |")
        lines.append("")
        lines.append("## 要確認セル一覧")
        lines.append("（行番号は入力ファイル行番号。ヘッダー行=1、データ1行目=2）")
        lines.append("")
        if outcome.ledger.cells:
            lines.append("| 行 | 列 | 元の値 | 推定理由 |")
            lines.append("|---|---|---|---|")
            for cell in outcome.ledger.cells:
                raw = cell.raw_value if cell.raw_value != "" else "(空)"
                lines.append(f"| {cell.source_row_no} | {cell.column} | {raw} | {cell.reason} |")
        else:
            lines.append("要確認セルはありません。")
        lines.append("")
        lines.append("## 未マッピング入力ヘッダー")
        if mapping.unmapped_source_headers:
            for h in mapping.unmapped_source_headers:
                lines.append(f"- {h}")
        else:
            lines.append("- （なし）")
        lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
