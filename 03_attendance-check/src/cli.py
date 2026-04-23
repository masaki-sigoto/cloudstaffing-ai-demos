"""CLI パーサと二段ガード／サブコマンド本処理。"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from .config import (
    month_dir_name,
    output_dir,
    parse_month,
    resolve_as_of_date,
    resolve_response_deadline,
    samples_dir,
)
from .detection.anomaly_rule_engine import AnomalyRuleEngine
from .detection.rules.base import DetectionContext
from .errors import (
    DataClassGuardError,
    DemoError,
    SamplesDirectoryNotFoundError,
)
from .loaders.holiday_calendar_loader import HolidayCalendarLoader
from .loaders.leave_request_loader import LeaveRequestLoader
from .loaders.shift_plan_loader import ShiftPlanLoader
from .loaders.staff_punch_loader import StaffPunchLoader
from .masking.pii_masking_filter import PiiMaskingFilter
from .matching.client_approval_matcher import ClientApprovalMatcher
from .models import Severity
from .output.client_site_report import ClientSiteReport
from .output.dispatch_coordinator_report import DispatchCoordinatorReport
from .output.json_result_writer import JsonResultWriter
from .output.notification_writer import NotificationWriter
from .output.skipped_record_reporter import SkippedRecordReporter
from .output.summary_renderer import SummaryRenderer
from .recommendation.recommendation_composer import RecommendationComposer
from .scoring.severity_scorer import SeverityScorer

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="attendance-check")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_check = sub.add_parser("check", help="月次勤怠チェック")
    p_check.add_argument("--month", required=True, metavar="YYYY-MM")
    p_check.add_argument("--as-of-date", dest="as_of_date", metavar="YYYY-MM-DD", default=None)
    p_check.add_argument("--data-class", dest="data_class", required=True, choices=["dummy", "real"])
    p_check.add_argument("--allow-real-data", dest="allow_real_data", action="store_true")
    p_check.add_argument(
        "--mask-names", dest="mask_names",
        action=argparse.BooleanOptionalAction, default=None,
    )
    p_check.add_argument("--confirm-unmask-real", dest="confirm_unmask_real", action="store_true")
    p_check.add_argument("--assignee", default=None)
    p_check.add_argument("--client", default=None)
    p_check.add_argument("--llm", action="store_true")
    p_check.add_argument("--no-color", dest="no_color", action="store_true")

    p_gen = sub.add_parser("generate-samples", help="ダミーCSV生成")
    p_gen.add_argument("--month", required=True)
    p_gen.add_argument("--data-class", dest="data_class", default="dummy", choices=["dummy"])
    p_gen.add_argument("--count", type=int, default=20)
    p_gen.add_argument("--seed", type=int, default=42)
    p_gen.add_argument("--anomaly-rate", dest="anomaly_rate", type=float, default=0.15)
    p_gen.add_argument("--overwrite", action="store_true")

    return parser


def validate_data_class_guard(args: argparse.Namespace) -> None:
    if args.subcommand == "generate-samples":
        if args.data_class != "dummy":
            raise DataClassGuardError("generate-samples は --data-class dummy のみ許可")
        return

    if args.data_class == "real":
        if not args.allow_real_data:
            raise DataClassGuardError(
                "--data-class real には --allow-real-data が必須です"
            )
        if args.mask_names is None:
            args.mask_names = True
        if args.mask_names is False and not args.confirm_unmask_real:
            raise DataClassGuardError(
                "--data-class real + --no-mask-names には --confirm-unmask-real が必須"
            )
    elif args.data_class == "dummy":
        if args.mask_names is None:
            args.mask_names = False


def run_check(args: argparse.Namespace) -> int:
    t0 = datetime.now()
    month = args.month
    ym = month_dir_name(month)
    today_jst = datetime.now().date()
    as_of_date = resolve_as_of_date(month, args.as_of_date, today_jst)

    sdir = samples_dir(month)
    if not sdir.exists():
        raise SamplesDirectoryNotFoundError(f"{sdir} が見つかりません")
    ts_path = sdir / "timesheet.csv"
    if not ts_path.exists():
        raise SamplesDirectoryNotFoundError(f"{ts_path} が見つかりません（timesheet.csv 必須）")

    # データ分類バナー
    if args.data_class == "dummy":
        print("注意: 本ツールはダミーデータ前提のモックです（--data-class dummy）")
    else:
        print("注意: --data-class real が指定されています。実データ扱いで動作します。")

    skip_reporter = SkippedRecordReporter()

    # Load
    print(f"[1/3] スタッフ打刻データ読み込み中... ({ts_path.name})")
    punches = StaffPunchLoader(skip_reporter).load(ts_path)
    ap_path = sdir / "applications.csv"
    if ap_path.exists():
        leaves_all = LeaveRequestLoader(skip_reporter).load(ap_path)
        has_applications = True
    else:
        logger.warning("applications.csv が見つからないため、申請系パターンを skip します")
        leaves_all = []
        has_applications = False
    sh_path = sdir / "shifts.csv"
    if sh_path.exists():
        shifts = ShiftPlanLoader(skip_reporter).load(sh_path)
        has_shifts = True
    else:
        logger.warning("shifts.csv が見つからないため、シフト系パターンを skip します")
        shifts = []
        has_shifts = False
    hol_path = sdir / "holidays.csv"
    holidays = HolidayCalendarLoader().load(hol_path if hol_path.exists() else None)

    print(
        f"[2/3] 申請データ／派遣先承認ステータス突合中... 申請{len(leaves_all)}件と突合"
    )

    # Filter 適用
    filters: dict = {}
    if args.assignee:
        filters["assignee"] = args.assignee
        punches = [
            p for p in punches
            if p.assignee_id == args.assignee or p.assignee_name == args.assignee
        ]
    if args.client:
        filters["client"] = args.client
        punches = [
            p for p in punches
            if p.client_id == args.client or p.client_name == args.client
        ]

    # Match
    cases = ClientApprovalMatcher(skip_reporter).match(punches, leaves_all, shifts)
    case_index = {c.day_key: c for c in cases}

    # Detect
    print("[3/3] 異常パターン検出中... ", end="")
    ctx = DetectionContext(
        as_of_date=as_of_date,
        holidays=holidays,
        has_applications=has_applications,
        has_shifts=has_shifts,
    )
    engine = AnomalyRuleEngine()
    findings, rule_skipped = engine.run(cases, ctx)
    print(f"完了（{len(findings)}件の Finding）")

    # Score
    scored = SeverityScorer().score(findings, case_index)

    # Recommend
    scored = RecommendationComposer(use_llm=args.llm).compose(scored)

    # Mask
    scored = PiiMaskingFilter(enabled=bool(args.mask_names)).apply(scored)

    # Summary
    total_records = len(punches) if not filters else 0
    # total_records は常に原寸（フィルタ後との違いは別途）
    all_punches_count = _count_original_punches(sdir / "timesheet.csv")
    total_records_filtered = len(punches)

    renderer = SummaryRenderer()
    summary_text = renderer.render(
        scored=scored,
        total_records=all_punches_count,
        total_records_filtered=total_records_filtered,
        month=month,
        no_color=args.no_color,
        filters=filters or None,
    )
    print()
    print(summary_text)

    # Output
    out_root = output_dir()
    checklist_dir = out_root / "checklist"
    notif_dir = out_root / "notifications"

    dcr = DispatchCoordinatorReport()
    grouped_coord = dcr.build(scored)
    coord_path = checklist_dir / f"by_coordinator_{ym}.txt"
    dcr.write(grouped_coord, coord_path, resolve_response_deadline(month, holidays), month)

    csr = ClientSiteReport()
    grouped_site = csr.build(scored)
    site_path = checklist_dir / f"by_client_site_{ym}.txt"
    csr.write(grouped_site, site_path, resolve_response_deadline(month, holidays), month)

    # 通知
    nw = NotificationWriter()
    response_deadline = resolve_response_deadline(month, holidays)
    notif_paths = nw.write(grouped_coord, response_deadline, notif_dir, month)

    # Skipped records
    skip_reporter.write(out_root / "skipped_records.csv")

    # JSON result
    high = sum(1 for s in scored if s.severity == Severity.HIGH)
    med = sum(1 for s in scored if s.severity == Severity.MEDIUM)
    low = sum(1 for s in scored if s.severity == Severity.LOW)
    meta = {
        "month": month,
        "as_of_date": as_of_date.isoformat(),
        "response_deadline": response_deadline.isoformat(),
        "data_class": args.data_class,
        "filters": filters,
        "skipped_summary": skip_reporter.summary(),
        "rule_skipped": rule_skipped,
        "processed_at": datetime.combine(as_of_date, datetime.min.time())
        .replace(hour=18, minute=0)
        .isoformat(),
    }
    summary_json = {
        "total_records": all_punches_count,
        "total_records_filtered": total_records_filtered,
        "flagged_records": len(scored),
        "high": high,
        "medium": med,
        "low": low,
    }
    result_path = out_root / f"result_{ym}.json"
    JsonResultWriter().write(scored, meta, summary_json, result_path)

    # run_summary JSON (実行サマリ別途)
    run_summary = {
        "meta": meta,
        "summary": summary_json,
        "outputs": {
            "coordinator_checklist": str(coord_path.relative_to(out_root.parent)),
            "client_site_checklist": str(site_path.relative_to(out_root.parent)),
            "notifications": [str(p.relative_to(out_root.parent)) for p in notif_paths],
            "result_json": str(result_path.relative_to(out_root.parent)),
        },
    }
    rs_path = out_root / f"run_summary_{ym}.json"
    with open(rs_path, "w", encoding="utf-8") as f:
        json.dump(run_summary, f, ensure_ascii=False, indent=2)

    # 通知出力メッセージ
    print()
    print("▼ 派遣元コーディネーター別通知ファイル")
    for p in notif_paths:
        print(f"  通知ファイル出力: {p.relative_to(out_root.parent)}")
    print()
    print(f"▼ チェックリスト")
    print(f"  {coord_path.relative_to(out_root.parent)}")
    print(f"  {site_path.relative_to(out_root.parent)}")
    print()
    print(f"▼ JSON 結果: {result_path.relative_to(out_root.parent)}")
    print(f"▼ 実行サマリ: {rs_path.relative_to(out_root.parent)}")

    elapsed = (datetime.now() - t0).total_seconds()
    print()
    print(f"完了: 処理時間 {elapsed:.2f}秒")
    return 0


def _count_original_punches(ts_path: Path) -> int:
    """timesheet.csv の行数（ヘッダ除く）。フィルタ前分母表示用。"""
    if not ts_path.exists():
        return 0
    n = 0
    with open(ts_path, encoding="utf-8-sig") as f:
        for i, _ in enumerate(f):
            if i == 0:
                continue
            n += 1
    return n


def run_generate_samples(args: argparse.Namespace) -> int:
    from .generate_samples.sample_data_generator import SampleDataGenerator
    sdir = samples_dir(args.month)
    SampleDataGenerator(seed=args.seed, anomaly_rate=args.anomaly_rate).generate(
        month=args.month,
        count=args.count,
        output_dir=sdir,
        overwrite=args.overwrite,
    )
    print(f"サンプル生成完了: {sdir}")
    return 0
