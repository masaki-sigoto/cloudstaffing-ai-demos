"""Error policy applier (spec §5.15, §7.6)."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum

from ..normalize.timesheet import NormalizedResult
from ..schema.canonical import CANONICAL_COLUMNS
from .counters import Counters
from .review import ReviewLedger


class ErrorPolicy(str, Enum):
    DROP = "drop"
    KEEP = "keep"
    FAIL = "fail"


@dataclass
class OutputRow:
    source_row_no: int
    output_row_no: int
    has_review: bool
    review_columns: list[str] = field(default_factory=list)
    values: dict[str, str] = field(default_factory=dict)


@dataclass
class PolicyOutcome:
    output_rows: list[OutputRow]
    ledger: ReviewLedger
    counters: Counters
    halted: bool = False


class ErrorPolicyApplier:
    def apply(
        self,
        result: NormalizedResult,
        ledger: ReviewLedger,
        policy: ErrorPolicy,
    ) -> PolicyOutcome:
        review_rows = ledger.review_source_row_nos
        input_rows_count = len(result.rows)

        if policy == ErrorPolicy.DROP:
            out_rows: list[OutputRow] = []
            out_no = 2  # data starts at line 2 (header=1)
            for row in result.rows:
                if row.source_row_no in review_rows:
                    continue
                values = {c: row.cells[c].normalized_value for c in CANONICAL_COLUMNS if c in row.cells}
                out_rows.append(OutputRow(
                    source_row_no=row.source_row_no,
                    output_row_no=out_no,
                    has_review=False,
                    review_columns=[],
                    values=values,
                ))
                out_no += 1
            counters = Counters(
                input_rows=input_rows_count,
                output_rows=len(out_rows),
                dropped_rows=len(review_rows),
                review_rows=len(review_rows),
            )
            return PolicyOutcome(output_rows=out_rows, ledger=ledger, counters=counters)

        elif policy == ErrorPolicy.KEEP:
            out_rows = []
            out_no = 2
            for row in result.rows:
                review_cols = [c for c, cell in row.cells.items() if cell.is_review]
                has_review = bool(review_cols)
                values: dict[str, str] = {}
                for c in CANONICAL_COLUMNS:
                    cell = row.cells.get(c)
                    if cell is None:
                        values[c] = ""
                    elif cell.is_review:
                        values[c] = cell.raw_value
                    else:
                        values[c] = cell.normalized_value
                out_rows.append(OutputRow(
                    source_row_no=row.source_row_no,
                    output_row_no=out_no,
                    has_review=has_review,
                    review_columns=review_cols,
                    values=values,
                ))
                out_no += 1
            counters = Counters(
                input_rows=input_rows_count,
                output_rows=len(out_rows),
                dropped_rows=0,
                review_rows=len(review_rows),
            )
            return PolicyOutcome(output_rows=out_rows, ledger=ledger, counters=counters)

        elif policy == ErrorPolicy.FAIL:
            if len(review_rows) > 0:
                counters = Counters(
                    input_rows=input_rows_count,
                    output_rows=0,
                    dropped_rows=0,
                    review_rows=len(review_rows),
                )
                return PolicyOutcome(output_rows=[], ledger=ledger, counters=counters, halted=True)
            out_rows = []
            out_no = 2
            for row in result.rows:
                values = {c: row.cells[c].normalized_value for c in CANONICAL_COLUMNS if c in row.cells}
                out_rows.append(OutputRow(
                    source_row_no=row.source_row_no,
                    output_row_no=out_no,
                    has_review=False,
                    review_columns=[],
                    values=values,
                ))
                out_no += 1
            counters = Counters(
                input_rows=input_rows_count,
                output_rows=len(out_rows),
                dropped_rows=0,
                review_rows=0,
            )
            return PolicyOutcome(output_rows=out_rows, ledger=ledger, counters=counters)

        else:
            raise ValueError(f"unknown policy: {policy}")
