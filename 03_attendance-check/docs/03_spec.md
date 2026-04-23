# 技術仕様書: 勤怠チェック自動化（Attendance Check Automation）

本書は `docs/01_requirements.md`（要件定義書）および `docs/02_design.md`（設計書）を前提に、Phase5 実装者が単独で着手可能な粒度までブレイクダウンした **技術仕様書** である。クラウドスタッフィング（人材派遣管理SaaS）の月次締め業務における **3者ワークフロー（派遣元担当者／派遣先承認者／スタッフ）** を設計思想として継承し、ルールエンジン型デモの実装輪郭を規定する。

---

## 1. 仕様書の位置付け

### 1.1 要件定義書・設計書との対応

| 設計書§ | 本仕様書§ | 主題 |
|---|---|---|
| §2 アーキテクチャ | §3, §6 | ディレクトリ構成／データフロー実装形 |
| §3 コンポーネント | §5 | 関数/クラスシグネチャ |
| §4 データフロー | §4, §6 | 中間データモデル／エラー分岐 |
| §5 スキーマ | §4 | CSV/JSON 実装仕様 |
| §6 I/F | §7 | CLI 実装 argparse 構造 |
| §7 アルゴリズム | §6 | A-01〜A-10 疑似コード |
| §8 エラー | §8 | 例外階層 |
| §10 観測可能性 | §9 | ログ仕様 |
| （補助） | §4.2, §5.11, §8 | 補助モジュール: `models.py`（共通dataclass）/ `errors.py`（例外階層）/ `rules/base.py`（AnomalyRule ABC）/ `output/__init__.py` の `safe_join_output`（Round1 追記） |

### 1.2 本仕様書がカバーする範囲
- 実装直前までの関数シグネチャ、型、データクラス定義
- 各異常検知ルール A-01〜A-10 の near-Python 疑似コード
- CLI の argparse 構造、終了コード、二段ガード実装
- ファイルI/O、PIIマスキング、スキップ記録
- 単体テスト設計の骨格

### 1.3 カバーしない範囲
- 具体的なテスト実装コード（ケース骨格のみ記述）
- LLM プロンプト本文（MAY-1、モックでは辞書フォールバックで完結）
- パッケージング、配布（セミナー実演用モックのため）

### 1.4 実装着手の前提条件
- Python 3.10.x が利用可能（Round1 M-1: 再現性のためマイナーバージョン固定）
- サンプルデータ `samples/202604/` が `generate-samples` サブコマンドで生成可能
- 設計書 §3 のモジュール分割（19 モジュール）を継承
- `src/detection/rules/` 配下は **1ファイル1ルール** で 10 ファイル作成（§3 の実装ディレクトリ定義と一致、Round2 Major 1）

### 1.5 3者ワークフローの技術仕様への反映

本ツールは検知結果を「派遣元コーディネーター別」と「派遣先事業所別」の2系統で出力する。これは要件§3.3 のデータフロー「派遣元→派遣先／スタッフへの差戻し起票」を仕様レベルで担保するための設計選択であり、`DispatchCoordinatorReport` と `ClientSiteReport` を独立モジュールとして分離する形で実装する（設計書§4.1）。

---

## 2. 動作環境と依存

### 2.1 Python バージョン

- **固定**: Python 3.10.x（再現性のため 3.11 以降は動作保証外。`match` 文は使用せず、`TypeAlias` / `X | None` 記法を使用）
- 型ヒントはフル活用（`from __future__ import annotations` は付けず、実行時評価可能な型のみ）
- Round1 M-1 対応: 「3.10 以上」ではなく **3.10.x に固定** することでサンプル再生成・検知結果の完全再現を担保

### 2.2 依存ライブラリ

| カテゴリ | ライブラリ | 用途 |
|---|---|---|
| 必須 | `csv`（標準） | CSV 入出力 |
| 必須 | `argparse`（標準） | CLI |
| 必須 | `pathlib`（標準） | パス操作 |
| 必須 | `datetime`（標準） | 日時演算 |
| 必須 | `json`（標準） | JSON 出力 |
| 必須 | `dataclasses`（標準） | 中間データモデル |
| 必須 | `typing`（標準） | 型ヒント |
| 必須 | `logging`（標準） | ログ |
| 必須 | `re`（標準） | slug サニタイズ |
| 必須 | `random`（標準） | サンプル生成（seed固定） |
| 必須 | `enum`（標準） | Severity 列挙 |
| 必須 | `calendar`（標準） | 月末日数算出（§6.13 `resolve_response_deadline`） |
| 必須 | `collections`（標準） | `defaultdict`（§6.12 SeverityScorer） |
| 必須 | `sys`（標準） | stderr ハンドル（§9.1 logging）、exit コード |
| 任意 | （なし） | 第三者ライブラリは **使用しない**（S-4 カラー出力も ANSI エスケープを自前で組む） |

**Round3 Minor 1 対応**: 疑似コードで使用される `calendar` / `collections` / `sys` を必須欄に明記（実装時に標準モジュールだが import 漏れを防ぐため）。

### 2.3 OS / ロケール / 文字コード
- OS: macOS / Linux（Windows は対象外）
- 文字コード: 入出力すべて UTF-8（CSV は `newline=""` + `encoding="utf-8"`）
- ロケール: JST（UTC+9）固定。TZ 変換は行わず naïve datetime で扱う
- 改行: 出力ファイルは `\n` 固定

---

## 3. ディレクトリ構成（実装版）

```
ai-demos/03_attendance-check/
├── docs/
│   ├── 01_requirements.md
│   ├── 02_design.md
│   └── 03_spec.md                             # 本書
├── src/
│   ├── __init__.py
│   ├── main.py                                # CLI エントリ（argparse 呼出）
│   ├── cli.py                                 # サブコマンド振分、二段ガード
│   ├── config.py                              # 締め日/営業日/対応期限 純粋計算
│   ├── models.py                              # 共通 dataclass 定義（Finding 等）
│   ├── errors.py                              # 例外階層（DemoError 系）
│   ├── loaders/
│   │   ├── __init__.py
│   │   ├── staff_punch_loader.py              # timesheet.csv
│   │   ├── leave_request_loader.py            # applications.csv
│   │   ├── shift_plan_loader.py               # shifts.csv
│   │   └── holiday_calendar_loader.py         # holidays.csv（任意）
│   ├── matching/
│   │   ├── __init__.py
│   │   └── client_approval_matcher.py         # MatchedCase 生成
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── anomaly_rule_engine.py             # ルール配列実行
│   │   └── rules/
│   │       ├── __init__.py
│   │       ├── base.py                        # AnomalyRule ABC
│   │       ├── a01_clock_out_missing.py
│   │       ├── a02_clock_in_missing.py
│   │       ├── a03_break_insufficient.py
│   │       ├── a04_continuous_24h.py
│   │       ├── a05_multi_clock.py
│   │       ├── a06_application_mismatch.py
│   │       ├── a07_approval_pending_stale.py
│   │       ├── a08_night_unscheduled.py
│   │       ├── a09_shift_deviation.py
│   │       └── a10_duplicate_punch.py
│   ├── scoring/
│   │   ├── __init__.py
│   │   └── severity_scorer.py                 # 3軸スコア+例外
│   ├── masking/
│   │   ├── __init__.py
│   │   └── pii_masking_filter.py              # --mask-names
│   ├── recommendation/
│   │   ├── __init__.py
│   │   └── recommendation_composer.py         # 既定辞書+LLM
│   ├── output/
│   │   ├── __init__.py
│   │   ├── summary_renderer.py                # stdout サマリ
│   │   ├── dispatch_coordinator_report.py     # 派遣元担当者別
│   │   ├── client_site_report.py              # 派遣先事業所別
│   │   ├── notification_writer.py             # U-001_sato.txt
│   │   ├── json_result_writer.py              # result_YYYYMM.json
│   │   └── skipped_record_reporter.py         # skipped_records.csv
│   └── generate_samples/
│       ├── __init__.py
│       └── sample_data_generator.py           # generate-samples
├── samples/
│   └── 202604/
│       ├── timesheet.csv
│       ├── applications.csv
│       ├── shifts.csv
│       └── holidays.csv                       # 任意
├── output/
│   ├── notifications/
│   │   └── {assignee_id}_{slug}.txt
│   ├── checklist/
│   │   ├── by_coordinator_202604.txt         # M-4: 派遣元担当者別
│   │   └── by_client_site_202604.txt         # M-4: 派遣先事業所別
│   ├── result_202604.json
│   └── skipped_records.csv
├── tests/
│   ├── __init__.py
│   ├── test_rules_a01_to_a10.py               # 10ルール各1ケース
│   ├── test_data_class_guard.py
│   ├── test_as_of_date.py
│   ├── test_severity_scorer.py
│   ├── test_response_deadline.py              # §10.1 #5
│   ├── test_sanitize_slug.py                  # §10.1 #6
│   ├── test_finding_key.py                    # §10.1 #7
│   ├── test_edge_cases.py                     # §10.1 #8（Round1 M-2）
│   ├── test_safe_join_output.py               # §10.1 #9（Round1 C-3）
│   ├── test_pii_masking.py                    # §10.1 #10（Round1 C-2）
│   └── fixtures/
│       └── micro_202604/                      # テスト用最小データ
└── README.md
```

---

## 4. データスキーマ（実装レベル）

### 4.1 入力 CSV（要件§7.3 + 設計書§5.1 を実装形に詳細化）

#### 4.1.1 `timesheet.csv`

| 列 | 型 | 必須 | 制約 | 欠損時 |
|---|---|---|---|---|
| record_id | str | ○ | 一意、例 `T-2026-04-15-0042` | 列欠損は行 skip |
| staff_id | str | ○ | `S-\d{4}` 推奨 | skip |
| staff_name | str | ○ | 日本語可（表示用） | skip |
| client_id | str | ○ | `C-\d{3}` 推奨 | skip |
| client_name | str | ○ | 日本語可 | `client_id` にフォールバック |
| client_site | str | ○（論理必須） | 派遣先事業所（列としては必須、値が欠損/空のときのみ補完） | WARN + `"unknown"` にフォールバック、行は保持 |
| date | str→date | ○ | `YYYY-MM-DD` | skip |
| clock_in | str→datetime? | × | `YYYY-MM-DD HH:MM` or 空 | `None` |
| clock_out | str→datetime? | × | 同上 | `None` |
| break_minutes | str→int | ○ | 0以上 | 負値は WARN+skip |
| assignee_id | str | ○ | `U-\d{3}` 推奨 | skip |
| assignee_name | str | ○ | 日本語可 | skip |

追加バリデーション:

- `clock_in` と `clock_out` が両方埋まっていて `clock_out < clock_in` の場合は **WARN + skip**（暗黙の翌日補正はしない）
- **時刻表記の境界（Round1 M-2）**: `24:00` / `25:00` 等の 24 時以上表記は `datetime.strptime` が解釈しない前提で **WARN + skip**。シフトの日跨ぎは `shifts.csv` 側で翌日日付 + `00:00` 以降の表記を要求（§4.1.3 参照）
- **文字コード（Round1 M-2）**: CSV 読み込みは UTF-8 固定。BOM 付き UTF-8 は `utf-8-sig` として許容。CP932 など他エンコーディングは `UnicodeDecodeError` を `InputSchemaError` に包んで FATAL（exit=1）とする

#### 4.1.2 `applications.csv`

| 列 | 型 | 必須 | 制約 |
|---|---|---|---|
| application_id | str | ○ | 一意 |
| staff_id | str | ○ | |
| date | str→date | ○ | `YYYY-MM-DD` |
| type | str | ○ | `leave` \| `overtime` |
| status | str | ○ | `pending` \| `approved` \| `rejected` |
| applied_at | str→datetime | ○ | `YYYY-MM-DD HH:MM` |
| approved_at | str→datetime? | × | 同上 or 空 |

#### 4.1.3 `shifts.csv`

| 列 | 型 | 必須 |
|---|---|---|
| staff_id | str | ○ |
| date | str→date | ○ |
| scheduled_start | str→datetime | ○ |
| scheduled_end | str→datetime | ○（跨ぎ時は翌日日付で明示） |

#### 4.1.4 `holidays.csv`（任意）

| 列 | 型 | 必須 |
|---|---|---|
| date | str→date | ○ |

### 4.2 内部データモデル（dataclass）

```python
# src/models.py
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Mapping, Optional

class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Scope(str, Enum):
    RECORD = "record"
    DAY = "day"
    APPLICATION = "application"

@dataclass(frozen=True)
class PunchRecord:
    record_id: str
    staff_id: str
    staff_name: str
    client_id: str
    client_name: str
    client_site: str                    # 必須、欠損時は "unknown"
    date: date
    clock_in: Optional[datetime]
    clock_out: Optional[datetime]
    break_minutes: int
    assignee_id: str
    assignee_name: str

@dataclass(frozen=True)
class LeaveApplication:
    application_id: str
    staff_id: str
    date: date
    type: str                           # "leave" | "overtime"
    status: str                         # "pending" | "approved" | "rejected"
    applied_at: datetime
    approved_at: Optional[datetime]

@dataclass(frozen=True)
class ShiftPlan:
    staff_id: str
    date: date
    scheduled_start: datetime
    scheduled_end: datetime

    @property
    def span_hours(self) -> float:
        return (self.scheduled_end - self.scheduled_start).total_seconds() / 3600.0

@dataclass
class MatchedCase:
    # Round2 Critical 2: (staff_id, date) だけでは DAY/APPLICATION スコープの
    # Finding に載せる client_id / client_site / assignee_id が一意に決まらない
    # ため、キーに case 代表の派遣先・担当者を含める。同一スタッフ同日で複数
    # client / assignee が混在する場合は ClientApprovalMatcher が別 MatchedCase
    # として分割する（下記 §5.4 の契約を参照）。
    staff_id: str
    date: date
    client_id: str                      # case 代表（punches/leaves/overtimes 全行で一致）
    client_site: str                    # 同上
    assignee_id: str                    # 同上（派遣元担当者）
    punches: list[PunchRecord] = field(default_factory=list)
    leaves: list[LeaveApplication] = field(default_factory=list)
    overtimes: list[LeaveApplication] = field(default_factory=list)
    shift: Optional[ShiftPlan] = None
    approver_statuses: list[str] = field(default_factory=list)  # 表示専用、A-07判定には不使用

    @property
    def day_key(self) -> str:
        # 派遣元担当者／派遣先が変わる case は同じ staff × date でも別キーとなる。
        return f"{self.staff_id}_{self.date.isoformat()}_{self.client_id}_{self.client_site}_{self.assignee_id}"

    def within_scheduled(self, client_id: str) -> bool:
        """A-05据え置き例外判定用：同一 client_id 内の実働合計が所定労働時間以内か"""
        ...  # §6.11 参照

@dataclass(frozen=True)
class Finding:
    """AnomalyRuleEngine が発行する検知結果。ScoredFinding の素材。"""
    pattern_id: str                     # "A-01"〜"A-10"
    pattern_name: str
    scope: Scope                        # RECORD / DAY / APPLICATION
    staff_id: str
    staff_name: str
    date: date
    client_id: str
    client_name: str
    client_site: str
    assignee_id: str
    assignee_name: str
    approver_statuses: tuple[str, ...]
    record_id: Optional[str] = None     # scope=RECORD 時必須
    application_id: Optional[str] = None  # scope=APPLICATION 時必須
    day_key: str = ""                   # scope=DAY/RECORD/APPLICATION いずれも必須（空は禁止）
    raw_context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # C-4（Round1）: scope ごとの必須項目を型ではなく実行時契約で強制。
        # 型で保証しきれないため、生成時の事故を早期検出する。
        if not self.day_key:
            raise ValueError("Finding.day_key は全 scope で必須")
        if self.scope == Scope.RECORD and not self.record_id:
            raise ValueError("scope=RECORD には record_id が必須")
        if self.scope == Scope.APPLICATION and not self.application_id:
            raise ValueError("scope=APPLICATION には application_id が必須")

    @property
    def finding_key(self) -> str:
        # Round3 Critical 1: A-06 は申請スコープの Finding として扱い、
        # 重複配布された leaves/overtimes が複数 case にまたがって多重発火
        # するのを防ぐ。キーは staff_id + date + branch に固定し、case 代表
        # （client_id/site/assignee_id）を含まない。
        if self.pattern_id == "A-06":
            branch = str(self.raw_context.get("branch", "unknown"))
            return f"a06:{self.staff_id}:{self.date.isoformat()}:{branch}"
        if self.scope == Scope.RECORD:
            return f"record:{self.record_id}"
        if self.scope == Scope.DAY:
            return f"day:{self.day_key}"
        if self.scope == Scope.APPLICATION:
            return f"application:{self.application_id}"
        raise ValueError(f"Unknown scope: {self.scope}")

@dataclass(frozen=True)
class ScoreBreakdown:
    payroll: int   # 0-3
    billing: int
    legal: int

@dataclass
class ScoredFinding:
    finding_key: str
    primary: Finding                    # 代表 Finding
    additional_patterns: list[str]      # 集約で併記された pattern_id
    severity: Severity
    score_breakdown: ScoreBreakdown
    recommended_action: str             # RecommendationComposer が埋める

@dataclass(frozen=True)
class SkippedRecord:
    file: str
    line_no: int
    staff_id: Optional[str]
    date: Optional[str]
    reason: str
```

### 4.3 出力 JSON スキーマ（`output/result_{YYYYMM}.json`）

```json
{
  "meta": {
    "month": "2026-04",
    "as_of_date": "2026-04-28",
    "response_deadline": "2026-04-28",
    "data_class": "dummy",
    "filters": {},
    "skipped_summary": {"total": 3, "by_reason": {"date parse error": 2, "clock_out before clock_in": 1}},
    "rule_skipped": [{"pattern_id": "A-08", "reason": "shifts.csv missing"}],
    "processed_at": "2026-04-30T18:23:11"
  },
  "summary": {
    "total_records": 248,
    "total_records_filtered": 248,
    "flagged_records": 12,
    "high": 4,
    "medium": 5,
    "low": 3
  },
  "items": [
    {
      "finding_key": "record:T-2026-04-15-0042",
      "record_id": "T-2026-04-15-0042",
      "application_id": null,
      "scope": "record",
      "date": "2026-04-15",
      "staff_id": "S-1011",
      "staff_name": "鈴木太郎",
      "client_id": "C-001",
      "client_name": "ACME商事",
      "client_site": "本社事業所",
      "assignee_id": "U-001",
      "assignee_name": "佐藤",
      "approver_statuses": ["pending"],
      "pattern_id": "A-01",
      "pattern_name": "退勤打刻漏れ",
      "additional_patterns": [],
      "severity": "high",
      "recommended_action": "スタッフ本人に退勤時刻を確認し、打刻訂正申請を起票"
    }
  ]
}
```

**`filters` ポリシー（Round1 M-4）**:

- 未指定時は **空オブジェクト `{}`**（`null` 値は使わない）
- `--assignee U-001` のようにフィルタが指定された場合のみ該当キーを追加（例: `{"assignee": "U-001"}`）
- 設計書 §10.1 に準拠。`null` は採用しない（空オブジェクトに統一）

**`approver_statuses` ポリシー（Round3 Major 2）**:

- JSON の `items[].approver_statuses` は **常に配列（`list[str]`）** として出力する。モデル側
  `MatchedCase.approver_statuses` / `Finding.approver_statuses` の複数値を単一値へ潰さずに保持する
- 該当 case に申請が無い場合は空配列 `[]`
- 配列内の並び順は「入力 `applications.csv` 出現順」を維持する（重複除去はしない）
- 旧 Round1/2 例に単数形 `approver_status` 表記が残っていた箇所は R3 でこの複数形配列に統一する。`JsonResultWriter` は `Finding.approver_statuses`（`tuple[str, ...]`）をそのまま JSON 配列化して書き出すこと（単一値へ join する変換規約は設けない）

### 4.4 通知ファイル命名規則

```
output/notifications/{assignee_id}_{assignee_slug}.txt
```

- `assignee_slug` = `re.sub(r"[^A-Za-z0-9-]", "", assignee_name)`（日本語・記号を除去）
- 結果が空文字なら `"unknown"` に置換
- 例: `U-001_sato.txt` / `U-999_unknown.txt`

### 4.5 `skipped_records.csv` 列定義

| 列 | 型 |
|---|---|
| file | str |
| line_no | int |
| staff_id | str (optional, 空可) |
| date | str (optional, 空可) |
| reason | str |

---

## 5. 関数/クラス仕様

### 5.1 `cli` / `main.py`

```python
# src/main.py
def main(argv: Optional[list[str]] = None) -> int:
    """CLI エントリ。exit コードを返す。"""

# src/cli.py
def build_parser() -> argparse.ArgumentParser:
    """argparse パーサを組立てる。"""

def validate_data_class_guard(args: argparse.Namespace) -> None:
    """§5.1 二段ガード。違反時は DataClassGuardError を送出。"""

def run_check(args: argparse.Namespace) -> int:
    """check サブコマンドの本処理ディスパッチ。"""

def run_generate_samples(args: argparse.Namespace) -> int:
    """generate-samples サブコマンドの本処理ディスパッチ。"""
```

- **責務**: 引数解析、二段ガード、サブコマンド振分
- **例外**: `DataClassGuardError` → exit 2、`FileNotFoundError` → exit 1、想定外 → exit 1 + stderr にスタックトレース
- **副作用**: stdout/stderr 書き込み

### 5.2 `config`

```python
# src/config.py
from datetime import date
from typing import Protocol

class HolidayCalendar(Protocol):
    def is_business_day(self, d: date) -> bool: ...
    def business_days_between(self, start: date, end: date) -> int: ...

def resolve_as_of_date(
    month_str: str,
    as_of_arg: Optional[str],
    today_jst: date,
) -> date:
    """--as-of-date 未指定時: (月末締め日, today_jst) の早い方を返す。"""

def resolve_response_deadline(
    month_str: str,
    holidays: HolidayCalendar,
) -> date:
    """M-5 対応期限: target_month 末日から2営業日前を逆算。as_of_date は使わない。"""

def samples_dir(month_str: str) -> Path:
    """samples/{YYYYMM}/ の Path を返す（存在確認はしない）。"""

def output_dir() -> Path:
    """output/ の Path を返す。存在しなければ作成（ディレクトリ作成の副作用あり）。"""
```

- **責務**: パス規約・営業日/締め日計算（`HolidayCalendar` は注入）。基本は純粋計算だが、`output_dir()` のみディレクトリ作成の副作用を含む（Round2 Minor 2: 責務記述を副作用明示に修正）
- **例外**: `DateValidationError`（`month_str` 書式不正）

### 5.3 `StaffPunchLoader` / Loader 群

```python
# src/loaders/staff_punch_loader.py
class StaffPunchLoader:
    def __init__(self, skip_reporter: "SkippedRecordReporter") -> None: ...

    def load(self, path: Path) -> list[PunchRecord]:
        """timesheet.csv を打刻イベント行モデルで読み込む。"""

# 他 Loader も同形
class LeaveRequestLoader:
    def load(self, path: Path) -> list[LeaveApplication]: ...

class ShiftPlanLoader:
    def load(self, path: Path) -> list[ShiftPlan]: ...

class HolidayCalendarLoader:
    def load(self, path: Optional[Path]) -> HolidayCalendar:
        """path=None or 不在なら土日のみ非営業日のカレンダーを返す。"""
```

- **責務**: CSV → dataclass、行不正は `skip_reporter` に登録して skip
- **例外**: `InputSchemaError`（必須列自体が欠けるヘッダ異常）、`FileNotFoundError`（timesheet.csv のみ FATAL、他は呼出側で WARN）

### 5.4 `ClientApprovalMatcher`

```python
# src/matching/client_approval_matcher.py
class ClientApprovalMatcher:
    def __init__(self, skip_reporter: "SkippedRecordReporter") -> None: ...

    def match(
        self,
        punches: list[PunchRecord],
        leaves: list[LeaveApplication],
        shifts: list[ShiftPlan],
    ) -> list[MatchedCase]:
        """staff × date × 派遣先 × 担当者 の 5 キーで合流し MatchedCase を返す。

        Round2 Critical 2 対応:
        - 合流キーは `(staff_id, date, client_id, client_site, assignee_id)`。
          同一スタッフ・同日でも `client_id` / `client_site` / `assignee_id` の
          いずれかが異なれば別の MatchedCase とする（DAY/APPLICATION スコープの
          Finding に載せる値の一意性を保証するため）。
        - `leaves` / `overtimes` は `staff_id × date` のみで引ける申請であり、
          その日の punches を持つ全 case に **同一インスタンスを重複配布** する。
          case ごとに多重発火しないよう、A-06 は `finding_key = a06:{staff_id}:{date}:{branch}`
          を採用して case 代表（client/site/assignee）をキーから外し、A-07 は
          `finding_key = application:{application_id}` で申請単位に一意化する
          （§4.2 `Finding.finding_key` 参照。R3 Critical 1 で A-06 のキー設計を確定）。
        - 対応する punches が 1 件も無く `leaves` / `overtimes` だけが存在する
          場合は、申請の `staff_id × date` に対して `client_id=""`,
          `client_site="unknown"`, `assignee_id=""` の仮想 case を 1 件立てる。
        - 派遣先／担当者解決不能で上記のフォールバックも取れない行は
          `skip_reporter` に `reason="unresolved_client_or_assignee"` で登録し、
          当該 case 自体を破棄する（WARN + skip）。
        """
```

### 5.5 `AnomalyRule` 基底クラスと共通IF

```python
# src/detection/rules/base.py
from abc import ABC, abstractmethod
from typing import Iterator
from dataclasses import dataclass

@dataclass(frozen=True)
class DetectionContext:
    as_of_date: date
    holidays: HolidayCalendar
    has_applications: bool              # applications.csv の有無
    has_shifts: bool                    # shifts.csv の有無

class AnomalyRule(ABC):
    pattern_id: str = ""
    pattern_name: str = ""
    requires_applications: bool = False
    requires_shifts: bool = False

    @abstractmethod
    def check(self, case: MatchedCase, ctx: DetectionContext) -> Iterator[Finding]:
        """1 MatchedCase を検査し、Finding を 0 件以上 yield する。"""
```

- **責務共通IF**: `check(case, ctx) -> Iterator[Finding]`
- 各ルールクラスは `src/detection/rules/aXX_*.py` に配置し、`AnomalyRuleEngine.RULES` リストに登録
- **Round2 Major 3（設計書との語彙整合）**: 設計書 §7.1 では疑似コードとしてメソッド名を `detect(case, ctx) -> list[AnomalyFinding]` と表記しているが、**実装仕様としては本節の `check(case, ctx) -> Iterator[Finding]` を唯一の正とする**。設計書側は概念説明のための擬似表記であり、実装者は本仕様書の `AnomalyRule.check` を参照すること（戻り値も `list` ではなく `Iterator[Finding]` を採用し、大量ケース時のメモリを抑える）

### 5.6 `AnomalyRuleEngine`

```python
# src/detection/anomaly_rule_engine.py
class AnomalyRuleEngine:
    # 型注釈はインスタンスの列。`list[type[AnomalyRule]]` ではなく
    # `list[AnomalyRule]` に統一する（C-4 対応、Round1）。
    RULES: list[AnomalyRule] = [A01(), A02(), A03(), A04(), A05(),
                                A06(), A07(), A08(), A09(), A10()]

    def run(
        self,
        cases: list[MatchedCase],
        ctx: DetectionContext,
    ) -> tuple[list[Finding], list[dict]]:
        """全ルールを全ケースに適用。返り値: (findings, rule_skipped_info)"""
```

- `rule_skipped_info` は `ctx.has_applications=False` で A-06/A-07 を skip した等の情報
- A-07 のみ case 単位ではなく `case.leaves + case.overtimes` の **申請単位** でイテレート（内部実装上、`check()` が複数 Finding を yield する形で実現）

### 5.7 `SeverityScorer`

```python
# src/scoring/severity_scorer.py
SCORE_TABLE: dict[str, ScoreBreakdown] = {
    "A-01": ScoreBreakdown(3, 3, 2),
    "A-02": ScoreBreakdown(3, 3, 2),
    "A-03": ScoreBreakdown(2, 1, 2),
    "A-04": ScoreBreakdown(2, 2, 3),
    "A-05": ScoreBreakdown(1, 1, 1),
    "A-06": ScoreBreakdown(3, 3, 2),
    "A-07": ScoreBreakdown(1, 2, 1),
    "A-08": ScoreBreakdown(2, 1, 2),
    "A-09": ScoreBreakdown(2, 2, 1),
    "A-10": ScoreBreakdown(3, 3, 1),
}

class SeverityScorer:
    def score(
        self,
        findings: list[Finding],
        case_index: dict[str, MatchedCase],    # key = day_key
    ) -> list[ScoredFinding]:
        """finding_key で集約、3軸 max + 例外適用、最高 severity 採用。"""

    def _pick_primary(
        self,
        group: list[Finding],
        per_scores: list[int],
    ) -> Finding:
        """Round3 Major 1: `primary` の決定規約。
        (1) `per_scores` が最大の Finding → (2) 同点時 `pattern_id` 昇順 →
        (3) それでも同点なら `record_id` / `application_id` 昇順、最後に group の入力順で
        stable に選ぶ。`ScoredFinding.severity` と `score_breakdown` が同一 Finding を
        指す不変条件を保証する（§6.12 参照）。"""
```

### 5.8 `PiiMaskingFilter`

```python
# src/masking/pii_masking_filter.py
class PiiMaskingFilter:
    """全出力共通の前処理（Round1 C-2）。
    `enabled=True` のとき `staff_name` / `assignee_name` を先頭1文字+'.' に変換する。
    ID 系（`staff_id` / `assignee_id` / `client_id` / `record_id` / `application_id`）はマスクしない。
    stdout / 通知 txt / チェックリスト / JSON 全てで共通ポリシーを適用し、出力層の直前に必ず通す。"""

    def __init__(self, enabled: bool) -> None: ...

    def apply(self, scored: list[ScoredFinding]) -> list[ScoredFinding]:
        """enabled=True の場合のみ氏名を先頭1文字+'.' に変換。
        Round2 Minor 1 改訂: `additional_patterns` は pattern_id 配列でマスク対象外。
        マスクは各 `ScoredFinding.primary` の `staff_name` / `assignee_name` に対して
        適用し、チェックリスト／通知 txt で additional_patterns の pattern_id を
        併記する場合も氏名は primary 側のマスク済み値を参照する。"""
```

- **配置**: パイプラインでは `SeverityScorer` → `RecommendationComposer` → `PiiMaskingFilter` → Output 層 の順に固定（Output 層の各 Writer は加工しない）

### 5.9 `RecommendationComposer`

```python
# src/recommendation/recommendation_composer.py
DEFAULT_ACTIONS: dict[str, str] = {
    "A-01": "スタッフ本人に退勤時刻を確認し、打刻訂正申請を起票",
    "A-02": "スタッフ本人に出勤時刻を確認し、打刻訂正申請を起票",
    "A-03": "休憩時間の実態をスタッフに確認、不足時は是正指導",
    "A-04": "シフト・打刻の再確認、労務リスク要確認（派遣元労務へエスカレーション）",
    "A-05": "分割勤務の妥当性を確認、通常運用なら据え置き",
    "A-06": "休暇取消または打刻削除／残業申請をスタッフ・派遣先承認者と調整",
    "A-07": "派遣先承認者に承認処理を督促（pending滞留）",
    "A-08": "シフト外深夜打刻の理由を確認、必要なら労務へ相談",
    "A-09": "シフト予定との乖離理由を確認、シフト修正要否を判断",
    "A-10": "どちらが正しい打刻かスタッフ本人に確認",
}

class RecommendationComposer:
    def __init__(self, use_llm: bool) -> None: ...

    def compose(self, scored: list[ScoredFinding]) -> list[ScoredFinding]:
        """recommended_action を埋めて返す。LLM失敗時は辞書にフォールバック。"""
```

### 5.10 Output 層

```python
class SummaryRenderer:
    def render(self, scored: list[ScoredFinding], total_records: int,
               total_records_filtered: int, month: str, no_color: bool) -> str: ...

class DispatchCoordinatorReport:
    def build(self, scored: list[ScoredFinding]) -> dict[str, list[ScoredFinding]]:
        """assignee_id 別にグルーピング（key=assignee_id、昇順ソート）"""

    def write(
        self,
        grouped: dict[str, list[ScoredFinding]],
        output_path: Path,          # 既定: output/checklist/by_coordinator_{YYYYMM}.txt
        response_deadline: date,
        month: str,
    ) -> Path:
        """M-4: 派遣元担当者別チェックリストを1ファイルにまとめて出力。
        担当者ごとにセクション見出し（assignee_id 昇順）→ Findings を §付録B のソート順で列挙。
        response_deadline をヘッダに明記する。"""

class ClientSiteReport:
    def build(self, scored: list[ScoredFinding]) -> dict[tuple[str, str], list[ScoredFinding]]:
        """(client_id, client_site) 別にグルーピング（(client_id, client_site) 昇順）"""

    def write(
        self,
        grouped: dict[tuple[str, str], list[ScoredFinding]],
        output_path: Path,          # 既定: output/checklist/by_client_site_{YYYYMM}.txt
        response_deadline: date,
        month: str,
    ) -> Path:
        """M-4: 派遣先事業所別チェックリストを1ファイルにまとめて出力。
        見出しは `{client_id} / {client_site}` 昇順。response_deadline をヘッダに明記する。"""

class NotificationWriter:
    def write(
        self,
        grouped: dict[str, list[ScoredFinding]],
        response_deadline: date,
        output_dir: Path,
    ) -> list[Path]:
        """各 assignee について output/notifications/{assignee_id}_{slug}.txt を生成。"""

    @staticmethod
    def sanitize_slug(name: str) -> str:
        """re.sub(r'[^A-Za-z0-9-]', '', name) or 'unknown'"""

class JsonResultWriter:
    def write(
        self,
        scored: list[ScoredFinding],
        meta: dict,                 # response_deadline を含む（§4.3 と整合、真実源はここに一本化）
        summary: dict,
        output_path: Path,
    ) -> None:
        """Round2 Major 4: `response_deadline` の真実源は `meta["response_deadline"]`
        に一本化。別引数としての `response_deadline` は削除する（旧 Round1 M-3 で
        明示伝播させたが、meta 内と二重化していたため整理）。呼出側は
        `resolve_response_deadline()` の結果を `meta["response_deadline"]` に
        `isoformat()` 文字列で詰めてから `write()` を呼ぶこと。"""

class SkippedRecordReporter:
    def register(self, rec: SkippedRecord) -> None: ...
    def write(self, output_path: Path) -> None: ...
    def summary(self) -> dict: ...         # {"total": N, "by_reason": {...}}
```

### 5.11 `safe_join_output`（出力先ガード、Round1 C-3）

```python
# src/output/__init__.py または src/config.py に配置
def safe_join_output(base: Path, rel: str | Path) -> Path:
    """base（通常 `output/`）配下への相対パスを安全に結合する（通常のパストラバーサル防止用）。
    `realpath` 解決後に base 配下でなければ `OutputPathViolationError`（FATAL, exit=1）を送出。
    `..` による脱出、絶対パス混入、および **呼び出し時点で存在するシンボリックリンクによる脱出** を弾く。
    呼出側（NotificationWriter / JsonResultWriter / Checklist 2種 / SkippedRecordReporter）は
    出力パス生成時に必ず本関数を通すこと。

    Round3 Major 3 改訂: `resolve(strict=False)` を使うため、解決後にパス上へ新規作成される
    後置シンボリックリンクや TOCTOU（time-of-check vs time-of-use）攻撃に対する完全な耐性
    までは保証しない。デモ用途における通常のパストラバーサル（`..` / 絶対パス / 既存 symlink）
    防止を目的とする。より強固な保護が必要になった場合は `open(..., os.O_NOFOLLOW)` 相当に
    実装を引き上げる方針とする（本デモでは採用しない）。"""
    candidate = (base / rel).resolve(strict=False)
    base_real = base.resolve(strict=False)
    try:
        candidate.relative_to(base_real)
    except ValueError:
        raise OutputPathViolationError(
            f"出力先が {base_real} の外を指しています: {candidate}")
    return candidate
```

- **責務**: 全出力ファイルの書き出し前に `realpath` で `output/` 配下判定を行い、外部への書き込みを拒否
- **例外**: `OutputPathViolationError`（`DemoError`、exit_code=1）
- **適用対象**: §5.10 の全 Writer／Reporter、§5.12 `SampleDataGenerator` の書き出し

### 5.12 `SampleDataGenerator`

```python
class SampleDataGenerator:
    def __init__(self, seed: int, anomaly_rate: float) -> None: ...

    def generate(
        self,
        month: str,
        count: int,
        output_dir: Path,
        overwrite: bool,
    ) -> None:
        """10パターン全てが最低1件は混入するダミーCSVを生成。"""
```

---

## 6. アルゴリズム詳細（A-01〜A-10 near-Python 疑似コード）

### 6.1 A-01 退勤打刻漏れ（scope=RECORD）

```python
class A01(AnomalyRule):
    pattern_id = "A-01"
    pattern_name = "退勤打刻漏れ"

    def check(self, case, ctx):
        for p in case.punches:
            if p.clock_in is not None and p.clock_out is None:
                yield Finding(
                    pattern_id="A-01", pattern_name=self.pattern_name,
                    scope=Scope.RECORD, record_id=p.record_id,
                    day_key=case.day_key,
                    staff_id=p.staff_id, staff_name=p.staff_name,
                    date=p.date, client_id=p.client_id, client_name=p.client_name,
                    client_site=p.client_site,
                    assignee_id=p.assignee_id, assignee_name=p.assignee_name,
                    approver_statuses=tuple(case.approver_statuses),
                )
```

### 6.2 A-02 出勤打刻漏れ（scope=RECORD）
A-01 と対称。`clock_in is None and clock_out is not None`。

### 6.3 A-03 休憩未入力（scope=RECORD）

```python
worked = ((p.clock_out - p.clock_in).total_seconds() / 60) - p.break_minutes
if 360 < worked <= 480 and p.break_minutes < 45:
    yield Finding(...)
elif worked > 480 and p.break_minutes < 60:
    yield Finding(...)
```
※ `p.clock_in` / `p.clock_out` が欠ける行は対象外（A-01/A-02 側で検知）。

### 6.4 A-04 連続24時間超（scope=RECORD）

```python
if p.clock_in and p.clock_out and (p.clock_out - p.clock_in) >= timedelta(hours=24):
    raw = {"shift_span_hours": case.shift.span_hours if case.shift else None}
    yield Finding(..., raw_context=raw)
```
※ スコア降格（shift_span_hours >= 24 のとき high→medium）は `SeverityScorer` 側で適用。

### 6.5 A-05 1日複数回の出退勤（scope=DAY）

```python
complete = [p for p in case.punches if p.clock_in and p.clock_out]
if len(complete) >= 2:
    yield Finding(scope=Scope.DAY, day_key=case.day_key, record_id=None, ...)
```

### 6.6 A-06 申請×実績不整合（scope=DAY、2分岐）

**Round3 Critical 1 対応**: `leaves` / `overtimes` は §5.4 で「同一 staff × date の全 case に重複配布」される設計のため、A-06 の `finding_key` は case 代表（client/site/assignee）を含めず `a06:{staff_id}:{date}:{branch}` に固定する（§4.2 `Finding.finding_key` 参照）。これにより同一 staff × date で複数 client case に分かれていても、分岐ごとに Finding は 1 件に集約される（`SeverityScorer` の `finding_key` 集約で重複排除）。

**発行ガード**: 各分岐とも、`case.punches` を持たない仮想 case（§5.4 で `leaves`/`overtimes` のみの日に立てるもの）では Finding を発行しない。punches を持つ複数 case から同分岐が複数 yield されても、集約キー（`a06:...:branch`）で 1 件に畳み込む前提。

```python
if not ctx.has_applications:
    return   # 呼出側で rule_skipped に記録済み

# 仮想 case（punches が 0 件、leaves/overtimes のみ集約された case）からは発行しない
if not case.punches:
    return

# 分岐1: 休暇申請と打刻の矛盾
approved_leave = next(
    (l for l in case.leaves if l.status == "approved"), None)
if approved_leave and any(p.clock_in or p.clock_out for p in case.punches):
    yield Finding(pattern_id="A-06", scope=Scope.DAY, day_key=case.day_key,
                  raw_context={"branch": "leave_vs_punch"}, ...)
    # finding_key は "a06:{staff_id}:{date}:leave_vs_punch" に畳み込まれる

# 分岐2: 残業申請漏れ
if case.shift:
    threshold_h = case.shift.span_hours - 1.0   # 1h休憩控除
else:
    threshold_h = 8.0                            # fallback
threshold_min = threshold_h * 60 + 30
total_worked_min = sum(
    ((p.clock_out - p.clock_in).total_seconds() / 60 - p.break_minutes)
    for p in case.punches if p.clock_in and p.clock_out)
if total_worked_min > threshold_min:
    # overtime 申請の status を approved > pending > rejected で採用
    ot_status = pick_overtime_status(case.overtimes)
    if ot_status in ("rejected", None):
        yield Finding(pattern_id="A-06", scope=Scope.DAY, day_key=case.day_key,
                      raw_context={"branch": "overtime_missing"}, ...)
        # finding_key は "a06:{staff_id}:{date}:overtime_missing" に畳み込まれる

def pick_overtime_status(overtimes):
    priority = {"approved": 0, "pending": 1, "rejected": 2}
    if not overtimes:
        return None
    return min(overtimes, key=lambda a: priority.get(a.status, 99)).status
```

**回帰テスト追加（§10.1 / §10.2）**: 同一 staff × date で複数 client case に分かれる入力で A-06 が 1 件に集約されることを保証する `T-A06-DedupeAcrossCases` を `test_rules_a01_to_a10.py` に追加（詳細は §10.2 参照）。

### 6.7 A-07 派遣先承認待ち滞留（scope=APPLICATION）

```python
if not ctx.has_applications:
    return
targets = [a for a in (case.leaves + case.overtimes) if a.status == "pending"]
for a in targets:
    bd = ctx.holidays.business_days_between(a.applied_at.date(), ctx.as_of_date)
    if bd >= 3:
        yield Finding(
            pattern_id="A-07", scope=Scope.APPLICATION,
            application_id=a.application_id,
            day_key=case.day_key,
            raw_context={"application_id": a.application_id,
                         "applied_at": a.applied_at.isoformat(),
                         "business_days_elapsed": bd,
                         "application_type": a.type},
            ...
        )
```
**重要**: A-07 は **申請単位で別 Finding** を発行（R3対応）。同一 staff × date に複数 pending 申請があっても day 集約で潰れない。`finding_key = f"application:{application_id}"`。

### 6.8 A-08 深夜打刻（シフト外、scope=DAY）

```python
if not ctx.has_shifts:
    return
for p in case.punches:
    for t in (p.clock_in, p.clock_out):
        if t is None:
            continue
        if not (t.hour >= 22 or t.hour < 5):
            continue
        # 深夜帯の打刻
        if case.shift and case.shift.scheduled_start <= t <= case.shift.scheduled_end:
            continue   # 予定時間内なら除外（§7.1 例外）
        yield Finding(pattern_id="A-08", scope=Scope.DAY, day_key=case.day_key, ...)
        return    # 1日1件で足りる（重複発行を避ける）
```

### 6.9 A-09 シフトとの大幅乖離（scope=RECORD）

```python
if not ctx.has_shifts or case.shift is None:
    return
for p in case.punches:
    if p.clock_in and abs((p.clock_in - case.shift.scheduled_start).total_seconds()) > 3600:
        yield Finding(pattern_id="A-09", scope=Scope.RECORD, record_id=p.record_id, ...)
        continue
    if p.clock_out and abs((p.clock_out - case.shift.scheduled_end).total_seconds()) > 3600:
        yield Finding(pattern_id="A-09", scope=Scope.RECORD, record_id=p.record_id, ...)
```

### 6.10 A-10 重複打刻（scope=RECORD）

```python
# clock_in 時刻を時系列ソートし、隣接差が5分以内なら検知
ins = sorted([(p.record_id, p.clock_in) for p in case.punches if p.clock_in],
             key=lambda x: x[1])
for (r1, t1), (r2, t2) in zip(ins, ins[1:]):
    if (t2 - t1).total_seconds() <= 300:
        yield Finding(pattern_id="A-10", scope=Scope.RECORD, record_id=r2, ...)
# clock_out も同様
```

### 6.11 `MatchedCase.within_scheduled(client_id)` の実装

```python
def within_scheduled(self, client_id):
    """同一 client_id 内の実働合計 ≤ 所定労働時間 か"""
    if not self.shift:
        scheduled_min = 8 * 60
    else:
        scheduled_min = (self.shift.span_hours - 1.0) * 60
    total = 0
    for p in self.punches:
        if p.client_id != client_id or not (p.clock_in and p.clock_out):
            continue
        total += (p.clock_out - p.clock_in).total_seconds() / 60 - p.break_minutes
    return total <= scheduled_min
```

### 6.12 SeverityScorer 疑似コード

```python
def score(self, findings, case_index):
    buckets = defaultdict(list)
    for f in findings:
        buckets[f.finding_key].append(f)

    scored = []
    for key, group in buckets.items():
        case = case_index.get(group[0].day_key)
        per_scores = [self._resolve_score(f, case) for f in group]
        max_score = max(per_scores)
        severity = {3: Severity.HIGH, 2: Severity.MEDIUM, 1: Severity.LOW}[max_score]
        primary = self._pick_primary(group, per_scores)
        scored.append(ScoredFinding(
            finding_key=key, primary=primary,
            additional_patterns=[f.pattern_id for f in group if f is not primary],
            severity=severity,
            score_breakdown=SCORE_TABLE[primary.pattern_id],  # primary と必ず一致
            recommended_action="",   # RecommendationComposer が埋める
        ))
    return sorted(scored, key=self._sort_key)

def _pick_primary(self, group, per_scores):
    """Round3 Major 1 対応: `primary` の決定規約を明文化する。
    `severity`（表示）と `score_breakdown`（説明軸）が同じ Finding を指すよう、
    以下の順序で tie-break して唯一の Finding を返す。

    1. `_resolve_score(f, case)`（例外適用後のスコア）が最大の Finding
    2. 同点時は `pattern_id` 昇順（A-01 < A-02 < ... < A-10）の最小を採用
    3. それでも同点（同一 pattern_id が複数）なら `raw_context` の `application_id` /
       `record_id` 昇順、最後に group 中の入力順（stable sort）で決定

    これにより `severity` は group の最大スコア、`score_breakdown` は `primary.pattern_id`
    に対応する `SCORE_TABLE` の行、という両者が同一 Finding を指す不変条件が成立する。
    """
    # per_scores と group は同順。zip で pair を作り、上記 3 段階で sort して先頭を採る。
    paired = list(zip(group, per_scores))
    paired.sort(key=lambda item: (
        -item[1],                                   # 1: 例外適用後スコア降順
        item[0].pattern_id,                         # 2: pattern_id 昇順
        item[0].record_id or "",                    # 3a: record_id 昇順（None は "" 扱い）
        item[0].application_id or "",               # 3b: application_id 昇順
    ))
    return paired[0][0]

def _resolve_score(self, f, case):
    base = SCORE_TABLE[f.pattern_id]
    raw = max(base.payroll, base.billing, base.legal)
    # A-04 降格
    if f.pattern_id == "A-04" and case and case.shift and case.shift.span_hours >= 24:
        return 2
    # A-05 据え置き
    if f.pattern_id == "A-05" and case and case.within_scheduled(
        f.client_id if case.punches else ""):
        return 1
    return raw

def _sort_key(self, sf):
    sev_rank = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}
    return (sev_rank[sf.severity], sf.primary.date,
            sf.primary.staff_id, sf.primary.pattern_id)
```

### 6.13 M-5 対応期限算出（`config.resolve_response_deadline`）

```python
def resolve_response_deadline(month_str, holidays):
    y, m = map(int, month_str.split("-"))
    last = date(y, m, calendar.monthrange(y, m)[1])
    # 月末締め日から2営業日前を逆算
    d = last
    count = 0
    while count < 2:
        d -= timedelta(days=1)
        if holidays.is_business_day(d):
            count += 1
    return d
```

### 6.14 営業日計算（`HolidayCalendar.business_days_between`）

```python
def business_days_between(self, start, end):
    """(start, end] の営業日数"""
    if end <= start:
        return 0
    d = start + timedelta(days=1)
    n = 0
    while d <= end:
        if self.is_business_day(d):
            n += 1
        d += timedelta(days=1)
    return n

def is_business_day(self, d):
    if d.weekday() >= 5:    # 土日
        return False
    if d in self._holiday_set:
        return False
    return True
```

---

## 7. CLI 仕様（実装版）

### 7.1 argparse 構造

```python
parser = argparse.ArgumentParser(prog="attendance-check")
sub = parser.add_subparsers(dest="subcommand", required=True)

# check
p_check = sub.add_parser("check", help="月次勤怠チェック")
p_check.add_argument("--month", required=True, metavar="YYYY-MM")
p_check.add_argument("--as-of-date", metavar="YYYY-MM-DD", default=None)
p_check.add_argument("--data-class", required=True, choices=["dummy", "real"])
p_check.add_argument("--allow-real-data", action="store_true")
p_check.add_argument("--mask-names", dest="mask_names",
                     action=argparse.BooleanOptionalAction, default=None)
p_check.add_argument("--confirm-unmask-real", action="store_true")
p_check.add_argument("--assignee", default=None)
p_check.add_argument("--client", default=None)
p_check.add_argument("--llm", action="store_true")
p_check.add_argument("--no-color", action="store_true")

# generate-samples
p_gen = sub.add_parser("generate-samples", help="ダミーCSV生成")
p_gen.add_argument("--month", required=True)
p_gen.add_argument("--data-class", required=True, choices=["dummy"])
p_gen.add_argument("--count", type=int, default=50)
p_gen.add_argument("--seed", type=int, default=42)
p_gen.add_argument("--anomaly-rate", type=float, default=0.15)
p_gen.add_argument("--overwrite", action="store_true")
```

### 7.2 二段ガード実装（`validate_data_class_guard`）

```python
def validate_data_class_guard(args):
    if args.subcommand == "generate-samples":
        if args.data_class != "dummy":
            raise DataClassGuardError("generate-samples は --data-class dummy のみ許可")
        return

    # check 分
    if args.data_class == "real":
        if not args.allow_real_data:
            raise DataClassGuardError("--data-class real には --allow-real-data が必須")
        # mask_names デフォルト: real なら ON
        if args.mask_names is None:
            args.mask_names = True
        if args.mask_names is False and not args.confirm_unmask_real:
            raise DataClassGuardError(
                "--data-class real + --no-mask-names には --confirm-unmask-real が必須")
    elif args.data_class == "dummy":
        if args.mask_names is None:
            args.mask_names = False
        # --allow-real-data は dummy では無視（警告のみ）
```

### 7.3 終了コード

| コード | 意味 |
|---|---|
| 0 | 正常終了（検知0件でも 0） |
| 1 | 致命的エラー（`samples/{YYYYMM}/` 不在、`timesheet.csv` 不在、想定外例外） |
| 2 | 引数エラー（`--data-class` 未指定、ガード違反、`argparse` エラー） |

### 7.4 stdout / stderr 出し分け
- **stdout**: 進捗表示、サマリ、チェックリスト、通知生成メッセージ
- **stderr**: WARN / ERROR ログ（`[WARN] {module}: {message}` / `[ERROR] {module}: {message}`）

---

## 8. エラー処理と例外階層

```python
# src/errors.py
class DemoError(Exception):
    """本デモの全例外の基底。"""
    exit_code: int = 1

class InputSchemaError(DemoError):
    """CSV ヘッダが必須列を満たさない等。"""
    exit_code = 1

class DataClassGuardError(DemoError):
    """--data-class ガード違反。"""
    exit_code = 2

class DateValidationError(DemoError):
    """--month / --as-of-date の書式不正。"""
    exit_code = 2

class SamplesDirectoryNotFoundError(DemoError):
    exit_code = 1

class OutputPathViolationError(DemoError):
    """出力先が `output/` 配下を逸脱した場合に送出（Round1 C-3）。"""
    exit_code = 1

class RuleSkippedWarning(UserWarning):
    """ルール skip 情報（例外ではなく警告）。"""
```

| 例外 | 発生条件 | 終了コード | メッセージ例 |
|---|---|---|---|
| `DataClassGuardError` | `--data-class` 未指定等 | 2 | `--data-class real には --allow-real-data が必須です` |
| `SamplesDirectoryNotFoundError` | `samples/YYYYMM/` 不在 | 1 | `samples/202604/ が見つかりません` |
| `InputSchemaError` | `timesheet.csv` 必須列欠落 | 1 | `timesheet.csv: 必須列 'record_id' がありません` |
| `DateValidationError` | 書式不正 | 2 | `--month は YYYY-MM 形式で指定してください` |
| `OutputPathViolationError` | `output/` 外への書き込み試行 | 1 | `出力先が output/ の外を指しています: /etc/passwd` |

---

## 9. ログ仕様

### 9.1 logging 設定

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)
```
- **WARN / ERROR は stderr**（`basicConfig` の `stream=sys.stderr` 経由）
- **INFO 以下の進捗表示は `print()` で stdout**（セミナー映え演出用、logging を通さない）
- `run_id` は `datetime.now().strftime("%Y%m%dT%H%M%S")` で生成し、JSON `meta.processed_at` に記録
- **Round2 Critical 1（再現性）**: `meta.processed_at` は毎回の実行時刻を記録するため JSON バイト列は原則一致しない。再現性を検証する `T-AsOfDate-Reproducibility`（§10.2）は **`processed_at` を除外した部分木の一致** を期待とする（比較時に `meta.processed_at` をドロップしてから `json.dumps(..., sort_keys=True)` で比較）。完全なバイト一致テストが必要な場合はテスト側で `Clock` 相当（`datetime.now` を差し替える薄い関数注入）により固定時刻を与える運用とし、仕様としてはバイト一致を要件としない

### 9.2 実行サマリ JSON 構造（再掲、§4.3 と整合）

`meta` の必須フィールド:
- `month` / `as_of_date` / `response_deadline` / `data_class`
- `filters: {assignee?, client?}`
- `skipped_summary: {total, by_reason}`
- `rule_skipped: [{pattern_id, reason}]`
- `processed_at`（ISO8601）

### 9.3 PII マスキング適用箇所（Round1 C-2 改訂）

- **全出力共通**: stdout / 通知 txt / チェックリスト（`by_coordinator_*.txt` / `by_client_site_*.txt`）/ JSON（`result_*.json`） いずれも `PiiMaskingFilter` を出力直前に通す
- マスク対象は **氏名のみ**（`staff_name` / `assignee_name`）→ 先頭1文字+`.`（例: `鈴木太郎` → `鈴.`）
- **ID 系はマスクしない**: `staff_id` / `assignee_id` / `client_id` / `record_id` / `application_id` / `day_key` / `finding_key` は突合性確保のため全出力で平文を維持
- `client_name` / `client_site` も非マスク（派遣先業務上の識別子として扱う）
- `--data-class real` では `mask_names` の既定は ON。解除したい場合は `--no-mask-names` + `--confirm-unmask-real` の二重宣言が必須
- `skipped_records.csv` の `reason` 列に氏名は含めない（`staff_id` のみ記録）

---

## 10. テスト設計

### 10.1 対象モジュール一覧

| # | テストファイル | 対象 | 重点 |
|---|---|---|---|
| 1 | `test_rules_a01_to_a10.py` | 10 ルール | 各1ケース（仕込み→検知成立） |
| 2 | `test_data_class_guard.py` | `cli.validate_data_class_guard` | §7.2 の分岐全網羅 |
| 3 | `test_as_of_date.py` | `config.resolve_as_of_date`, A-07 | 再現性：`--as-of-date` 固定で同一結果 |
| 4 | `test_severity_scorer.py` | `SeverityScorer` | 3軸max、A-04降格、A-05据え置き |
| 5 | `test_response_deadline.py` | `resolve_response_deadline` | 月末から2営業日前の逆算 |
| 6 | `test_sanitize_slug.py` | `NotificationWriter.sanitize_slug` | 日本語→unknown、英数のみ保持 |
| 7 | `test_finding_key.py` | `Finding.finding_key` | 3 scope の prefix 付与 |
| 8 | `test_edge_cases.py` | Loader / Engine / Output | Round1 M-2: 24:00 境界、0件入力、CP932 混入、BOM 付き UTF-8 |
| 9 | `test_safe_join_output.py` | `safe_join_output` | Round1 C-3: `..` 脱出、絶対パス、シンボリックリンクで `OutputPathViolationError` |
| 10 | `test_pii_masking.py` | `PiiMaskingFilter` | Round1 C-2: JSON／stdout／txt 全出力で氏名マスク・ID非マスク |

### 10.2 代表テストケース（入力→期待出力）

**T-A01（A-01 退勤打刻漏れ）**
- 入力: `PunchRecord(clock_in="09:00", clock_out=None)` 1件
- 期待: Finding 1件、`pattern_id="A-01"`, `scope=RECORD`, `severity=HIGH`

**T-A07-複数申請（R3 Critical 1 対応）**
- 入力: 同一 staff × date に `pending` 申請2件（`applied_at` 異なる）
- 期待: Finding 2件（`finding_key` は `application:{id1}` と `application:{id2}`）、day 集約で潰れない

**T-A06-overtime-fallback**
- 入力: `shifts.csv` なし、実働9h、overtime 申請なし
- 期待: Finding 1件、`threshold=8h+30min=510min`、9h=540min > 510 → 検知

**T-A06-DedupeAcrossCases**（R3 Critical 1 対応）
- 入力: 同一 `staff_id × date` で異なる `client_id` / `client_site` の punches が 2 case に分かれ、いずれも approved な `leave` 申請 1 件と矛盾（`leave_vs_punch` 分岐が 2 case で発火する状況）
- 期待: A-06 Finding は内部的に 2 件 yield されても、`finding_key = "a06:{staff_id}:{date}:leave_vs_punch"` で畳み込まれ、`ScoredFinding` は 1 件のみとなる
- 追加確認: `case.punches` が空（`leaves` のみの仮想 case）からは A-06 が発行されないこと

**T-Guard-Real-NoAllow**
- 入力: `--data-class real` のみ
- 期待: `DataClassGuardError`、exit code 2

**T-Guard-Real-NoConfirm**
- 入力: `--data-class real --allow-real-data --no-mask-names`（`--confirm-unmask-real` なし）
- 期待: `DataClassGuardError`、exit code 2

**T-AsOfDate-Reproducibility**（Round2 Critical 1 改訂）
- 入力: 同一サンプル + `--as-of-date 2026-04-28` を2回実行
- 期待: `output/result_202604.json` を `json.load` した後 `meta.processed_at` を除外したオブジェクトが両実行で一致（`json.dumps(..., sort_keys=True)` 比較）。`processed_at` は実行時刻そのものを示すため比較対象から外す
- 補足: 完全バイト一致が必要な場合は、`datetime.now` を差し替える Clock 注入（例: `json_result_writer.py` の now 取得を引数化）により固定時刻を与えるテストを別途用意すること

**T-Scorer-A04-Demote**
- 入力: A-04 Finding + `case.shift.span_hours=25`
- 期待: `severity=MEDIUM`（high→medium 降格）

**T-Edge-24Hour**（Round1 M-2）
- 入力: `timesheet.csv` に `clock_out=2026-04-15 24:00`
- 期待: WARN + skip、`skipped_records.csv` に reason `invalid time format` で登録

**T-Edge-EmptyInput**（Round1 M-2）
- 入力: `timesheet.csv` がヘッダのみ（0件）
- 期待: exit=0、`summary.total_records=0`、`items=[]`、JSON 正常生成

**T-Edge-Encoding-CP932**（Round1 M-2）
- 入力: CP932 でエンコードされた `timesheet.csv`
- 期待: `InputSchemaError`（exit=1）、stderr に文字コード起因である旨のメッセージ

**T-Edge-Encoding-UTF8-BOM**（Round1 M-2）
- 入力: BOM 付き UTF-8 の `timesheet.csv`
- 期待: 正常読み込み（`utf-8-sig` 扱い）

**T-SafePath-Violation**（Round1 C-3）
- 入力: `safe_join_output(Path("output"), "../etc/passwd")`
- 期待: `OutputPathViolationError`、exit=1

**T-PII-JSON-Masked**（Round1 C-2）
- 入力: `--mask-names` ON で JSON 出力
- 期待: `items[].staff_name="鈴."`、`items[].staff_id="S-1011"`（ID 非マスク）

### 10.3 テストデータ
- `tests/fixtures/micro_202604/` に 10 パターン全てを最低1件含む最小CSVを配置
- `SampleDataGenerator --seed 42 --count 10` で再生成可能

### 10.4 テスト自動化方針（Round1 M-1 改訂）

- **標準ライブラリ `unittest` を採用**（外部依存ゼロ方針を厳守）
- 実装者が `python -m unittest discover -s tests -v` で手元実行可能な状態を目標
- CI は組まない（セミナー実演用モック）
- `pytest` は使用しない（依存固定コスト／環境差異を回避するため）

---

## 付録A. 重要度スコア表（実装定数、再掲）

§5.7 の `SCORE_TABLE` を単一の真実源とする。要件§4.1 M-3 の表と整合。

## 付録B. 出力並び順（決定的実行の担保）

全ての一覧出力は `severity desc, date asc, staff_id asc, pattern_id asc` の固定順（§6.12 `_sort_key` 実装）。

**グループキーのソート規約（Round1 m-3）**:

- 派遣元担当者別チェックリスト: `assignee_id` 昇順でセクションを並べる。同一セクション内の Finding は上記の固定順
- 派遣先事業所別チェックリスト: `(client_id, client_site)` のタプル昇順でセクションを並べる。同一セクション内の Finding は上記の固定順
- `dict` を使う場合も Python 3.7+ の挿入順保持に頼らず、出力直前に明示的に `sorted()` を通すこと（デモ時の差分ブレ防止）

## 付録C. 実装上の決定記録

| # | 決定 | 理由 |
|---|---|---|
| D-1 | `argparse` を採用（click 不採用） | 標準ライブラリ方針、最小依存 |
| D-2 | `dataclass(frozen=True)` を原則とし、`MatchedCase` と `ScoredFinding` のみ mutable | ルール実行中に書き換える中間データと不変データを分離 |
| D-3 | S-4 カラー出力は ANSI を自前実装 | `rich` 不採用、標準ライブラリ方針 |
| D-4 | A-07 を `scope=APPLICATION` で申請単位検知 | R3 Critical 1 対応。同一日複数 pending の取り違え防止 |
| D-5 | `finding_key` は必ず prefix 付き | scope 跨ぎの衝突を名前空間分離で設計的排除 |
| D-6 | `response_deadline` は `--month` から逆算 | `as_of_date` と分離し、対象月末基準で安定化 |
| D-7 | `approver_statuses` は list を原形保持 | A-07 判定に使わず、表示用 join は出力層のみで実施 |
| D-8 | `safe_join_output` で全書き出しを `output/` 配下に固定 | Round1 C-3: realpath/symlink による外部書込みを構造的に防止 |
| D-9 | `PiiMaskingFilter` を全出力共通の前処理に固定（JSON含む） | Round1 C-2: JSON の氏名残存を防止。ID は突合のため非マスク |
| D-10 | テストは `unittest` に一本化（`pytest` 不採用） | Round1 M-1: 標準ライブラリのみ方針を厳守、外部依存ゼロ |
| D-11 | JSON `filters` は未指定時 `{}`（`null` 採用せず） | Round1 M-4: 設計書 §10.1 と統一 |
| D-12 | A-06 は `finding_key = a06:{staff_id}:{date}:{branch}` で case 代表を外す | Round3 Critical 1: `leaves`/`overtimes` を複数 case に重複配布する設計と `finding_key` が両立するよう、A-06 のみ case 依存を外して重複排除する |
| D-13 | `_pick_primary` はスコア降順→`pattern_id`→`record_id`/`application_id`→入力順で stable | Round3 Major 1: `severity` と `score_breakdown` が同一 Finding を指す不変条件を保証 |
| D-14 | JSON `items[].approver_statuses` は常に配列 | Round3 Major 2: モデル側複数値と JSON 出力の型を `list[str]` で統一。単一化ルールは持たない |
| D-15 | `safe_join_output` は「通常のパストラバーサル防止」まで | Round3 Major 3: `resolve(strict=False)` ベースのため TOCTOU や後置 symlink には踏み込まず、デモ用途の保証範囲を明確化 |

---

（以上）
