"""skipped_records.csv 出力。"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


class SkippedRecordReporter:
    def __init__(self) -> None:
        self._records: list = []

    def register(self, rec) -> None:
        self._records.append(rec)

    def write(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["file", "line_no", "staff_id", "date", "reason"])
            for r in self._records:
                w.writerow([
                    r.file,
                    r.line_no,
                    r.staff_id or "",
                    r.date or "",
                    r.reason,
                ])

    def summary(self) -> dict:
        by_reason: dict = defaultdict(int)
        for r in self._records:
            by_reason[r.reason] += 1
        return {"total": len(self._records), "by_reason": dict(by_reason)}

    def records(self) -> list:
        return list(self._records)
