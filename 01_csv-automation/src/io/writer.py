"""CSV writer (spec §5.17)."""
from __future__ import annotations
import csv
from pathlib import Path

from ..schema.canonical import CANONICAL_COLUMNS


class TimesheetWriter:
    def write(self, output_rows, out_path: Path, policy) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        header = list(CANONICAL_COLUMNS)
        keep_mode = (str(getattr(policy, "value", policy)) == "keep")
        if keep_mode:
            header = header + ["__needs_review"]
        with out_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(header)
            for r in output_rows:
                row = [r.values.get(c, "") for c in CANONICAL_COLUMNS]
                if keep_mode:
                    row.append("1" if r.has_review else "0")
                writer.writerow(row)

    def write_sidecar(self, output_rows, sidecar_path: Path) -> None:
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        with sidecar_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["output_row_no", "source_row_no", "has_review", "review_columns"])
            for r in output_rows:
                writer.writerow([
                    r.output_row_no,
                    r.source_row_no,
                    "1" if r.has_review else "0",
                    "|".join(r.review_columns),
                ])
