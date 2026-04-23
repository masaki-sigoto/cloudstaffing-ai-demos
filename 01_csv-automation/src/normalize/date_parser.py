"""Date parser (spec §6.3)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from ..normalize.text import normalize_text

PATTERN_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
PATTERN_SLASH = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
PATTERN_REIWA_KANJI = re.compile(r"^令和(\d+)年(\d+)月(\d+)日$")
PATTERN_REIWA_ABBR = re.compile(r"^R(\d+)\.(\d+)\.(\d+)$")
PATTERN_DIGITS_8 = re.compile(r"^(\d{4})(\d{2})(\d{2})$")

REIWA_BASE_YEAR = 2018


@dataclass(frozen=True)
class DateParseResult:
    value: Optional[str]
    is_valid: bool
    reason: str


def _validate(y: int, mo: int, d: int) -> DateParseResult:
    if not (1 <= mo <= 12):
        return DateParseResult(None, False, f"月が不正（{mo}月は存在しない）")
    try:
        dt = date(y, mo, d)
    except ValueError:
        return DateParseResult(None, False, f"日付が実在しない: {y}-{mo}-{d}")
    return DateParseResult(dt.strftime("%Y-%m-%d"), True, "")


def parse_date(raw: str) -> DateParseResult:
    s = normalize_text(raw or "")
    if not s:
        return DateParseResult(None, False, "日付が空欄")

    m = PATTERN_ISO.match(s)
    if m:
        y, mo, d = map(int, m.groups())
        return _validate(y, mo, d)
    m = PATTERN_SLASH.match(s)
    if m:
        y, mo, d = map(int, m.groups())
        return _validate(y, mo, d)
    m = PATTERN_REIWA_KANJI.match(s)
    if m:
        ry, mo, d = map(int, m.groups())
        return _validate(REIWA_BASE_YEAR + ry, mo, d)
    m = PATTERN_REIWA_ABBR.match(s)
    if m:
        ry, mo, d = map(int, m.groups())
        return _validate(REIWA_BASE_YEAR + ry, mo, d)
    m = PATTERN_DIGITS_8.match(s)
    if m:
        y, mo, d = map(int, m.groups())
        return _validate(y, mo, d)

    return DateParseResult(None, False, f"認識できない日付形式: {raw}")
