"""Counters and row-count validator (spec §5.16, §7.5)."""
from __future__ import annotations
from dataclasses import dataclass

from ..errors import RowCountMismatchError


@dataclass(frozen=True)
class Counters:
    input_rows: int
    output_rows: int
    dropped_rows: int
    review_rows: int


class RowCountValidator:
    def validate(self, counters: Counters, policy) -> None:
        p = str(getattr(policy, "value", policy))
        if p == "drop":
            if counters.input_rows != counters.output_rows + counters.dropped_rows:
                raise RowCountMismatchError(
                    message=(
                        f"drop: input={counters.input_rows} != "
                        f"output+dropped={counters.output_rows + counters.dropped_rows}"
                    ),
                )
            if counters.dropped_rows < counters.review_rows:
                raise RowCountMismatchError(
                    message=f"drop: dropped={counters.dropped_rows} < review={counters.review_rows}",
                )
        elif p == "keep":
            if counters.input_rows != counters.output_rows:
                raise RowCountMismatchError(
                    message=f"keep: input={counters.input_rows} != output={counters.output_rows}",
                )
            if counters.dropped_rows != 0:
                raise RowCountMismatchError(message="keep: dropped must be 0")
        elif p == "fail":
            if counters.input_rows != counters.output_rows:
                raise RowCountMismatchError(
                    message=f"fail: input={counters.input_rows} != output={counters.output_rows}",
                )
            if counters.dropped_rows != 0:
                raise RowCountMismatchError(
                    message=f"fail: dropped must be 0 (got {counters.dropped_rows})",
                )
