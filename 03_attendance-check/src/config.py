"""パス規約・締め日/営業日/対応期限の純粋計算。"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional, Protocol

from .errors import DateValidationError, OutputPathViolationError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class HolidayCalendar(Protocol):
    def is_business_day(self, d: date) -> bool: ...
    def business_days_between(self, start: date, end: date) -> int: ...


def parse_month(month_str: str) -> tuple:
    if not re.match(r"^\d{4}-\d{2}$", month_str):
        raise DateValidationError(f"--month は YYYY-MM 形式で指定してください: {month_str}")
    y, m = map(int, month_str.split("-"))
    if not (1 <= m <= 12):
        raise DateValidationError(f"月が不正: {month_str}")
    return y, m


def month_dir_name(month_str: str) -> str:
    y, m = parse_month(month_str)
    return f"{y:04d}{m:02d}"


def resolve_as_of_date(
    month_str: str, as_of_arg: Optional[str], today_jst: date
) -> date:
    """--as-of-date 未指定時: (月末締め日, today_jst) の早い方。"""
    if as_of_arg:
        try:
            return datetime.strptime(as_of_arg, "%Y-%m-%d").date()
        except ValueError as e:
            raise DateValidationError(
                f"--as-of-date は YYYY-MM-DD 形式で指定してください: {as_of_arg}"
            ) from e
    y, m = parse_month(month_str)
    last = date(y, m, calendar.monthrange(y, m)[1])
    return min(last, today_jst)


def resolve_response_deadline(month_str: str, holidays: HolidayCalendar) -> date:
    """月末締め日から2営業日前を逆算。"""
    y, m = parse_month(month_str)
    last = date(y, m, calendar.monthrange(y, m)[1])
    d = last
    count = 0
    while count < 2:
        d -= timedelta(days=1)
        if holidays.is_business_day(d):
            count += 1
    return d


def samples_dir(month_str: str) -> Path:
    return _PROJECT_ROOT / "samples" / month_dir_name(month_str)


def output_dir() -> Path:
    p = _PROJECT_ROOT / "out"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_root() -> Path:
    return _PROJECT_ROOT


def safe_join_output(base: Path, rel) -> Path:
    """out/ 配下を超えて書き込むのを防ぐ。"""
    candidate = (base / rel).resolve()
    base_real = base.resolve()
    try:
        candidate.relative_to(base_real)
    except ValueError as e:
        raise OutputPathViolationError(
            f"出力先が {base_real} の外を指しています: {candidate}"
        ) from e
    return candidate
