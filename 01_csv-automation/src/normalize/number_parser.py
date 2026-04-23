"""Number parser for wage/minutes (spec §5.12)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from ..normalize.text import normalize_text


@dataclass(frozen=True)
class NumberParseResult:
    value: Optional[int]
    is_valid: bool
    reason: str


def parse_wage(raw: str) -> NumberParseResult:
    s = normalize_text(raw or "")
    if not s:
        return NumberParseResult(None, False, "時給が空欄")
    # Strip ¥, 円, commas, whitespace
    s2 = s.replace("¥", "").replace("円", "").replace(",", "").strip()
    if not s2:
        return NumberParseResult(None, False, "数値に変換できない")
    try:
        n = int(s2)
    except ValueError:
        return NumberParseResult(None, False, "数値に変換できない")
    if n < 0:
        return NumberParseResult(None, False, "時給が負値")
    return NumberParseResult(n, True, "")


_H_M_PATTERN = re.compile(r"^(\d+)時間(\d+)分$")
_H_PATTERN = re.compile(r"^(\d+)時間$")
_M_PATTERN = re.compile(r"^(\d+)分$")


def parse_minutes(raw: str) -> NumberParseResult:
    s = normalize_text(raw or "")
    if not s:
        # Optional with default handled upstream; here empty is valid as None-signal
        return NumberParseResult(None, False, "休憩が空欄")
    m = _H_M_PATTERN.match(s)
    if m:
        return NumberParseResult(int(m.group(1)) * 60 + int(m.group(2)), True, "")
    m = _H_PATTERN.match(s)
    if m:
        return NumberParseResult(int(m.group(1)) * 60, True, "")
    m = _M_PATTERN.match(s)
    if m:
        return NumberParseResult(int(m.group(1)), True, "")
    s2 = s.replace(",", "").strip()
    try:
        n = int(s2)
    except ValueError:
        return NumberParseResult(None, False, "数値に変換できない")
    if n < 0:
        return NumberParseResult(None, False, "休憩分が負値")
    return NumberParseResult(n, True, "")
