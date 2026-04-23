"""holidays.csv ローダー。存在しない場合は土日のみ非営業日のカレンダーを返す。"""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HolidayCalendarImpl:
    def __init__(self, holiday_set: set) -> None:
        self._holiday_set = holiday_set

    def is_business_day(self, d: date) -> bool:
        if d.weekday() >= 5:
            return False
        if d in self._holiday_set:
            return False
        return True

    def business_days_between(self, start: date, end: date) -> int:
        """(start, end] の営業日数。"""
        if end <= start:
            return 0
        d = start + timedelta(days=1)
        n = 0
        while d <= end:
            if self.is_business_day(d):
                n += 1
            d += timedelta(days=1)
        return n


class HolidayCalendarLoader:
    def load(self, path: Optional[Path]) -> HolidayCalendarImpl:
        if path is None or not path.exists():
            return HolidayCalendarImpl(set())
        holiday_set: set = set()
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw = (row.get("date") or "").strip()
                if not raw:
                    continue
                try:
                    holiday_set.add(datetime.strptime(raw, "%Y-%m-%d").date())
                except ValueError:
                    logger.warning(
                        "holidays.csv: 日付パース失敗 '%s'（skip）", raw
                    )
        return HolidayCalendarImpl(holiday_set)
