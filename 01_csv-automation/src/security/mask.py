"""PII masker (spec §5.21, §7.7)."""
from __future__ import annotations


def mask_name(name: str) -> str:
    if not name:
        return ""
    return name[0] + "***"


def mask_wage(wage: str) -> str:
    if not wage:
        return ""
    return "****"


def mask_row(row: dict[str, str]) -> dict[str, str]:
    masked = dict(row)
    if "name" in masked:
        masked["name"] = mask_name(masked["name"])
    if "hourly_wage" in masked:
        masked["hourly_wage"] = mask_wage(masked["hourly_wage"])
    return masked
