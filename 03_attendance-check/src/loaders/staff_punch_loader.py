"""timesheet.csv ローダー（1行=1出退勤ペア）。"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..errors import InputSchemaError
from ..models import PunchRecord, SkippedRecord

logger = logging.getLogger(__name__)

_REQUIRED = [
    "record_id",
    "staff_id",
    "staff_name",
    "client_id",
    "client_name",
    "client_site",
    "date",
    "clock_in",
    "clock_out",
    "break_minutes",
    "assignee_id",
    "assignee_name",
]


def _parse_dt(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


class StaffPunchLoader:
    def __init__(self, skip_reporter) -> None:
        self.skip_reporter = skip_reporter

    def load(self, path: Path) -> list:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise InputSchemaError("timesheet.csv: ヘッダがありません")
            missing = [c for c in _REQUIRED if c not in reader.fieldnames]
            if missing:
                raise InputSchemaError(
                    f"timesheet.csv: 必須列が欠落 {missing}"
                )
            out: list = []
            for line_no, row in enumerate(reader, start=2):
                try:
                    client_site = (row.get("client_site") or "").strip()
                    if not client_site:
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="timesheet.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="client_site missing, filled as unknown",
                            )
                        )
                        client_site = "unknown"
                    try:
                        date_val = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
                    except Exception:
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="timesheet.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="date parse error",
                            )
                        )
                        continue
                    try:
                        ci = _parse_dt(row.get("clock_in", ""))
                        co = _parse_dt(row.get("clock_out", ""))
                    except ValueError:
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="timesheet.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="datetime parse error",
                            )
                        )
                        continue
                    if ci and co and co < ci:
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="timesheet.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="clock_out before clock_in",
                            )
                        )
                        continue
                    try:
                        bm = int((row.get("break_minutes") or "0").strip())
                    except ValueError:
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="timesheet.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="break_minutes parse error",
                            )
                        )
                        continue
                    if bm < 0:
                        self.skip_reporter.register(
                            SkippedRecord(
                                file="timesheet.csv",
                                line_no=line_no,
                                staff_id=row.get("staff_id"),
                                date=row.get("date"),
                                reason="break_minutes negative",
                            )
                        )
                        continue
                    out.append(
                        PunchRecord(
                            record_id=row["record_id"].strip(),
                            staff_id=row["staff_id"].strip(),
                            staff_name=row["staff_name"].strip(),
                            client_id=row["client_id"].strip(),
                            client_name=(row.get("client_name") or row["client_id"]).strip(),
                            client_site=client_site,
                            date=date_val,
                            clock_in=ci,
                            clock_out=co,
                            break_minutes=bm,
                            assignee_id=row["assignee_id"].strip(),
                            assignee_name=row["assignee_name"].strip(),
                        )
                    )
                except KeyError as e:
                    self.skip_reporter.register(
                        SkippedRecord(
                            file="timesheet.csv",
                            line_no=line_no,
                            staff_id=None,
                            date=None,
                            reason=f"missing column: {e}",
                        )
                    )
        return out
