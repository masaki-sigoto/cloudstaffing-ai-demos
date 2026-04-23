#!/usr/bin/env python3
"""端数処理チェッカー (rounding-checker) - 最小MVP CLI.

派遣管理SaaS「クラウドスタッフィング」の勤怠・請求・給与計算における
端数処理ルールを、打刻データ + YAML ルールで可視化するセミナー実演ツール。

サブコマンド:
  simulate : 打刻CSV + YAMLルール → 丸め後時間・金額を表示
  compare  : 複数ルール間の差分（同じ打刻で支払額がどれだけ違うか）
  explain  : 「なぜこの結果か」を日本語で逆算説明
  validate : YAMLルール定義の妥当性チェック
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DISCLAIMER = (
    "※本ツールは設定ルール通り計算するだけの補助ツールです。"
    "36協定・同一労働同一賃金・抵触日等の法令適合判定は行いません。"
)

ALLOWED_DIRECTIONS = ("ceil", "floor", "round")
ALLOWED_AMOUNT_ROUNDING = ("floor", "half_up", "ceil")
EMP_ID_RE = re.compile(r"^[A-Z]{2,4}\d{3,6}$")
ALLOWED_CSV_COLS = {"date", "employee_id", "clock_in", "clock_out"}


# --------------------------------------------------------------------------
# YAML loader (PyYAML 優先 / なければミニマル実装にフォールバック)
# --------------------------------------------------------------------------
try:
    import yaml  # type: ignore

    def _load_yaml(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be a mapping (got {type(data).__name__})")
        return data
except ImportError:  # pragma: no cover
    def _load_yaml(path: str) -> dict:
        """PyYAML 非インストール時の極小パーサ。

        サンプル YAML の書式（2 スペースインデント / key: value / コメント #）
        のみを解釈する。複雑な YAML（リスト、多段ネスト、アンカー）は非対応。
        """
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        root: dict[str, Any] = {}
        stack: list[tuple[int, dict]] = [(-1, root)]
        for raw in lines:
            line = raw.rstrip("\n")
            # strip comments except inside quotes
            stripped_for_comment = line
            if "#" in stripped_for_comment and not stripped_for_comment.strip().startswith('"'):
                stripped_for_comment = stripped_for_comment.split("#", 1)[0]
            if not stripped_for_comment.strip():
                continue
            indent = len(stripped_for_comment) - len(stripped_for_comment.lstrip(" "))
            content = stripped_for_comment.strip()
            if ":" not in content:
                continue
            key, _, val = content.partition(":")
            key = key.strip()
            val = val.strip()
            # pop back to parent
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]
            if val == "":
                new_map: dict[str, Any] = {}
                parent[key] = new_map
                stack.append((indent, new_map))
            else:
                # unquote
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    parsed: Any = val[1:-1]
                else:
                    # numeric?
                    try:
                        parsed = int(val)
                    except ValueError:
                        try:
                            parsed = float(val)
                        except ValueError:
                            parsed = val
                parent[key] = parsed
        return root


# --------------------------------------------------------------------------
# Data models
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Rule:
    name: str
    description: str
    unit_minutes: int
    clock_in_direction: str
    clock_out_direction: str
    break_minutes: int
    amount_rounding: str
    source_path: str


@dataclass
class Punch:
    date: str | None
    employee_id: str | None
    clock_in_min: int
    clock_out_min: int
    source_line: int | None = None


@dataclass
class SimRow:
    punch: Punch
    in_rounded: int
    out_rounded: int
    delta_in: int
    delta_out: int
    gross_min: int
    break_min: int
    net_min: int
    pay_yen: int | None


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def parse_hhmm(s: str) -> int:
    s = s.strip()
    if not s:
        raise ValueError("empty time")
    if s.count(":") != 1:
        raise ValueError(f"invalid time format: {s!r}")
    h_str, m_str = s.split(":")
    if not h_str.isdigit() or not m_str.isdigit():
        raise ValueError(f"invalid time chars: {s!r}")
    h, m = int(h_str), int(m_str)
    if not (0 <= h <= 23) or not (0 <= m <= 59):
        raise ValueError(f"out of range: {s!r}")
    return h * 60 + m


def fmt_hhmm(minutes: int) -> str:
    if minutes == 1440:
        return "24:00"
    h, m = divmod(minutes, 60)
    return f"{h}:{m:02d}"


def fmt_duration(minutes: int) -> str:
    neg = minutes < 0
    minutes = abs(minutes)
    h, m = divmod(minutes, 60)
    sign = "-" if neg else ""
    return f"{sign}{h}時間{m:02d}分"


# --------------------------------------------------------------------------
# Rounding engine
# --------------------------------------------------------------------------
def round_minutes(m: int, unit: int, direction: str) -> int:
    if direction == "floor":
        return (m // unit) * unit
    if direction == "ceil":
        q, r = divmod(m, unit)
        return (q + 1) * unit if r else m
    if direction == "round":  # half-up
        q, r = divmod(m, unit)
        return (q + 1) * unit if r * 2 >= unit else q * unit
    raise ValueError(f"unknown direction: {direction}")


def calc_pay(minutes: int, hourly: int, amount_rounding: str) -> int:
    """整数演算のみで支払額を算出。float を使わない。"""
    num = hourly * minutes
    q, r = divmod(num, 60)
    if amount_rounding == "floor":
        return q
    if amount_rounding == "ceil":
        return q + (1 if r > 0 else 0)
    if amount_rounding == "half_up":
        return q + (1 if r * 2 >= 60 else 0)
    raise ValueError(f"unknown amount_rounding: {amount_rounding}")


# --------------------------------------------------------------------------
# Config loader
# --------------------------------------------------------------------------
def load_rule(path: str) -> Rule:
    try:
        data = _load_yaml(path)
    except FileNotFoundError:
        raise SystemExit(f"[ERROR] rule file not found: {path}")
    except Exception as e:
        raise SystemExit(f"[ERROR] failed to parse YAML '{path}': {e}")

    def _req(key: str) -> Any:
        if key not in data:
            raise SystemExit(f"[ERROR] required key missing in {path}: {key}")
        return data[key]

    name = str(_req("name"))
    unit = int(_req("unit_minutes"))
    if unit not in (1, 5, 15, 30, 60):
        raise SystemExit(f"[ERROR] unit_minutes must be 1/5/15/30/60 (got {unit})")

    cin = _req("clock_in")
    cout = _req("clock_out")
    if not isinstance(cin, dict) or not isinstance(cout, dict):
        raise SystemExit(f"[ERROR] clock_in / clock_out must be mappings in {path}")
    in_dir = str(cin.get("direction", "")).strip()
    out_dir = str(cout.get("direction", "")).strip()
    if in_dir not in ALLOWED_DIRECTIONS:
        raise SystemExit(f"[ERROR] unknown direction (clock_in): {in_dir}")
    if out_dir not in ALLOWED_DIRECTIONS:
        raise SystemExit(f"[ERROR] unknown direction (clock_out): {out_dir}")

    desc = str(data.get("description", ""))
    break_minutes = 0
    br = data.get("break")
    if isinstance(br, dict):
        btype = br.get("type", "fixed")
        if btype != "fixed":
            raise SystemExit(f"[ERROR] break.type must be 'fixed' in MUST (got {btype})")
        break_minutes = int(br.get("minutes", 0))

    amt = str(data.get("amount_rounding", "floor"))
    if amt not in ALLOWED_AMOUNT_ROUNDING:
        raise SystemExit(
            f"[ERROR] unknown amount_rounding: {amt} (must be floor/half_up/ceil)"
        )

    if "overtime" in data:
        sys.stderr.write(
            "[WARN] overtime is not applied in this build (SHOULD scope)\n"
        )

    return Rule(
        name=name,
        description=desc,
        unit_minutes=unit,
        clock_in_direction=in_dir,
        clock_out_direction=out_dir,
        break_minutes=break_minutes,
        amount_rounding=amt,
        source_path=path,
    )


# --------------------------------------------------------------------------
# Punch parser
# --------------------------------------------------------------------------
def parse_punch_arg(s: str) -> Punch:
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        raise SystemExit(f"[ERROR] --punch must be 'HH:MM,HH:MM' (got {s!r})")
    try:
        cin = parse_hhmm(parts[0])
        cout = parse_hhmm(parts[1])
    except ValueError as e:
        raise SystemExit(f"[ERROR] invalid --punch: {e}")
    if cout <= cin:
        raise SystemExit("[ERROR] clock_out must be > clock_in")
    return Punch(None, None, cin, cout)


def parse_punch_csv(path: str) -> list[Punch]:
    try:
        fh = open(path, "r", encoding="utf-8-sig", newline="")
    except FileNotFoundError:
        raise SystemExit(f"[ERROR] punch file not found: {path}")

    with fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        header_set = {h.strip() for h in header}
        missing = ALLOWED_CSV_COLS - header_set
        if missing:
            raise SystemExit(
                f"[ERROR] CSV missing required columns: {sorted(missing)}"
            )
        extra = header_set - ALLOWED_CSV_COLS
        if extra:
            raise SystemExit(
                f"[ERROR] unexpected column (not in allowlist): {sorted(extra)}"
            )

        out: list[Punch] = []
        for i, row in enumerate(reader, start=2):  # header = line 1
            date = (row.get("date") or "").strip()
            emp = (row.get("employee_id") or "").strip()
            cin_s = (row.get("clock_in") or "").strip()
            cout_s = (row.get("clock_out") or "").strip()

            if not date or not emp or not cin_s or not cout_s:
                sys.stderr.write(f"[WARN] line {i}: empty field\n")
                continue
            # date
            try:
                from datetime import date as _d

                _d.fromisoformat(date)
            except ValueError:
                sys.stderr.write(f"[WARN] line {i}: invalid date format: {date}\n")
                continue
            if not EMP_ID_RE.match(emp):
                sys.stderr.write(
                    f"[WARN] line {i}: employee_id must match ^[A-Z]{{2,4}}\\d{{3,6}}$\n"
                )
                continue
            try:
                cin = parse_hhmm(cin_s)
                cout = parse_hhmm(cout_s)
            except ValueError as e:
                sys.stderr.write(f"[WARN] line {i}: invalid time: {e}\n")
                continue
            if cout <= cin:
                sys.stderr.write(
                    f"[WARN] line {i}: clock_out must be > clock_in\n"
                )
                continue
            out.append(Punch(date, emp, cin, cout, source_line=i))
    if not out:
        raise SystemExit(
            "[ERROR] no valid punches after parsing (all rows skipped)"
        )
    return out


# --------------------------------------------------------------------------
# Core simulation
# --------------------------------------------------------------------------
def simulate_punch(p: Punch, rule: Rule, break_override: int | None, hourly: int | None,
                   amount_rounding_override: str | None = None) -> SimRow:
    in_r = round_minutes(p.clock_in_min, rule.unit_minutes, rule.clock_in_direction)
    out_r = round_minutes(p.clock_out_min, rule.unit_minutes, rule.clock_out_direction)
    # clock_in_rounded == 1440 is invalid per design
    if in_r >= 1440:
        raise SystemExit("[ERROR] clock_in rounded to 24:00 is invalid")
    if out_r > 1440:
        out_r = 1440
    gross = out_r - in_r
    br = break_override if break_override is not None else rule.break_minutes
    net_raw = gross - br
    if net_raw < 0:
        sys.stderr.write(
            f"[WARN] break_minutes ({br}) exceeds gross ({gross}); net clamped to 0\n"
        )
    net = max(0, net_raw)
    pay = None
    if hourly is not None:
        ar = amount_rounding_override or rule.amount_rounding
        pay = calc_pay(net, hourly, ar)
    return SimRow(
        punch=p,
        in_rounded=in_r,
        out_rounded=out_r,
        delta_in=in_r - p.clock_in_min,
        delta_out=out_r - p.clock_out_min,
        gross_min=gross,
        break_min=br,
        net_min=net,
        pay_yen=pay,
    )


# --------------------------------------------------------------------------
# Warnings
# --------------------------------------------------------------------------
def check_rule_warnings(rule: Rule) -> list[str]:
    w: list[str] = []
    ci, co, u = rule.clock_in_direction, rule.clock_out_direction, rule.unit_minutes
    if ci == "ceil" and co == "floor":
        w.append("出勤ceil × 退勤floor は労働時間 減少方向に偏った設定です")
    if ci == "floor" and co == "ceil" and u >= 15:
        w.append("出勤floor × 退勤ceil (unit>=15) は労働時間 増加方向に偏った設定です")
    return w


# --------------------------------------------------------------------------
# Subcommand: simulate
# --------------------------------------------------------------------------
def cmd_simulate(args: argparse.Namespace) -> int:
    rule = load_rule(args.config)
    punches = _collect_punches(args)

    rows = [simulate_punch(p, rule, args.break_minutes, args.hourly) for p in punches]

    print(DISCLAIMER)
    print()
    print("=" * 64)
    print(f" 端数処理チェッカー  |  ルール: {rule.name}")
    print("=" * 64)
    total_net = 0
    total_pay = 0
    total_1min_net = 0  # ベース（1分単位相当）との比較
    for r in rows:
        p = r.punch
        hdr = f"[{p.date}] {p.employee_id}" if p.date else "[単発打刻]"
        print()
        print(hdr)
        in_sign = "+" if r.delta_in >= 0 else ""
        out_sign = "+" if r.delta_out >= 0 else ""
        in_dir_label = _direction_label(rule.clock_in_direction, "in", r.delta_in)
        out_dir_label = _direction_label(rule.clock_out_direction, "out", r.delta_out)
        print(
            f"  出勤打刻: {fmt_hhmm(p.clock_in_min):<6} → 丸め後: {fmt_hhmm(r.in_rounded):<6}"
            f" ({in_sign}{r.delta_in}分 {in_dir_label})"
        )
        print(
            f"  退勤打刻: {fmt_hhmm(p.clock_out_min):<6} → 丸め後: {fmt_hhmm(r.out_rounded):<6}"
            f" ({out_sign}{r.delta_out}分 {out_dir_label})"
        )
        print(f"  Gross:     {fmt_duration(r.gross_min)}")
        print(f"  休憩控除: -{r.break_min}分")
        print(f"  " + "─" * 36)
        print(f"  支払対象時間: {fmt_duration(r.net_min)}")
        if r.pay_yen is not None:
            print(f"  支払額(時給{args.hourly}円): {r.pay_yen:,}円")
        # 1分単位比較
        base_net = (p.clock_out_min - p.clock_in_min) - r.break_min
        base_net = max(0, base_net)
        diff = r.net_min - base_net
        print(
            f"  (1分単位なら: {fmt_duration(base_net)}  /  差分: "
            f"{'+' if diff >= 0 else ''}{diff}分)"
        )
        total_net += r.net_min
        total_1min_net += base_net
        if r.pay_yen is not None:
            total_pay += r.pay_yen

    print()
    print("-" * 64)
    print(f" 合計{len(rows)}件  支払対象時間合計: {fmt_duration(total_net)}"
          f"  (1分単位比: {fmt_duration(total_net - total_1min_net)})")
    if args.hourly is not None:
        print(f" 支払額合計(時給{args.hourly}円): {total_pay:,}円")
    for w in check_rule_warnings(rule):
        print(f" 警告: {w}")
    print("=" * 64)
    return 0


def _direction_label(direction: str, side: str, delta: int) -> str:
    # side: "in" or "out"
    # 真理値表: 出勤+ceil→減、出勤+floor→増、退勤+ceil→増、退勤+floor→減
    if delta == 0:
        return "変化なし"
    if side == "in":
        if direction == "ceil":
            return "労働時間 減少方向"
        if direction == "floor":
            return "労働時間 増加方向"
    else:
        if direction == "ceil":
            return "労働時間 増加方向"
        if direction == "floor":
            return "労働時間 減少方向"
    return "中立"


def _collect_punches(args: argparse.Namespace) -> list[Punch]:
    if getattr(args, "punch", None) and getattr(args, "punch_file", None):
        raise SystemExit("[ERROR] --punch and --punch cannot be combined with --punch-file")
    if getattr(args, "punch", None):
        return [parse_punch_arg(args.punch)]
    if getattr(args, "punch_file", None):
        return parse_punch_csv(args.punch_file)
    raise SystemExit("[ERROR] no input: specify --punch or --punch-file (or use --punch-file for CSV)")


# --------------------------------------------------------------------------
# Subcommand: compare
# --------------------------------------------------------------------------
def cmd_compare(args: argparse.Namespace) -> int:
    rules = [load_rule(p) for p in args.config]
    if len(rules) < 2:
        raise SystemExit("[ERROR] compare requires >=2 --config rules")
    punches = _collect_punches(args)
    hourly = args.hourly
    if hourly is None:
        raise SystemExit("[ERROR] compare requires --hourly")

    # 共通 amount_rounding と break（公平性担保）
    effective_ar = args.amount_rounding or "floor"
    yaml_ars = {r.amount_rounding for r in rules}
    if any(ar != effective_ar for ar in yaml_ars):
        sys.stderr.write(
            f"[WARN] compare では共通 amount_rounding={effective_ar} を適用します"
            f" (YAML値は無視): {sorted(yaml_ars)}\n"
        )
    effective_break = args.break_minutes if args.break_minutes is not None else 0
    yaml_breaks = {r.break_minutes for r in rules}
    if any(b != effective_break for b in yaml_breaks):
        sys.stderr.write(
            f"[WARN] compare では共通 break={effective_break} を適用します"
            f" (YAML値は無視): {sorted(yaml_breaks)}\n"
        )

    # 各ルールで集計（行単位丸め合算）
    per_rule: list[tuple[Rule, int, int, int]] = []  # rule, gross, net, pay
    for rule in rules:
        total_gross = 0
        total_net = 0
        total_pay = 0
        for p in punches:
            row = simulate_punch(
                p, rule, effective_break, hourly, amount_rounding_override=effective_ar
            )
            total_gross += row.gross_min
            total_net += row.net_min
            total_pay += row.pay_yen or 0
        per_rule.append((rule, total_gross, total_net, total_pay))

    baseline_idx = 0
    baseline_pay = per_rule[baseline_idx][3]

    print(DISCLAIMER)
    print()
    punch_desc = (
        f"{fmt_hhmm(punches[0].clock_in_min)} - {fmt_hhmm(punches[0].clock_out_min)}"
        if len(punches) == 1 else f"{len(punches)}件"
    )
    print("=" * 72)
    print(f" ルール比較  |  打刻: {punch_desc}  |  時給: {hourly:,}円"
          f"  |  休憩: {effective_break}分")
    print(f" 比較基準: 支払対象時間（Net）  |  金額丸め: {effective_ar}")
    print("=" * 72)
    # header
    show_gross = args.show_gross
    if show_gross:
        print(f" {'ルール':<40} {'Gross':>8} {'Net':>8} {'支払額':>12} {'基準との差':>12}")
    else:
        print(f" {'ルール':<40} {'Net':>8} {'支払額':>12} {'基準との差':>12}")
    print("-" * 72)
    for rule, gross, net, pay in per_rule:
        diff = pay - baseline_pay
        diff_s = f"{'+' if diff > 0 else ''}{diff:,}円" if diff != 0 else "±0円"
        name = rule.name if len(rule.name) <= 38 else rule.name[:37] + "…"
        if show_gross:
            print(f" {name:<40} {fmt_duration(gross):>8} {fmt_duration(net):>8}"
                  f" {pay:>10,}円 {diff_s:>12}")
        else:
            print(f" {name:<40} {fmt_duration(net):>8} {pay:>10,}円 {diff_s:>12}")
    print("-" * 72)
    pays = [p for _, _, _, p in per_rule]
    spread = max(pays) - min(pays)
    print(f" ルール間 最大差額: {spread:,}円（月20日換算: {spread * 20:,}円）")
    print("=" * 72)
    return 0


# --------------------------------------------------------------------------
# Subcommand: explain
# --------------------------------------------------------------------------
def cmd_explain(args: argparse.Namespace) -> int:
    rule = load_rule(args.config)
    punch = parse_punch_arg(args.punch) if args.punch else None
    if punch is None:
        raise SystemExit("[ERROR] explain requires --punch 'HH:MM,HH:MM'")
    hourly = args.hourly
    row = simulate_punch(punch, rule, args.break_minutes, hourly)

    if args.demo:
        return _explain_demo(row, rule)
    return _explain_full(row, rule, hourly)


def _explain_full(row: SimRow, rule: Rule, hourly: int | None) -> int:
    p = row.punch
    print("=" * 64)
    print(" 逆算チェック  |  なぜこの結果になったか？")
    print("=" * 64)
    print()
    print(f"入力打刻: 出勤 {fmt_hhmm(p.clock_in_min)}  退勤 {fmt_hhmm(p.clock_out_min)}")
    print(f"適用ルール: {rule.name}")
    print()
    print("[ステップ1] 出勤時刻の丸め")
    print(f"  原時刻:    {fmt_hhmm(p.clock_in_min)}")
    print(f"  ルール:    clock_in / unit={rule.unit_minutes}min /"
          f" direction={rule.clock_in_direction}")
    print(f"  計算過程:  {fmt_hhmm(p.clock_in_min)} → {rule.unit_minutes}分単位で"
          f"{_direction_verb(rule.clock_in_direction)} → {fmt_hhmm(row.in_rounded)}")
    print(f"  結果:      {fmt_hhmm(row.in_rounded)}（元より {row.delta_in:+d}分"
          f" / {_direction_label(rule.clock_in_direction, 'in', row.delta_in)}）")
    print()
    print("[ステップ2] 退勤時刻の丸め")
    print(f"  原時刻:    {fmt_hhmm(p.clock_out_min)}")
    print(f"  ルール:    clock_out / unit={rule.unit_minutes}min /"
          f" direction={rule.clock_out_direction}")
    print(f"  計算過程:  {fmt_hhmm(p.clock_out_min)} → {rule.unit_minutes}分単位で"
          f"{_direction_verb(rule.clock_out_direction)} → {fmt_hhmm(row.out_rounded)}")
    print(f"  結果:      {fmt_hhmm(row.out_rounded)}（元より {row.delta_out:+d}分"
          f" / {_direction_label(rule.clock_out_direction, 'out', row.delta_out)}）")
    print()
    print("[ステップ3] Gross労働時間の算出")
    print(f"  計算:      {fmt_hhmm(row.out_rounded)} - {fmt_hhmm(row.in_rounded)}"
          f" = {fmt_duration(row.gross_min)}")
    print()
    print("[ステップ4] 休憩控除")
    print(f"  ルール:    break / type=fixed / minutes={row.break_min}")
    print(f"  計算:      {fmt_duration(row.gross_min)} - {row.break_min}分"
          f" = {fmt_duration(row.net_min)}")
    print()
    print("─" * 60)
    print(f" 支払対象時間: {fmt_duration(row.net_min)}")
    if row.pay_yen is not None:
        print(f" 支払額(時給{hourly}円, {rule.amount_rounding}): {row.pay_yen:,}円")
    print("─" * 60)
    warnings = check_rule_warnings(rule)
    if warnings:
        print()
        print("[警告] このルール設定は偏っています:")
        for w in warnings:
            print(f"  - {w}")
        print("  長期運用時、請求・給与説明の不満につながる可能性があります。")
    return 0


def _explain_demo(row: SimRow, rule: Rule) -> int:
    p = row.punch
    print("=" * 64)
    print(f" 逆算チェック  |  打刻 {fmt_hhmm(p.clock_in_min)} - {fmt_hhmm(p.clock_out_min)}"
          f"  |  ルール: {rule.name}")
    print("=" * 64)
    print()
    print(f"[1] 丸め:    {fmt_hhmm(p.clock_in_min)} → {fmt_hhmm(row.in_rounded)}"
          f" ({row.delta_in:+d}分)   "
          f"{fmt_hhmm(p.clock_out_min)} → {fmt_hhmm(row.out_rounded)}"
          f" ({row.delta_out:+d}分)")
    print(f"[2] 控除:    Gross {fmt_duration(row.gross_min)} − 休憩{row.break_min}分"
          f" = Net {fmt_duration(row.net_min)}")
    print(f"[3] 最終:    支払対象時間 {fmt_duration(row.net_min)}")
    print()
    for w in check_rule_warnings(rule):
        print(f"[警告] {w}")
    return 0


def _direction_verb(direction: str) -> str:
    return {"ceil": "上に丸め", "floor": "下に丸め", "round": "四捨五入"}[direction]


# --------------------------------------------------------------------------
# Subcommand: validate
# --------------------------------------------------------------------------
def cmd_validate(args: argparse.Namespace) -> int:
    for path in args.config:
        try:
            rule = load_rule(path)
        except SystemExit as e:
            print(f"NG  {path}: {e}")
            return 2
        print(f"OK  {path}: name={rule.name!r} unit={rule.unit_minutes}"
              f" in={rule.clock_in_direction} out={rule.clock_out_direction}"
              f" break={rule.break_minutes} amount_rounding={rule.amount_rounding}")
        for w in check_rule_warnings(rule):
            print(f"    [注意] {w}")
    return 0


# --------------------------------------------------------------------------
# argparse
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rounding-checker",
        description="端数処理チェッカー - 派遣勤怠の丸めルールを可視化",
    )
    sub = p.add_subparsers(dest="subcommand", required=True)

    def _common_input(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--config", help="YAMLルールファイル", required=True)
        sp.add_argument("--punch", help="単発打刻 'HH:MM,HH:MM'")
        sp.add_argument("--punch-file", dest="punch_file", help="打刻CSVファイル")
        sp.add_argument("--break", dest="break_minutes", type=int,
                        help="休憩分数（YAML値より優先）")
        sp.add_argument("--hourly", type=int, help="時給（指定時は支払額を計算）")

    # simulate
    sp_sim = sub.add_parser("simulate", help="シミュレーション")
    _common_input(sp_sim)
    sp_sim.set_defaults(func=cmd_simulate)

    # compare
    sp_cmp = sub.add_parser("compare", help="複数ルール比較")
    sp_cmp.add_argument("--config", action="append", required=True,
                        help="YAMLルールファイル（2回以上指定）")
    sp_cmp.add_argument("--punch", help="単発打刻 'HH:MM,HH:MM'")
    sp_cmp.add_argument("--punch-file", dest="punch_file", help="打刻CSVファイル")
    sp_cmp.add_argument("--break", dest="break_minutes", type=int,
                        help="休憩分数（全ルール共通）")
    sp_cmp.add_argument("--hourly", type=int, required=True, help="時給（必須）")
    sp_cmp.add_argument("--amount-rounding", dest="amount_rounding",
                        choices=ALLOWED_AMOUNT_ROUNDING,
                        help="金額丸め（全ルール共通、未指定時 floor）")
    sp_cmp.add_argument("--show-gross", dest="show_gross", action="store_true",
                        help="Gross列も表示")
    sp_cmp.set_defaults(func=cmd_compare)

    # explain
    sp_exp = sub.add_parser("explain", help="逆算説明")
    sp_exp.add_argument("--config", required=True, help="YAMLルールファイル")
    sp_exp.add_argument("--punch", required=True, help="単発打刻 'HH:MM,HH:MM'")
    sp_exp.add_argument("--break", dest="break_minutes", type=int,
                        help="休憩分数（YAML値より優先）")
    sp_exp.add_argument("--hourly", type=int, help="時給（指定時は支払額を計算）")
    sp_exp.add_argument("--demo", action="store_true",
                        help="7分デモ枠向け短縮モード（3ステップ）")
    sp_exp.set_defaults(func=cmd_explain)

    # validate
    sp_val = sub.add_parser("validate", help="YAMLルール妥当性チェック")
    sp_val.add_argument("--config", action="append", required=True,
                        help="YAMLルールファイル")
    sp_val.set_defaults(func=cmd_validate)

    return p


def main(argv: list[str] | None = None) -> int:
    # バージョンチェック
    if sys.version_info < (3, 10):
        sys.stderr.write(
            f"[ERROR] requires Python >=3.10 (got {sys.version.split()[0]})\n"
        )
        return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SystemExit as e:
        if isinstance(e.code, str):
            sys.stderr.write(e.code + "\n")
            return 2
        return int(e.code) if e.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
