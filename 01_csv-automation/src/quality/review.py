"""Review collector (spec §5.14)."""
from __future__ import annotations
from dataclasses import dataclass, field

from ..normalize.timesheet import NormalizedResult


@dataclass(frozen=True)
class ReviewCell:
    source_row_no: int
    column: str
    raw_value: str
    reason: str


@dataclass
class ReviewLedger:
    cells: list[ReviewCell] = field(default_factory=list)

    @property
    def review_source_row_nos(self) -> frozenset[int]:
        return frozenset(c.source_row_no for c in self.cells)


class ReviewCollector:
    def collect(self, result: NormalizedResult) -> ReviewLedger:
        ledger = ReviewLedger()
        for row in result.rows:
            for col, cell in row.cells.items():
                if cell.is_review:
                    ledger.cells.append(
                        ReviewCell(
                            source_row_no=row.source_row_no,
                            column=col,
                            raw_value=cell.raw_value,
                            reason=cell.review_reason or "（理由未設定）",
                        )
                    )
        return ledger
