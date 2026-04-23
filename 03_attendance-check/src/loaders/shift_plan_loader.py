"""shifts.csv ローダー。"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

from ..models import ShiftPlan, SkippedRecord

logger = logging.getLogger(__name__)


class ShiftPlanLoader:
    def __init__(self, skip_reporter) -> None:
        self.skip_reporter = skip_reporter

    def load(self, path: Path) -> list:
        out: list = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                return out
            for line_no, row in enumerate(reader, start=2):
                try:
                    d = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
                    ss = datetime.strptime(
                        row["scheduled_start"].strip(), "%Y-%m-%d %H:%M"
                    )
                    se = datetime.strptime(
                        row["scheduled_end"].strip(), "%Y-%m-%d %H:%M"
                    )
                    out.append(
                        ShiftPlan(
                            staff_id=row["staff_id"].strip(),
                            date=d,
                            scheduled_start=ss,
                            scheduled_end=se,
                        )
                    )
                except Exception as e:
                    self.skip_reporter.register(
                        SkippedRecord(
                            file="shifts.csv",
                            line_no=line_no,
                            staff_id=row.get("staff_id"),
                            date=row.get("date"),
                            reason=f"parse error: {e}",
                        )
                    )
        return out
