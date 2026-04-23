"""Timesheet normalizer (spec §5.13)."""
from __future__ import annotations
from dataclasses import dataclass

from ..io.loader import LoadedTimesheet
from ..mapping.inferencer import HeaderMapping
from ..schema.canonical import CANONICAL_COLUMNS, REQUIRED_COLUMNS, OPTIONAL_WITH_DEFAULT
from .date_parser import parse_date
from .number_parser import parse_wage, parse_minutes
from .text import normalize_text
from .time_parser import parse_time


@dataclass
class NormalizedCell:
    normalized_value: str
    raw_value: str
    is_review: bool
    review_reason: str | None = None


@dataclass
class NormalizedRow:
    source_row_no: int
    cells: dict[str, NormalizedCell]


@dataclass
class NormalizedResult:
    rows: list[NormalizedRow]


def _normalize_employee_id(raw: str) -> NormalizedCell:
    norm = normalize_text(raw or "")
    if not norm:
        return NormalizedCell("", raw or "", True, "必須項目が空欄")
    return NormalizedCell(norm, raw or "", False, None)


def _normalize_name(raw: str) -> NormalizedCell:
    norm = normalize_text(raw or "")
    if not norm:
        return NormalizedCell("", raw or "", True, "必須項目が空欄")
    return NormalizedCell(norm, raw or "", False, None)


def _normalize_work_date(raw: str) -> NormalizedCell:
    r = parse_date(raw or "")
    if r.is_valid and r.value is not None:
        return NormalizedCell(r.value, raw or "", False, None)
    return NormalizedCell("", raw or "", True, r.reason)


def _normalize_time(raw: str) -> NormalizedCell:
    r = parse_time(raw or "")
    if r.is_valid and r.value is not None:
        if r.is_24_hour:
            return NormalizedCell(r.value, raw or "", True, "24:00（要確認）")
        return NormalizedCell(r.value, raw or "", False, None)
    return NormalizedCell("", raw or "", True, r.reason)


def _normalize_break(raw: str) -> NormalizedCell:
    if not (raw or "").strip():
        return NormalizedCell(OPTIONAL_WITH_DEFAULT["break_minutes"], raw or "", False, None)
    r = parse_minutes(raw or "")
    if r.is_valid and r.value is not None:
        return NormalizedCell(str(r.value), raw or "", False, None)
    return NormalizedCell("", raw or "", True, r.reason)


def _normalize_wage(raw: str) -> NormalizedCell:
    r = parse_wage(raw or "")
    if r.is_valid and r.value is not None:
        return NormalizedCell(str(r.value), raw or "", False, None)
    return NormalizedCell("", raw or "", True, r.reason)


class TimesheetNormalizer:
    def normalize(
        self, loaded: LoadedTimesheet, mapping: HeaderMapping
    ) -> NormalizedResult:
        rows: list[NormalizedRow] = []
        for idx, raw_row in enumerate(loaded.rows):
            source_row_no = idx + 2  # header=1
            cells: dict[str, NormalizedCell] = {}
            for canonical in CANONICAL_COLUMNS:
                src_idx = mapping.canonical_to_source_index.get(canonical)
                if src_idx is None:
                    # Optional with default
                    if canonical in OPTIONAL_WITH_DEFAULT:
                        cells[canonical] = NormalizedCell(
                            OPTIONAL_WITH_DEFAULT[canonical], "", False, None
                        )
                    else:
                        cells[canonical] = NormalizedCell(
                            "", "", True, "列が未マッピング"
                        )
                    continue
                raw = raw_row[src_idx] if src_idx < len(raw_row) else ""
                if canonical == "employee_id":
                    cells[canonical] = _normalize_employee_id(raw)
                elif canonical == "name":
                    cells[canonical] = _normalize_name(raw)
                elif canonical == "work_date":
                    cells[canonical] = _normalize_work_date(raw)
                elif canonical in ("start_time", "end_time"):
                    cells[canonical] = _normalize_time(raw)
                elif canonical == "break_minutes":
                    cells[canonical] = _normalize_break(raw)
                elif canonical == "hourly_wage":
                    cells[canonical] = _normalize_wage(raw)

            # end < start check
            st = cells.get("start_time")
            et = cells.get("end_time")
            if st and et and st.normalized_value and et.normalized_value:
                if not et.is_review and not st.is_review:
                    # Compare HH:MM numerically (24:00 already review)
                    try:
                        sh, sm = map(int, st.normalized_value.split(":"))
                        eh, em = map(int, et.normalized_value.split(":"))
                        if (eh, em) < (sh, sm):
                            cells["end_time"] = NormalizedCell(
                                et.normalized_value,
                                et.raw_value,
                                True,
                                "終業が始業より前（日またぎは自動補正せず要確認）",
                            )
                    except ValueError:
                        pass

            rows.append(NormalizedRow(source_row_no=source_row_no, cells=cells))
        return NormalizedResult(rows=rows)
