"""Time parser (spec §6.4)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from ..normalize.text import normalize_text

PATTERN_HHMM = re.compile(r"^(\d{1,2}):(\d{1,2})$")
PATTERN_H_KANJI_M_KANJI = re.compile(r"^(\d{1,2})時(\d{1,2})分$")
PATTERN_H_KANJI = re.compile(r"^(\d{1,2})時$")


@dataclass(frozen=True)
class TimeParseResult:
    value: Optional[str]
    is_valid: bool
    is_24_hour: bool
    reason: str


def parse_time(raw: str) -> TimeParseResult:
    s = normalize_text(raw or "").replace("：", ":")
    if not s:
        return TimeParseResult(None, False, False, "時刻が空欄")

    m = PATTERN_HHMM.match(s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h == 24 and mi == 0:
            return TimeParseResult("24:00", True, True, "24:00（要確認）")
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return TimeParseResult(f"{h:02d}:{mi:02d}", True, False, "")
        return TimeParseResult(None, False, False, f"時刻範囲外: {raw}")

    m = PATTERN_H_KANJI_M_KANJI.match(s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return TimeParseResult(f"{h:02d}:{mi:02d}", True, False, "")
        return TimeParseResult(None, False, False, f"時刻範囲外: {raw}")

    m = PATTERN_H_KANJI.match(s)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return TimeParseResult(f"{h:02d}:00", True, False, "")
        if h == 24:
            return TimeParseResult("24:00", True, True, "24:00（要確認）")
        return TimeParseResult(None, False, False, f"時刻範囲外: {raw}")

    return TimeParseResult(None, False, False, f"認識できない時刻形式: {raw}")
