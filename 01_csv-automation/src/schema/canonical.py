"""Canonical schema constants (spec §4.1)."""
from __future__ import annotations
from typing import Final

CANONICAL_COLUMNS: Final[list[str]] = [
    "employee_id",
    "name",
    "work_date",
    "start_time",
    "end_time",
    "break_minutes",
    "hourly_wage",
]

REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset({
    "employee_id", "name", "work_date",
    "start_time", "end_time", "hourly_wage",
})

OPTIONAL_WITH_DEFAULT: Final[dict[str, str]] = {"break_minutes": "0"}

PII_MASKED_COLUMNS: Final[frozenset[str]] = frozenset({"name", "hourly_wage"})
