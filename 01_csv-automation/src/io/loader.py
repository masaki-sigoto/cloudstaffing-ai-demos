"""CSV loader (spec §5.5)."""
from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path

from ..errors import DialectDetectionError, InputValidationError
from .encoding import detect_encoding


@dataclass(frozen=True)
class Dialect:
    delimiter: str
    lineterminator: str


@dataclass
class LoadedTimesheet:
    headers: list[str]
    rows: list[list[str]]
    encoding: str
    dialect: Dialect
    source_path: Path


class TimesheetLoader:
    def load(self, path: Path) -> LoadedTimesheet:
        if not path.exists():
            raise InputValidationError(
                message=f"ファイルが存在しません: {path}",
                hint="--input のパスを確認してください",
            )
        try:
            encoding = detect_encoding(path)
            text = path.read_text(encoding=encoding)
        except OSError as e:
            raise InputValidationError(
                message=f"ファイル読込エラー: {e}", hint="権限・パスを確認してください"
            ) from e

        sample = text[:8192]
        delimiter = ","
        lineterm = "\r\n" if "\r\n" in text else "\n"
        try:
            sn = csv.Sniffer().sniff(sample, delimiters=",\t;")
            delimiter = sn.delimiter
        except csv.Error:
            # Fallback: count candidates in first line
            first_line = text.splitlines()[0] if text else ""
            for cand in (",", "\t", ";"):
                if cand in first_line:
                    delimiter = cand
                    break

        dialect = Dialect(delimiter=delimiter, lineterminator=lineterm)

        # Read rows using csv.reader on the decoded text
        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        all_rows = [r for r in reader if r]  # drop fully empty lines

        if not all_rows:
            raise DialectDetectionError(
                message="空のCSVファイルです", hint="ヘッダー行が必要です"
            )

        headers = all_rows[0]
        rows = all_rows[1:]
        return LoadedTimesheet(
            headers=headers,
            rows=rows,
            encoding=encoding,
            dialect=dialect,
            source_path=path,
        )
