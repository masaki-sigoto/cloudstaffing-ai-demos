"""Synonym dictionary (spec §5.7)."""
from __future__ import annotations
from typing import Final

SYNONYMS: Final[dict[str, list[str]]] = {
    "employee_id": [
        "従業員id", "社員コード", "スタッフno", "スタッフno.",
        "スタッフコード", "従業員番号", "社員番号", "従業員コード",
        "emp_id", "employee_id", "empid",
    ],
    "name": [
        "氏名", "名前", "スタッフ名", "従業員名",
        "ﾅﾏｴ", "ナマエ", "name",
    ],
    "work_date": [
        "勤務日", "日付", "出勤日", "作業日", "就業日",
        "date", "work_date", "workdate",
    ],
    "start_time": [
        "始業", "開始", "出勤時刻", "開始時刻", "始業時刻",
        "start", "start_time",
    ],
    "end_time": [
        "終業", "終了", "退勤時刻", "終了時刻", "終業時刻",
        "end", "end_time",
    ],
    "break_minutes": [
        "休憩", "休憩時間", "休憩（分）", "休憩分", "休憩(分)",
        "break", "break_minutes",
    ],
    "hourly_wage": [
        "時給", "時間給", "単価", "時給単価", "給与",
        "hourly_wage", "wage", "hourly",
    ],
}
