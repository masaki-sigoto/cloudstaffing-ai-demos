"""Encoding detection (spec §5.3, §6.1)."""
from __future__ import annotations
from pathlib import Path

from ..errors import EncodingDetectionError


def detect_encoding(path: Path) -> str:
    data = path.read_bytes()

    if data.startswith(b"\xEF\xBB\xBF"):
        try:
            data.decode("utf-8-sig", errors="strict")
            return "utf-8-sig"
        except UnicodeDecodeError:
            pass

    try:
        data.decode("utf-8", errors="strict")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    try:
        data.decode("cp932", errors="strict")
        return "cp932"
    except UnicodeDecodeError:
        pass

    raise EncodingDetectionError(
        message="UTF-8/CP932 いずれでもデコードできませんでした",
        hint="ファイルの文字コードを UTF-8 にしてから再実行してください",
    )
