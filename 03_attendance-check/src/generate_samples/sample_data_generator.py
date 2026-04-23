"""10パターンが最低1件ずつ混入する派遣業界リアルなダミーCSVを生成。"""

from __future__ import annotations

import csv
import random
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path

from ..config import parse_month
from ..errors import DemoError

# 派遣元コーディネーター（slug が通知ファイル名に入るためローマ字併記）
_ASSIGNEES = [
    ("U-001", "佐藤 sato"),
    ("U-002", "高橋 takahashi"),
    ("U-003", "渡辺 watanabe"),
]

# 派遣先企業・事業所
_CLIENTS = [
    ("CL-001", "ABC商事", ["本社", "大阪支店"]),
    ("CL-002", "XYZ物流", ["東京営業所"]),
    ("CL-003", "DEF製造", ["栃木工場"]),
]

# スタッフ（日本人氏名らしく）
_STAFF_NAMES = [
    "鈴木太郎", "佐々木花子", "田中次郎", "山田美咲", "小林健一",
    "伊藤真美", "加藤健太", "中村由美", "松本翔", "井上千夏",
    "木村悠", "斎藤恵子", "清水大輔", "山口直樹", "林奈々",
    "森さやか", "池田亮", "橋本愛", "石川剛", "岡田涼子",
]


class SampleDataGenerator:
    def __init__(self, seed: int = 42, anomaly_rate: float = 0.15) -> None:
        self.seed = seed
        self.anomaly_rate = anomaly_rate

    def generate(
        self,
        month: str,
        count: int,
        output_dir: Path,
        overwrite: bool,
    ) -> None:
        if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
            raise DemoError(
                f"{output_dir} に既存ファイルがあります（--overwrite 未指定のため中断）"
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        rng = random.Random(self.seed)
        y, m = parse_month(month)
        last_day = monthrange(y, m)[1]

        # スタッフを count 件分アサイン
        staff_count = min(count, len(_STAFF_NAMES))
        staff_list = []
        for i in range(staff_count):
            sid = f"S-{1001 + i:04d}"
            name = _STAFF_NAMES[i]
            # アサインクライアント（1スタッフ=1案件が主軸、一部ランダム切替）
            cidx = i % len(_CLIENTS)
            cid, cname, sites = _CLIENTS[cidx]
            site = sites[i % len(sites)]
            aid, aname = _ASSIGNEES[i % len(_ASSIGNEES)]
            staff_list.append(
                {
                    "staff_id": sid,
                    "staff_name": name,
                    "client_id": cid,
                    "client_name": cname,
                    "client_site": site,
                    "assignee_id": aid,
                    "assignee_name": aname,
                }
            )

        timesheet_rows: list = []
        applications_rows: list = []
        shifts_rows: list = []

        # 1ヶ月分の営業日（土日を除く）について打刻・シフトを発行
        for day in range(1, last_day + 1):
            d = date(y, m, day)
            if d.weekday() >= 5:
                continue
            for st in staff_list:
                # 通常の打刻
                ss = datetime(y, m, day, 9, 0)
                se = datetime(y, m, day, 18, 0)
                shifts_rows.append(
                    {
                        "staff_id": st["staff_id"],
                        "date": d.isoformat(),
                        "scheduled_start": ss.strftime("%Y-%m-%d %H:%M"),
                        "scheduled_end": se.strftime("%Y-%m-%d %H:%M"),
                    }
                )
                rec_id = f"T-{d.isoformat()}-{st['staff_id']}"
                ci = datetime(y, m, day, 9, rng.randint(0, 10))
                co = datetime(y, m, day, 18, rng.randint(0, 15))
                row = {
                    "record_id": rec_id,
                    "staff_id": st["staff_id"],
                    "staff_name": st["staff_name"],
                    "client_id": st["client_id"],
                    "client_name": st["client_name"],
                    "client_site": st["client_site"],
                    "date": d.isoformat(),
                    "clock_in": ci.strftime("%Y-%m-%d %H:%M"),
                    "clock_out": co.strftime("%Y-%m-%d %H:%M"),
                    "break_minutes": 60,
                    "assignee_id": st["assignee_id"],
                    "assignee_name": st["assignee_name"],
                }
                timesheet_rows.append(row)

        # 異常を意図的に混入（各A-01〜A-10を最低1件）
        self._inject_anomalies(
            rng, timesheet_rows, applications_rows, shifts_rows, staff_list, y, m
        )

        # 書き出し
        self._write_csv(
            output_dir / "timesheet.csv",
            [
                "record_id", "staff_id", "staff_name", "client_id", "client_name",
                "client_site", "date", "clock_in", "clock_out", "break_minutes",
                "assignee_id", "assignee_name",
            ],
            timesheet_rows,
        )
        self._write_csv(
            output_dir / "applications.csv",
            ["application_id", "staff_id", "date", "type", "status",
             "applied_at", "approved_at"],
            applications_rows,
        )
        self._write_csv(
            output_dir / "shifts.csv",
            ["staff_id", "date", "scheduled_start", "scheduled_end"],
            shifts_rows,
        )
        # クライアントマスター（参照用）
        clients_rows = []
        for cid, cname, sites in _CLIENTS:
            for s in sites:
                clients_rows.append({"client_id": cid, "client_name": cname, "client_site": s})
        self._write_csv(
            output_dir / "clients.csv",
            ["client_id", "client_name", "client_site"],
            clients_rows,
        )

    def _inject_anomalies(
        self, rng, timesheet_rows, applications_rows, shifts_rows, staff_list, y, m
    ) -> None:
        # A-01: 退勤打刻漏れ (S-1001, 15日)
        self._find_and_edit(
            timesheet_rows, staff_list[0]["staff_id"], f"{y}-{m:02d}-15",
            lambda r: r.update({"clock_out": ""}),
        )
        # A-02: 出勤打刻漏れ (S-1002, 16日)
        self._find_and_edit(
            timesheet_rows, staff_list[1]["staff_id"], f"{y}-{m:02d}-16",
            lambda r: r.update({"clock_in": ""}),
        )
        # A-03: 休憩未入力 (S-1003, 14日): 8h超勤務で break 30分
        self._find_and_edit(
            timesheet_rows, staff_list[2]["staff_id"], f"{y}-{m:02d}-14",
            lambda r: r.update({
                "clock_in": f"{y}-{m:02d}-14 09:00",
                "clock_out": f"{y}-{m:02d}-14 19:00",
                "break_minutes": 30,
            }),
        )
        # A-04: 連続24h超 (S-1004, 10日→11日にまたぐ)
        self._find_and_edit(
            timesheet_rows, staff_list[3]["staff_id"], f"{y}-{m:02d}-10",
            lambda r: r.update({
                "clock_in": f"{y}-{m:02d}-10 08:00",
                "clock_out": f"{y}-{m:02d}-11 09:00",
            }),
        )
        # A-05: 1日複数回の出退勤 (S-1005, 13日) -> 追加ペア行
        sid = staff_list[4]["staff_id"]
        dstr = f"{y}-{m:02d}-13"
        timesheet_rows.append({
            "record_id": f"T-{dstr}-{sid}-2",
            "staff_id": sid,
            "staff_name": staff_list[4]["staff_name"],
            "client_id": staff_list[4]["client_id"],
            "client_name": staff_list[4]["client_name"],
            "client_site": staff_list[4]["client_site"],
            "date": dstr,
            "clock_in": f"{dstr} 19:00",
            "clock_out": f"{dstr} 22:00",
            "break_minutes": 0,
            "assignee_id": staff_list[4]["assignee_id"],
            "assignee_name": staff_list[4]["assignee_name"],
        })
        # A-06 分岐1（休暇×打刻矛盾） (S-1006, 17日)
        sid = staff_list[5]["staff_id"]
        applications_rows.append({
            "application_id": "AP-0001",
            "staff_id": sid,
            "date": f"{y}-{m:02d}-17",
            "type": "leave",
            "status": "approved",
            "applied_at": f"{y}-{m:02d}-10 10:00",
            "approved_at": f"{y}-{m:02d}-11 09:00",
        })
        # A-06 分岐2（残業申請漏れ） (S-1007, 20日): 10時間勤務で申請なし
        self._find_and_edit(
            timesheet_rows, staff_list[6]["staff_id"], f"{y}-{m:02d}-20",
            lambda r: r.update({
                "clock_in": f"{y}-{m:02d}-20 09:00",
                "clock_out": f"{y}-{m:02d}-20 20:30",
                "break_minutes": 60,
            }),
        )
        # A-07: pending滞留 (S-1008)。前月20日申請、status=pending
        applied_dt = date(y, m, 1) - timedelta(days=10)
        applications_rows.append({
            "application_id": "AP-0002",
            "staff_id": staff_list[7]["staff_id"],
            "date": f"{y}-{m:02d}-22",
            "type": "overtime",
            "status": "pending",
            "applied_at": f"{applied_dt.isoformat()} 11:00",
            "approved_at": "",
        })
        # A-08: 深夜打刻（シフト外）(S-1009, 24日) 23:30打刻
        self._find_and_edit(
            timesheet_rows, staff_list[8]["staff_id"], f"{y}-{m:02d}-24",
            lambda r: r.update({
                "clock_in": f"{y}-{m:02d}-24 09:00",
                "clock_out": f"{y}-{m:02d}-24 23:30",
                "break_minutes": 60,
            }),
        )
        # A-09: シフト大幅乖離 (S-1010, 27日) 11:30出勤（9:00予定から+150分）
        self._find_and_edit(
            timesheet_rows, staff_list[9]["staff_id"], f"{y}-{m:02d}-27",
            lambda r: r.update({
                "clock_in": f"{y}-{m:02d}-27 11:30",
                "clock_out": f"{y}-{m:02d}-27 20:30",
                "break_minutes": 60,
            }),
        )
        # A-10: 重複打刻（S-1011, 28日）2分差で追加行
        sid = staff_list[10]["staff_id"] if len(staff_list) > 10 else staff_list[0]["staff_id"]
        dstr = f"{y}-{m:02d}-28"
        base = [r for r in timesheet_rows if r["staff_id"] == sid and r["date"] == dstr]
        if base:
            orig = base[0]
            ci_orig = datetime.strptime(orig["clock_in"], "%Y-%m-%d %H:%M")
            timesheet_rows.append({
                "record_id": f"T-{dstr}-{sid}-dup",
                "staff_id": sid,
                "staff_name": orig["staff_name"],
                "client_id": orig["client_id"],
                "client_name": orig["client_name"],
                "client_site": orig["client_site"],
                "date": dstr,
                "clock_in": (ci_orig + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M"),
                "clock_out": orig["clock_out"],
                "break_minutes": 60,
                "assignee_id": orig["assignee_id"],
                "assignee_name": orig["assignee_name"],
            })

    def _find_and_edit(self, rows, staff_id, date_str, mutator):
        for r in rows:
            if r["staff_id"] == staff_id and r["date"] == date_str:
                mutator(r)
                return

    def _write_csv(self, path: Path, columns: list, rows: list) -> None:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=columns)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in columns})
