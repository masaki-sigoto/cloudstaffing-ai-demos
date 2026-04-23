"""applications.csv ローダー。"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models import LeaveApplication, SkippedRecord

logger = logging.getLogger(__name__)

_REQUIRED = [
    "application_id",
    "staff_id",
    "date",
    "type",
    "status",
    "applied_at",
    "approved_at",
]


def _parse_dt(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


class LeaveRequestLoader:
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
                    t = (row.get("type") or "").strip()
                    s = (row.get("status") or "").strip()
                    if t not in ("leave", "overtime") or s not in (
                        "pending",
                        "approved",
                        "rejected",
                    ):
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="applications.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="invalid type/status",
                            )
                        )
                        continue
                    dt = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
                    applied_at = _parse_dt(row.get("applied_at", ""))
                    approved_at = _parse_dt(row.get("approved_at", ""))
                    if applied_at is None:
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="applications.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="applied_at missing",
                            )
                        )
                        continue
                    out.append(
                        LeaveApplication(
                            application_id=row["application_id"].strip(),
                            staff_id=row["staff_id"].strip(),
                            date=dt,
                            type=t,
                            status=s,
                            applied_at=applied_at,
                            approved_at=approved_at,
                        )
                    )
                except Exception as e:
                    self.skip_reporter.register(
                        SkippedRecord(
                            file="applications.csv",
                            line_no=line_no,
                            staff_id=row.get("staff_id"),
                            date=row.get("date"),
                            reason=f"parse error: {e}",
                        )
                    )
        return out
