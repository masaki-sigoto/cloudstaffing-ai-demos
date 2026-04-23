# 技術仕様書: 端数処理チェッカー

> **プロジェクトコード**: 02_rounding-checker
> **バージョン**: 0.1（初版 / 要件 v0.4・設計 v0.1 対応）
> **作成日**: 2026-04-23
> **対象**: クラウドスタッフィング（人材派遣管理SaaS）セミナーデモ
> **読者**: Phase5（実装フェーズ）着手担当者

---

## 1. 仕様書の位置付け

### 1.1 要件定義書・設計書との対応
- 要件定義書 `docs/01_requirements.md` v0.4 … **なにを** 作るか
- 設計書 `docs/02_design.md` v0.1 … **どう** 作るか（モジュール分割・データモデル・CLI体系）
- 本書 … **コードに落とす直前の具体形**（関数シグネチャ・型・例外階層・テスト設計）

**トレーサビリティ**: §5 関数仕様のうち **10 モジュール（`main` / `config_loader` / `punch_parser` / `rounding` / `payroll` / `warnings_detector` / `explainer` / `comparator` / `engine` / `formatter`）は設計書 §3.1 の 10 モジュールに 1:1 対応**する。加えて、本仕様書では実装容易性のため **責務インフラ用の補助モジュール 3 つ（`exceptions.py` / `logging_config.py` / `build_flags.py`）を追加**している。これらは設計書 §3.1 の 10 モジュールと機能的な責務は重複せず（例外階層定義・ロギング初期化・デモビルド定数）、10 モジュールの基盤として共有されるため追加モジュールとして扱う。設計書 §7 の疑似コードを §6 で近似 Python へ展開する。追加 3 モジュールの差分は §3 と §5.11-5.12・§4.1（`build_flags`）で明示する（R3 レビュー指摘 Critical 1 対応）。

### 1.2 この仕様書がカバーする範囲
- 全モジュールの公開関数シグネチャ（型ヒント付き）
- 例外階層（`DemoError` を頂点とするツリー）
- 内部データモデル（`dataclass` 全フィールド）
- YAML / CSV / text / json / csv 各入出力スキーマ
- アルゴリズム近似コード（丸め・金額・Net・compare集計・24:00境界）
- CLI argparse 構造と終了コード
- ログ仕様・テスト設計

### 1.3 カバーしない範囲（Phase5 以降で決める）
- 色コード（ANSI）の具体RGB値（実装時に決定）
- サンプル YAML / CSV 同梱の最終バイト列（実装時に `samples/` へ作成）
- パッケージング（`pip install -e .`・`pyproject.toml` 等）…セミナーデモでは `python src/main.py` 直接実行で十分

### 1.4 実装着手の前提条件
- Python 3.10+ がローカルで動作
- `pip install pyyaml>=6.0` が可能
- 本書・要件書・設計書・Codexレビュー履歴（`docs/review-log.md`）の4点が揃っていること

---

## 2. 動作環境と依存

### 2.1 Python
- **最低要件**: Python `>= 3.10`
- **デモ実行環境の固定バージョン（R1 レビュー指摘 Major 3 対応 / 再現性確保）**:
  - セミナー登壇 PC は **Python 3.10.14**（macOS / Linux とも同一）で再現検証する。
  - 3.11 / 3.12 系でも動作する想定だが、デモ日の動作保証は 3.10.14 のみ。
- 使用する 3.10+ 機能: `match` 文、`str | None` 型表記（PEP 604）、`Path.is_relative_to`（3.9+）
- 起動時バージョンチェック必須（設計書 §2.1）

### 2.2 依存ライブラリ
| ライブラリ | バージョン | 用途 | 採否の判断 |
|---|---|---|---|
| `PyYAML` | `>= 6.0`（**デモ登壇機は 6.0.1 固定**） | YAML ルール定義の読み込み（`yaml.safe_load`） | **採用**（設計書 §2.1 に準拠）。標準ライブラリで YAML をパースする手段がないため、最小実装でも外部依存必須。`safe_load` のセキュリティ挙動を前提とする。 |
| `argparse` | 標準 | CLI パーサ | 採用 |
| `csv` | 標準 | CSV 読み書き | 採用 |
| `datetime` | 標準 | 日付バリデーション | 採用 |
| `json` | 標準 | JSON 出力 | 採用 |
| `dataclasses` | 標準 | ドメインモデル | 採用 |
| `logging` | 標準 | ログ | 採用 |
| `pathlib` | 標準 | `--out` パス検証 | 採用 |
| `uuid` | 標準 | `run_id` 生成 | 採用 |
| `pytest` | `>= 7.4`（dev のみ、デモ機検証は 7.4.4） | 単体テスト実行 | **dev 依存として採用**（R1 レビュー指摘 Minor 1）。デモ実行バイナリには含めず `tests/` 実行時のみ必要。`pip install pytest>=7.4` を README / 開発手順に明記。 |

> **PyYAML採用の最終判断**: 標準ライブラリのみでは YAML パース不可。要件書 §5 でも「YAMLのみ PyYAML 許容」と明記。最小実装の原則を維持しつつ YAML 依存は受け入れる。バージョンは 6.0+ に固定（`safe_load` 挙動が 5.x と異なる箇所を排除）。
>
> **依存バージョン固定の運用上の扱い（R3 レビュー指摘 Minor 3）**: 本仕様書では `requirements.txt` / `pyproject.toml` の完全な pin（例: `PyYAML==6.0.1`）を規定まで降りず、「依存宣言は範囲指定（`>=6.0`）を維持し、デモ登壇機での実績バージョンを併記する」方針を採用する。**残論点**: 完全 pin は Phase5 でパッケージングを決める際に `pyproject.toml` と合わせて決定する（本仕様書のスコープ外 / §1.3 パッケージング方針に準拠）。デモまでの期間は「登壇前チェックリストで `python -V` / `pip show pyyaml` の目視確認」で担保する（属人化を受容する見送り）。

### 2.3 OS / ロケール / 文字コード
- **OS**: macOS 12+ / Linux（セミナー登壇 PC 想定）
- **ロケール**: 非依存（表示は日本語固定、ソート処理なし）
- **文字コード**: 入出力 UTF-8 固定（CSV 入力のみ BOM 許容、出力は BOM なし）
- **タイムゾーン**: JST 想定だが本ツールは時刻文字列のみ扱い、TZ は持たない（日本の勤怠慣習前提 / 要件書 §7）
- **文字コード異常時の扱い（R1 レビュー指摘4 対応）**:
  - CSV / YAML / STDIN 読み込み時に `UnicodeDecodeError` を捕捉し、`PunchValidationError`（CSV/STDIN）または `ConfigValidationError`（YAML）に正規化して exit 2。
  - 対象: CP932 / Shift_JIS でエンコードされたファイル、UTF-8 と他コードの混在、壊れたバイト列。
  - メッセージ例:
    - `[ERROR] input file is not UTF-8: <path> (hint: re-save as UTF-8, BOM optional)`
    - `[ERROR] rule YAML is not UTF-8: <path>`
  - テスト: §10.2.12 で CP932 / 壊れた UTF-8 バイト列を用いた異常系を担保。

### 2.4 起動時バージョンチェック（実装必須）
```python
# main.py の先頭で実行
import sys
MIN_PY = (3, 10)
if sys.version_info < MIN_PY:
    sys.stderr.write(f"[ERROR] requires Python >=3.10 (got {sys.version.split()[0]})\n")
    sys.exit(2)

import yaml, re
MIN_YAML = (6, 0)

# R3 Minor 1 対応: `6.0.1rc1` 等のプレリリース文字列でも落ちないよう、各セグメントから
# 数字プレフィクスのみを取り出して int 化する。数字が見つからないセグメントは 0 扱い。
def _parse_yaml_version(ver: str) -> tuple[int, int]:
    parts = ver.split(".")[:2]
    out: list[int] = []
    for p in parts:
        m = re.match(r"^(\d+)", p)
        out.append(int(m.group(1)) if m else 0)
    while len(out) < 2:
        out.append(0)
    return (out[0], out[1])

if _parse_yaml_version(yaml.__version__) < MIN_YAML:
    sys.stderr.write(f"[ERROR] requires PyYAML >=6.0 (got {yaml.__version__})\n")
    sys.exit(2)
```

---

## 3. ディレクトリ構成（実装版）

```
02_rounding-checker/
├── docs/
│   ├── 01_requirements.md         ← 要件定義書 v0.4
│   ├── 02_design.md               ← 設計書 v0.1
│   ├── 03_spec.md                 ← 本書（技術仕様書 v0.1）
│   ├── context-alignment-notes.md ← CS文脈寄せメモ
│   └── review-log.md              ← Codexレビュー履歴
├── src/
│   ├── __init__.py                ← 空ファイル
│   ├── main.py                    ← CLIルーター / argparse / サブコマンド分岐
│   ├── engine.py                  ← simulate/compare/explain の集約エンジン
│   ├── config_loader.py           ← YAML → Rule 変換・スキーマ検証
│   ├── punch_parser.py            ← CLI文字列/CSV/STDIN → Punch[] 変換
│   ├── rounding.py                ← round_minutes / round_punch（丸めエンジン）
│   ├── payroll.py                 ← calc_pay（金額計算・整数演算）
│   ├── warnings_detector.py       ← check_rule_warnings（警告条件 a/b 判定）
│   ├── explainer.py               ← explain 出力（通常5ステップ / --demo 3ステップ）
│   ├── comparator.py              ← compare_rules（複数ルール並列・行単位丸め合算）
│   ├── formatter.py               ← text/json/csv 出力・免責制御・--out検証
│   ├── exceptions.py              ← DemoError 以下の例外階層（設計§3.1 対象外の補助モジュール）
│   ├── logging_config.py          ← logging 設定・色付け（設計§3.1 対象外の補助モジュール）
│   └── build_flags.py             ← `IS_DEMO_BUILD` 定数（設計§3.1 対象外の補助モジュール / デモ配布時は True 固定）
├── samples/
│   ├── rules/
│   │   ├── 1min.yml
│   │   ├── 15min_employee_friendly.yml
│   │   ├── 15min_company_friendly.yml
│   │   └── 30min_floor.yml
│   ├── rules/advanced/
│   │   └── 15min_with_overtime.yml   ← SHOULD参考（overtime は WARN で読み捨て）
│   └── punches.csv                   ← 匿名ID（EMP001等）10行程度
├── tests/                            ← pytest 想定（自動化は MAY）
│   ├── test_rounding.py
│   ├── test_payroll.py
│   ├── test_punch_parser.py
│   ├── test_config_loader.py
│   ├── test_warnings_detector.py
│   ├── test_comparator.py
│   ├── test_engine.py
│   └── test_main_cli.py
├── out/                              ← --out 出力先（.gitignore）
└── README.md
```

**各ファイルの役割（1行）** は §5 で詳細定義。

---

## 4. データスキーマ（実装レベル）

### 4.1 入力: 打刻 CSV（`samples/punches.csv`）

| 列名 | 型 | 制約 | 備考 |
|---|---|---|---|
| `date` | string | `YYYY-MM-DD`（ISO8601） | `datetime.date.fromisoformat` でパース可能であること |
| `employee_id` | string | `^[A-Z]{2,4}\d{3,6}$` | 例: `EMP001`, `STAFF0001` |
| `clock_in` | string | `H:MM` or `HH:MM`、`0:00..23:59` | 秒付き `HH:MM:SS` は不許可 |
| `clock_out` | string | 同上、かつ `> clock_in` | 同時刻も不許可 |

- ヘッダ行必須（1行目）。列順不同。
- エンコーディング UTF-8（BOM 許容）。
- **許可列 allowlist**: 上記4列以外が含まれる場合 `[ERROR] unexpected column (not in allowlist): <name>` → exit 2。
- **禁止列ブラックリスト**（`--allow-extra-columns` 時も拒否、大文字小文字・前後空白無視）:
  `name`, `employee_name`, `staff_name`, `full_name`, `client_name`, `company_name`,
  `dispatch_destination`, `email`, `phone`, `address`, `birth_date`
- `--allow-extra-columns` は **デモビルドでは argparse 未登録**。判定は `src/build_flags.py` の **定数 `IS_DEMO_BUILD`** を参照する（環境変数 `DEMO_BUILD` ではなくソース定数にハードコード）。
  - 配布時は `IS_DEMO_BUILD = True` に固定した状態でセミナー PC へ配る。
  - 実行時の環境変数では上書きできない（R1 レビュー指摘 Major 4 対応: 環境変数抜け穴の封鎖）。
  - 開発時は `src/build_flags.py` を直接編集して `IS_DEMO_BUILD = False` に切り替える（symlink 運用は採用しない。単一ファイル定数 + デモ前チェックリストで簡素化 / R2 レビュー指摘 Major 1 対応）。
  - **デモ前チェックリスト**: 配布前に `grep -n "^IS_DEMO_BUILD" src/build_flags.py` が `IS_DEMO_BUILD = True` を返すことを目視確認する。

### 4.2 入力: CLI 単発打刻（`--punch`）
- 書式: `"<clock_in>,<clock_out>"`（例: `"9:03,18:07"` / `"09:03,18:07"`）
- `date` / `employee_id` は `None` で Punch を生成。

### 4.3 入力: YAML ルール定義（`samples/rules/*.yml`）

```yaml
# 必須キー
name: string                  # 表示用ルール名（例: "15分丸め（減少方向 / 会社有利）"）
unit_minutes: int             # 許容: 1 | 5 | 15 | 30 | 60
clock_in:
  direction: string           # 許容: "ceil" | "floor" | "round"
clock_out:
  direction: string           # 許容: "ceil" | "floor" | "round"

# 任意キー
description: string
break:
  type: "fixed"               # MUST では "fixed" のみ
  minutes: int                # >= 0、未指定時 0
amount_rounding: string       # 許容: "floor"（デフォルト） | "half_up" | "ceil"

# SHOULD（読み捨て + WARN）
overtime: {...}               # 検出時 [WARN] を出して無視
```

### 4.4 出力: text フォーマット
- 免責は stdout 先頭に 1 行。
- 本体は固定幅レイアウト（要件書 §10.5-10.8 のサンプル準拠）。
- 色付け: TTY かつ `--no-color` 未指定時のみ ANSI を付与。

### 4.5 出力: JSON スキーマ（`--format json`）

```json
{
  "meta": {
    "run_id": "string",
    "subcommand": "simulate|compare|explain",
    "generated_at": "YYYY-MM-DDTHH:MM:SS+09:00",
    "rule_name": "string | list[string]"
  },
  "rows": [
    {
      "date": "YYYY-MM-DD | null",
      "employee_id": "string | null",
      "clock_in_raw": "HH:MM",
      "clock_out_raw": "HH:MM",
      "clock_in_rounded": "HH:MM",
      "clock_out_rounded": "HH:MM",
      "delta_in_min": 0,
      "delta_out_min": 0,
      "gross_min": 0,
      "break_min": 0,
      "net_min": 0,
      "pay_yen": null
    }
  ],
  "totals": {
    "days": 0,
    "net_min": 0,
    "pay_yen": null
  },
  "warnings": ["string"]
}
```

- **`generated_at` のタイムゾーン**（R1 レビュー指摘 Minor 2）: ISO8601 オフセット付き文字列固定（JST `+09:00`）。実装: `datetime.datetime.now(tz=datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="seconds")`。naive 時刻は禁止。
- **再現性と `meta.run_id` / `meta.generated_at` の扱い**（R3 レビュー指摘 Major 1 対応）: 要件 §5 の「同じ入力なら常に同じ出力」を満たすため、`--deterministic` フラグ（§7.1.1）が **`True` のとき** は以下を固定値に差し替える:
  - `meta.run_id` = `"00000000-0000-0000-0000-000000000000".replace("-","")[:12]` = `"000000000000"` 固定
  - `meta.generated_at` = `"1970-01-01T00:00:00+09:00"` 固定（Epoch + JST）
  - `[INFO] summary` の `run_id=...` も `000000000000` 固定
  既定（`--deterministic` 未指定）では従来通り UUID4 + 現在時刻で出力。golden 比較テスト・CI 再現性・デモ録画の再現比較には `--deterministic` を使う。本フラグは全サブコマンドの共通オプションとする。
- **`rule_name` の型確定**（R2 レビュー指摘 Minor 2）: サブコマンド別に固定する。
  - `simulate` / `explain` / `validate`: `string`（単一ルール）
  - `compare`: `list[string]`（YAML `name` 値の配列、読み込み順）

compare 時は `rows` の代わりに `comparison` キー:
```json
"comparison": [
  {
    "rule_name": "string",
    "gross_min": 0,
    "net_min": 0,
    "pay_yen": 0,
    "diff_from_baseline_yen": 0
  }
]
```

> `gross_min` は常時出力（`--show-gross` 未指定でも含める）。text / csv 表示のみ `--show-gross` で列表示を切り替える。これにより formatter での再計算は不要（R1 レビュー指摘 Major 1 対応）。

### 4.6 出力: CSV スキーマ（`--format csv`）

**simulate**（ヘッダ固定）:
```
date,employee_id,clock_in_raw,clock_out_raw,clock_in_rounded,clock_out_rounded,delta_in_min,delta_out_min,gross_min,break_min,net_min,pay_yen
```

**compare**（`--show-gross` 未指定 / 既定）:
```
rule_name,net_min,pay_yen,diff_from_baseline_yen
```

**compare**（`--show-gross` 指定）:
```
rule_name,gross_min,net_min,pay_yen,diff_from_baseline_yen
```

- `ComparisonRow` は常に `gross_min` を保持している。CSV/text 出力時のみ `--show-gross` で列の有無を切り替える。formatter 側で Gross を再計算してはならない（R1 レビュー指摘 Major 1 対応 / 計算一貫性ルール）。

- 区切り文字: `,`（標準 `csv.writer` デフォルト）
- 改行: `\n`（LF）
- `pay_yen` が `None` の場合は空欄。

### 4.7 内部データモデル（`dataclass`）

```python
from dataclasses import dataclass
from typing import Literal

Direction = Literal["ceil", "floor", "round"]
AmountRounding = Literal["floor", "half_up", "ceil"]

@dataclass(frozen=True)
class Punch:
    date: str | None              # "YYYY-MM-DD" or None
    employee_id: str | None       # 匿名ID or None
    clock_in_min: int             # 0..1439（当日0時基点の分）
    clock_out_min: int            # 0..1439、かつ > clock_in_min

@dataclass(frozen=True)
class RoundingSide:
    direction: Direction

@dataclass(frozen=True)
class Rule:
    name: str
    description: str
    unit_minutes: int             # 1 | 5 | 15 | 30 | 60
    clock_in: RoundingSide
    clock_out: RoundingSide
    break_minutes: int            # >= 0
    amount_rounding: AmountRounding

@dataclass(frozen=True)
class RoundedPunch:
    original: Punch
    clock_in_min_rounded: int     # 0..1439（1440 は clock_in では不許可）
    clock_out_min_rounded: int    # 0..1440（1440 = 24:00 特殊値）
    delta_in_min: int             # 丸め後 - 丸め前
    delta_out_min: int

@dataclass
class SimulationRow:
    punch: Punch
    rounded: RoundedPunch
    gross_min: int
    break_min: int
    net_min: int
    pay_yen: int | None           # --hourly 未指定時 None

@dataclass
class ComparisonRow:
    rule_name: str
    gross_min: int                # 丸め後合計（休憩控除前）。--show-gross 用に常時保持
    net_min: int
    pay_yen: int
    diff_from_baseline_yen: int

@dataclass
class ExplainStep:
    label: str                    # "[ステップ1] 出勤時刻の丸め" 等
    detail_lines: list[str]       # 複数行トレース

@dataclass
class ExplainTrace:
    punch: Punch
    rule: Rule
    steps: list[ExplainStep]
    net_min: int
    warnings: list[str]
    demo: bool
```

---

## 5. 関数/クラス仕様

### 5.1 `main.py` — CLI ルーター
- **責務**: argparse 定義、サブコマンド分岐、起動時バージョンチェック、exit code 管理。
- **公開API**:
  ```python
  def main(argv: list[str] | None = None) -> int:
      """CLI エントリポイント。exit code を int で返す。argv=None で sys.argv[1:] を使う。"""

  def build_parser() -> argparse.ArgumentParser:
      """argparse 定義を構築。テストから直接呼べるように分離。"""
  ```
- **例外**: 捕捉対象は `DemoError` 系のみ。未捕捉例外は `--debug` 時はトレース、それ以外は簡潔メッセージで exit 1。
- **副作用**: stdout / stderr / ファイル I/O、`sys.exit`。

### 5.2 `config_loader.py` — 設定ローダ
- **責務**: YAML → `Rule` 変換、スキーマ検証、`overtime` 検出時の WARN。
- **公開API**:
  ```python
  def load_rule(path: str) -> Rule:
      """YAML ファイルを読み込み Rule に変換。違反時 ConfigValidationError。"""

  def load_rule_from_dict(data: dict, source: str = "<dict>") -> Rule:
      """パース済み dict から Rule を生成（テスト容易性）。"""
  ```
- **例外**: `ConfigValidationError`（YAML パース失敗、必須キー欠損、値域違反、**`FileNotFoundError` / `PermissionError` / `OSError` / `IsADirectoryError` 等の I/O 例外も正規化** / R2 レビュー指摘 Critical 2 対応）。
- **副作用**: `overtime` キー検出時 stderr に `[WARN]` 1行。ファイル読み込みのみ。

### 5.3 `punch_parser.py` — 打刻パーサ
- **責務**: CLI 文字列 / CSV / STDIN → `Punch[]` 変換、匿名ID・時刻・日付の検証、行スキップ警告。
- **公開API**:
  ```python
  def parse_punch_arg(s: str) -> Punch:
      """'9:03,18:07' 形式を Punch に変換（date/employee_id は None）。"""

  def parse_punch_csv(path: str, allow_extra_columns: bool = False) -> list[Punch]:
      """CSV ファイルを読み込み Punch[] を返す。不正行は skip + WARN。"""

  def parse_punch_stdin(allow_extra_columns: bool = False) -> list[Punch]:
      """STDIN から CSV 形式で読み込み。"""

  def parse_time(s: str) -> int:
      """'H:MM' / 'HH:MM' を分数(0..1439)に変換。'HH:MM:SS' は拒否。"""

  def format_minutes(m: int) -> str:
      """分数(0..1440)を 'HH:MM' 形式へ。1440 は '24:00'。"""

  EMPLOYEE_ID_PATTERN: re.Pattern  # ^[A-Z]{2,4}\d{3,6}$
  ALLOWED_COLUMNS: frozenset = frozenset({"date", "employee_id", "clock_in", "clock_out"})
  FORBIDDEN_COLUMNS: frozenset   # §4.1 参照
  ```
- **例外**: `PunchValidationError`（CSV必須列欠損、allowlist違反、禁止列検出、時刻パース失敗の最上位表現）。CSV の `FileNotFoundError` / `PermissionError` / `IsADirectoryError` / `OSError` および `csv.Error`（ヘッダ解析段階の致命）も **`PunchValidationError` に正規化** する（R2 レビュー指摘 Critical 2 対応）。行単位の `csv.Error` は `PunchRowError` に包んで `[WARN] line N: ...` + skip 継続。
- **副作用**: 行単位エラーは stderr に `[WARN] line N: <reason>` を出力しつつ処理継続。致命時は例外を投げて呼び出し側で exit 2。
- **STDIN 読み込みの決定（R2 レビュー指摘 Minor 3 対応）**: `parse_punch_stdin` は `sys.stdin.buffer.read()` でバイト列を取得後、`bytes.decode("utf-8-sig")` で明示デコードする。ロケール依存の `sys.stdin`（テキストストリーム）は使用しない。`UnicodeDecodeError` は `PunchValidationError` に正規化。

### 5.4 `rounding.py` — 丸めエンジン
- **責務**: 分単位丸め計算、真理値表（要件 §2.4）の実装。
- **公開API**:
  ```python
  def round_minutes(m: int, unit: int, direction: Direction) -> int:
      """0..1439 の分数を unit 分単位で direction 方向に丸める。
         戻り値は 0..1440（1440 は 24:00 特殊値、退勤 ceil のみ）。"""

  def round_punch(punch: Punch, rule: Rule) -> RoundedPunch:
      """Punch に rule.clock_in / clock_out のルールを適用。
         clock_in_min_rounded == 1440 なら RoundingBoundaryError を投げる。"""
  ```
- **例外**: `RoundingBoundaryError`（clock_in が 24:00 に繰り上がった場合）。
- **副作用**: なし（純関数）。

### 5.5 `payroll.py` — 金額計算
- **責務**: `支払額 = round_by(hourly × minutes / 60, amount_rounding)` を整数演算で実装。
- **公開API**:
  ```python
  def calc_pay(minutes: int, hourly_yen: int, amount_rounding: AmountRounding) -> int:
      """整数演算のみで円未満を floor/half_up/ceil に丸めた支払額を返す。
         不正引数（minutes<0 / hourly_yen<0 / 未知 amount_rounding）は PayrollError。"""
  ```
- **例外**: `PayrollError`（`DemoError` 系）に **一本化**。R1 レビュー指摘3対応。
  - `ValueError` を個別に投げずに、`PayrollError` で統一する。これにより `main.py` の `except DemoError` が漏れなく捕捉し exit 2 に変換される（exit 1 揺れを排除）。
- **副作用**: なし（純関数、float 不使用）。

### 5.6 `warnings_detector.py` — 警告検出
- **責務**: 要件 §4.1 M4 の警告条件 (a)(b) を判定。
- **公開API**:
  ```python
  def check_rule_warnings(rule: Rule) -> list[str]:
      """条件(a): clock_in=ceil & clock_out=floor → 減少方向
         条件(b): clock_in=floor & clock_out=ceil & unit>=15 → 増加方向
         上記以外は空リスト。"""
  ```
- **例外**: なし。
- **副作用**: なし（純関数）。

### 5.7 `explainer.py` — 逆算説明
- **責務**: explain サブコマンドの逐次トレース生成、`--demo` 短縮モード。
- **公開API**:
  ```python
  def explain(punch: Punch, rule: Rule, break_min: int, demo: bool = False) -> ExplainTrace:
      """通常モード: 5ステップ（出勤丸め/退勤丸め/Gross/控除/Net）。
         demo=True: 3ステップ（丸め/控除/最終）。
         引数の break_min は「確定済み最終値」。優先順位の解決は engine 側（run_explain）で完了している。"""
  ```
- **break_min の責務分担（R1 レビュー指摘 Major 2 対応）**:
  - **engine.run_explain** が `--break > rule.break_minutes > 0` の優先順位で最終値を確定する。
  - `explain()` は確定値のみを受け取り、分岐判断をしない。これによりテスト容易性・責務重複を排除。
- **例外**: 呼び出し側の `round_punch` から伝播する `RoundingBoundaryError`。
- **副作用**: なし（トレースデータを返すのみ、出力は `formatter` 側）。

### 5.8 `comparator.py` — 比較エンジン
- **責務**: 複数ルール並列計算、Net基準の差分算出、共通 `amount_rounding` / `break` 適用。
- **公開API**:
  ```python
  def compare_rules(
      punches: list[Punch],
      rules: list[Rule],
      hourly_yen: int,
      break_min_cli: int | None,
      amount_rounding_cli: AmountRounding | None,
      baseline: str | int | None = None,
  ) -> tuple[list[ComparisonRow], list[str]]:
      """要件 §4.1 M5 の公平性担保を実装。
         - amount_rounding: CLI > デフォルト 'floor'（YAML値は無視、不一致なら [WARN]）
         - break:           CLI > 0（YAML値は無視、不一致なら [WARN]）
         - 合算方式:         打刻1行ごとに calc_pay で丸めてから合算（設計 C.10）
         - baseline:        name文字列 or 0始まりindex、未指定は rules[0]。
           解決不能なら BaselineResolutionError。
         - 戻り値:           (ComparisonRow[], warnings[]) のタプル。warnings には
           共通 amount_rounding 不一致・共通 break 不一致・gross<0 反転・overtime 読み捨て
           など、compare 中に収集した `[WARN]` 行の本文（プレフィクスなし）を詰める。
           R3 Major 2 対応: JSON `warnings` 出力の源泉を単一化する。"""

  def resolve_baseline(rules: list[Rule], baseline: str | int | None) -> int:
      """baseline 文字列/int を rules 内のインデックスに解決。解決不能なら例外。"""
  ```
- **例外**: `BaselineResolutionError`（name 不一致・index 範囲外）。
- **副作用**: `amount_rounding` / `break` 不一致検出時、stderr に `[WARN]` を各1回出力。

### 5.9 `engine.py` — 集約エンジン
- **責務**: simulate / compare / explain / validate の高レベル手続き。
- **公開API**:
  ```python
  def run_simulate(
      rule: Rule, punches: list[Punch],
      break_min_cli: int | None, hourly_yen: int | None,
  ) -> tuple[list[SimulationRow], list[str]]:
      """各Punchに rounding.round_punch → gross → net → (hourly指定時)pay を適用。
         Net計算で休憩過大なら [WARN] を返り値 warnings に含める。"""

  def run_compare(
      rules: list[Rule], punches: list[Punch],
      hourly_yen: int, break_min_cli: int | None,
      amount_rounding_cli: AmountRounding | None,
      baseline: str | int | None,
  ) -> tuple[list[ComparisonRow], list[str]]:
      """compare_rules の薄いラッパ。戻り値は (rows, warnings)。warnings は
         formatter.emit_comparison() の warnings 引数へそのまま渡す（R3 Major 2）。"""

  def run_explain(rule: Rule, punch: Punch, break_min_cli: int | None, demo: bool) -> ExplainTrace:
      """break 優先順位を engine 側で確定してから explain() に渡す:
         effective_break = break_min_cli if break_min_cli is not None else rule.break_minutes
         explain(punch, rule, break_min=effective_break, demo=demo)"""

  def run_validate(path: str) -> None:
      """YAML を読み、スキーマ違反があれば ConfigValidationError を投げる。"""
  ```
- **例外**: `DemoError` 系を上位へ伝播。
- **副作用**: 各種 `[WARN]` を stderr に出力（休憩過大、overtime 検出、compare 不一致）。

### 5.10 `formatter.py` — 出力フォーマッタ
- **責務**: text / json / csv 出力、免責表示の出力先制御、`--out` パス検証、ANSI 色付け。
- **公開API**:
  ```python
  def emit_simulate(
      rows: list[SimulationRow],
      rule: Rule,
      warnings: list[str],
      fmt: Literal["text", "json", "csv"],
      out_path: str | None,
      quiet: bool,
      no_color: bool,
      run_id: str,
  ) -> None: ...

  def emit_comparison(
      rows: list[ComparisonRow],
      rules: list[Rule],
      punches: list[Punch],
      hourly_yen: int,
      break_min: int,
      amount_rounding: AmountRounding,
      warnings: list[str],
      fmt: Literal["text", "json", "csv"],
      out_path: str | None,
      quiet: bool,
      no_color: bool,
      show_gross: bool,
      run_id: str,
  ) -> None:
      """compare 出力。warnings は run_compare が返したリストをそのまま受け取り、
         JSON 出力時は §4.5 の `warnings` キーへ格納する（R3 Major 2 対応）。
         text / csv 出力では warnings は JSON に含めず、compare_rules 実行時に
         stderr へ出力済みの [WARN] と重複表示しない。"""

  def emit_explain(trace: ExplainTrace, out_path: str | None, quiet: bool, no_color: bool, run_id: str) -> None:
      """explain は text 専用。json/csv は呼ばれないことを前提（main.py 側で事前チェック）。"""

  def validate_out_path(path_str: str) -> Path:
      """正規化後の絶対パスが cwd 配下であることを検証。範囲外で OutPathError。"""

  DISCLAIMER: str  # 固定文言（要件 §5）
  ```
- **例外**: `OutPathError`（cwd 外、親ディレクトリ不存在）。
- **副作用**: stdout / stderr / ファイル書き出し。

### 5.11 `exceptions.py` — 例外階層
§8 で詳述。

### 5.12 `logging_config.py` — ロギング設定
- **責務**: `logging` 初期化、色付きフォーマッタ、`--quiet` / `--debug` 反映。
- **公開API**:
  ```python
  def setup_logging(quiet: bool, debug: bool, no_color: bool) -> logging.Logger:
      """root logger を設定して返す。stderr 出力、ANSI 色は TTY かつ no_color=False 時のみ。"""
  ```

---

## 6. アルゴリズム詳細

### 6.1 丸め `round_minutes`（設計 §7.1 を near-Python へ）

```python
def round_minutes(m: int, unit: int, direction: Direction) -> int:
    if not (0 <= m <= 1439):
        raise ValueError(f"minute out of range: {m}")
    if unit not in (1, 5, 15, 30, 60):
        raise ValueError(f"unit must be 1/5/15/30/60: {unit}")

    if direction == "floor":
        return (m // unit) * unit
    if direction == "ceil":
        q, r = divmod(m, unit)
        return (q + 1) * unit if r else m  # 割り切れれば据え置き
    if direction == "round":
        # half-up: 余りが unit の半分以上なら繰り上げ
        q, r = divmod(m, unit)
        return (q + 1) * unit if r * 2 >= unit else q * unit
    raise ValueError(f"unknown direction: {direction}")
```

> **`ValueError` の扱い（R2 レビュー指摘 Major 3 対応）**: `round_minutes` / `format_minutes` の `ValueError` は**純関数レイヤの契約違反（プログラミングバグ）を検出する用途のみ**に限定する。`main` から到達可能な経路では以下を保証することで `ValueError` が外に漏れない:
> - `m` の範囲 `0..1439` は `parse_time` が保証（`TimeFormatError` → `PunchRowError` で先に除外される）。
> - `unit` の値は `load_rule_from_dict` が `ConfigValidationError` で先に除外する。
> - `direction` の値は `load_rule_from_dict` が `ConfigValidationError` で先に除外する。
>
> したがって `main` の `except DemoError` で捕捉できなくても exit 1 に落ちるのは**バグ発覚時のみ**であり、正常フローでは発生しない。この契約をテスト（§10.2.1 `round_minutes` の異常値は直接呼び出しのみ）で担保する。

### 6.2 `round_punch` と 24:00 境界

```python
def round_punch(punch: Punch, rule: Rule) -> RoundedPunch:
    in_rounded = round_minutes(punch.clock_in_min, rule.unit_minutes, rule.clock_in.direction)
    out_rounded = round_minutes(punch.clock_out_min, rule.unit_minutes, rule.clock_out.direction)

    # 24:00 境界: clock_in 側は 1440 を拒否、clock_out 側は許容
    if in_rounded >= 1440:
        raise RoundingBoundaryError("clock_in rounded to 24:00 is invalid")
    # out_rounded は 1440 まで可（"24:00" 表示）

    # Gross 反転（out_rounded < in_rounded）は compute_net で専用WARN扱い（R2 Major 4）
    return RoundedPunch(
        original=punch,
        clock_in_min_rounded=in_rounded,
        clock_out_min_rounded=out_rounded,
        delta_in_min=in_rounded - punch.clock_in_min,
        delta_out_min=out_rounded - punch.clock_out_min,
    )
```

> **`gross<0` 反転の扱い（R2 レビュー指摘 Major 4 対応）**: 短時間打刻 + `clock_in=ceil` / `clock_out=floor` の組合せで `out_rounded < in_rounded` が発生し得る。このとき `gross_min = out_rounded - in_rounded` は負値になる。本仕様では**エラー化せず、0 クランプ + 専用 WARN** で処理継続とする（デモ中断を避け、業務的には「丸めで 0 分に縮んだ」と説明する）。休憩過大警告（`break_min > gross`）とは別メッセージを使って事実とズレないようにする（§6.4 参照）。

### 6.3 金額計算 `calc_pay`（設計 §7.6 / 整数演算）

```python
def calc_pay(minutes: int, hourly_yen: int, amount_rounding: AmountRounding) -> int:
    # 例外は PayrollError に一本化（R1 レビュー指摘3対応）
    if minutes < 0 or hourly_yen < 0:
        raise PayrollError(f"minutes/hourly must be >= 0 (got minutes={minutes}, hourly={hourly_yen})")
    num = hourly_yen * minutes
    q, r = divmod(num, 60)
    if amount_rounding == "floor":
        return q
    if amount_rounding == "ceil":
        return q + (1 if r > 0 else 0)
    if amount_rounding == "half_up":
        return q + (1 if r * 2 >= 60 else 0)
    raise PayrollError(f"unknown amount_rounding: {amount_rounding!r}")
```

### 6.4 Net 算出（設計 §7.2）

```python
def compute_net(rounded: RoundedPunch, break_min: int) -> tuple[int, list[str]]:
    warnings = []
    gross_min = rounded.clock_out_min_rounded - rounded.clock_in_min_rounded
    # Gross 反転（R2 Major 4）: 専用 WARN + 0 クランプしてから控除判定
    if gross_min < 0:
        warnings.append(
            f"[WARN] gross became negative after rounding "
            f"(in={rounded.clock_in_min_rounded}, out={rounded.clock_out_min_rounded}); "
            f"clamped to 0 (punch={rounded.original.date} {rounded.original.employee_id})"
        )
        gross_min = 0
    net_raw = gross_min - break_min
    if net_raw < 0 and gross_min > 0:
        # 通常の休憩過大（gross>0 だが break が超過）
        warnings.append(
            f"[WARN] break_minutes ({break_min}) exceeds gross ({gross_min}); "
            f"net clamped to 0 (punch={rounded.original.date} {rounded.original.employee_id})"
        )
    return max(0, net_raw), warnings
```

> **警告の分離ルール**: `gross<0`（反転）と `break>gross`（休憩過大）は根本原因が異なるため**別メッセージ**とする。反転時は休憩過大メッセージを**出さない**（事実とズレるため / R2 Major 4）。

### 6.5 compare の集計（設計 §7.5 C.10 / 行単位丸め合算）

```python
def compare_rules(punches, rules, hourly_yen, break_min_cli, amount_rounding_cli, baseline):
    warnings: list[str] = []  # R3 Major 2: JSON warnings の源泉

    # 1. 共通 amount_rounding
    effective_ar = amount_rounding_cli or "floor"
    yaml_ars = {r.amount_rounding for r in rules}
    if any(ar != effective_ar for ar in yaml_ars):
        msg = (
            "compare では共通 amount_rounding を適用します "
            f"(有効値={effective_ar}, YAML値は無視): {sorted(yaml_ars)}"
        )
        _log.warning(msg)
        warnings.append(msg)

    # 2. 共通 break
    effective_break = break_min_cli if break_min_cli is not None else 0
    yaml_breaks = {r.break_minutes for r in rules}
    if any(b != effective_break for b in yaml_breaks):
        msg = (
            f"compare では共通 break={effective_break} を適用します "
            f"(YAML値は無視): {sorted(yaml_breaks)}"
        )
        _log.warning(msg)
        warnings.append(msg)

    # 3. baseline 解決（§6.11 のルールで統一）
    baseline_index = resolve_baseline(rules, baseline)  # 数字文字列は index 優先

    # 4. 各 Rule について行単位丸め合算（gross も累積して保持）
    per_rule = []
    for rule in rules:
        total_gross = 0
        total_net = 0
        total_pay = 0
        for p in punches:
            rp = round_punch(p, rule)
            gross = rp.clock_out_min_rounded - rp.clock_in_min_rounded
            # R2 Major 4: gross<0 は 0 クランプ（WARN は compute_net 経由で一貫出力）
            if gross < 0:
                msg = (
                    f"gross became negative after rounding "
                    f"(rule={rule.name}, in={rp.clock_in_min_rounded}, "
                    f"out={rp.clock_out_min_rounded}); clamped to 0"
                )
                _log.warning(msg)
                warnings.append(msg)
                gross = 0
            net = max(0, gross - effective_break)
            total_gross += gross
            total_net += net
            total_pay += calc_pay(net, hourly_yen, effective_ar)  # ★行単位で丸め
        per_rule.append((rule.name, total_gross, total_net, total_pay))

    # 5. baseline との差
    baseline_pay = per_rule[baseline_index][3]
    rows = [
        ComparisonRow(name, gross, net, pay, pay - baseline_pay)
        for name, gross, net, pay in per_rule
    ]
    return rows, warnings  # R3 Major 2: (rows, warnings) のタプル
```

### 6.6 YAML 読み込みと `overtime` 読み捨て

```python
def load_rule(path: str) -> Rule:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError as e:
        # 入力由来のI/O例外を正規化（R2 レビュー指摘 Critical 2）
        raise ConfigValidationError(f"rule YAML not found: {path}") from e
    except IsADirectoryError as e:
        raise ConfigValidationError(f"rule YAML path is a directory: {path}") from e
    except PermissionError as e:
        raise ConfigValidationError(f"permission denied reading rule YAML: {path}") from e
    except OSError as e:
        # その他 I/O 障害（壊れたシンボリックリンク等）も DemoError に包む
        raise ConfigValidationError(f"failed to read rule YAML: {path} ({e})") from e
    except UnicodeDecodeError as e:
        # CP932 / 壊れた UTF-8 を正規化（R1 レビュー指摘4）
        raise ConfigValidationError(
            f"rule YAML is not UTF-8: {path} (hint: re-save as UTF-8)"
        ) from e
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"failed to parse YAML: {e}") from e
    if not isinstance(data, dict):
        raise ConfigValidationError("YAML root must be a mapping")
    return load_rule_from_dict(data, source=path)

def load_rule_from_dict(data: dict, source: str) -> Rule:
    # 必須キー検証
    for key in ("name", "unit_minutes", "clock_in", "clock_out"):
        if key not in data:
            raise ConfigValidationError(f"{source}: missing required key '{key}'")
    # unit_minutes（int 厳格チェック、bool 排除）
    unit = data["unit_minutes"]
    if not isinstance(unit, int) or isinstance(unit, bool) or unit not in (1, 5, 15, 30, 60):
        raise ConfigValidationError(
            f"{source}: unit_minutes must be int in (1/5/15/30/60), got {unit!r}"
        )
    # direction（clock_in / clock_out は dict 必須）
    def _dir(block, side):
        if not isinstance(block, dict):
            raise ConfigValidationError(
                f"{source}: {side} must be a mapping with 'direction' key, got {type(block).__name__}"
            )
        d = block.get("direction")
        if d not in ("ceil", "floor", "round"):
            raise ConfigValidationError(
                f"{source}: {side}.direction must be ceil/floor/round, got {d!r}"
            )
        return RoundingSide(direction=d)
    # break（None 許容 / dict 必須 / minutes は int 変換失敗もエラー）
    brk_raw = data.get("break")
    if brk_raw is None:
        break_min = 0
    else:
        if not isinstance(brk_raw, dict):
            raise ConfigValidationError(
                f"{source}: break must be a mapping or null, got {type(brk_raw).__name__}"
            )
        btype = brk_raw.get("type", "fixed")
        if btype != "fixed":
            raise ConfigValidationError(
                f"{source}: break.type must be 'fixed' in MUST scope (got {btype!r})"
            )
        try:
            break_min = int(brk_raw.get("minutes", 0))
        except (TypeError, ValueError) as e:
            raise ConfigValidationError(
                f"{source}: break.minutes must be a non-negative integer ({e})"
            ) from e
        if break_min < 0:
            raise ConfigValidationError(f"{source}: break.minutes must be >= 0")
    # amount_rounding
    ar = data.get("amount_rounding", "floor")
    if ar not in ("floor", "half_up", "ceil"):
        raise ConfigValidationError(
            f"{source}: amount_rounding must be floor/half_up/ceil, got {ar!r}"
        )
    # overtime: 読み捨て + WARN
    if "overtime" in data:
        _log.warning("overtime is not applied in this build (SHOULD scope)")
    # R3 Minor 2 対応: name/description は str 限定（暗黙の str() 変換はしない）
    name_val = data["name"]
    if not isinstance(name_val, str):
        raise ConfigValidationError(
            f"{source}: name must be str, got {type(name_val).__name__}"
        )
    desc_val = data.get("description", "")
    if not isinstance(desc_val, str):
        raise ConfigValidationError(
            f"{source}: description must be str, got {type(desc_val).__name__}"
        )
    return Rule(
        name=name_val,
        description=desc_val,
        unit_minutes=unit,
        clock_in=_dir(data["clock_in"], "clock_in"),
        clock_out=_dir(data["clock_out"], "clock_out"),
        break_minutes=break_min,
        amount_rounding=ar,
    )
```

> **型バリデーション方針（R1 レビュー指摘2 対応）**: YAML は任意型のため、`clock_in`/`clock_out` が dict でないケース（`AttributeError`）、`break.minutes` が文字列や None などで `int()` が失敗するケース（`TypeError`/`ValueError`）を **すべて `ConfigValidationError` に正規化** する。`load_rule_from_dict` から出る例外は `DemoError` 系のみ、という契約を守り、想定外例外が exit 1 に漏れない。

### 6.7 CSV 読み込み + allowlist

```python
def parse_punch_csv(path: str, allow_extra_columns: bool = False) -> list[Punch]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            # R3 Major 3: 正規化マップを生成し、以降は canonical キーで dict を作り直す
            header_map = _validate_header(header, allow_extra_columns)
            punches = []
            for idx, row in enumerate(reader, start=2):  # 1行目=ヘッダ
                try:
                    canonical_row = {header_map[k]: v for k, v in row.items() if k in header_map}
                    punches.append(_row_to_punch(canonical_row, idx))
                except PunchRowError as e:
                    _log.warning(f"line {idx}: {e}")
                    continue
                except csv.Error as e:
                    # 行単位のCSV構造エラーは PunchRowError に包んで継続（R2 Critical 2）
                    _log.warning(f"line {idx}: CSV parse error: {e}")
                    continue
            return punches
    except FileNotFoundError as e:
        # 入力由来のI/O例外を正規化（R2 レビュー指摘 Critical 2）
        raise PunchValidationError(f"punch CSV not found: {path}") from e
    except IsADirectoryError as e:
        raise PunchValidationError(f"punch CSV path is a directory: {path}") from e
    except PermissionError as e:
        raise PunchValidationError(f"permission denied reading punch CSV: {path}") from e
    except OSError as e:
        raise PunchValidationError(f"failed to read punch CSV: {path} ({e})") from e
    except UnicodeDecodeError as e:
        # CP932 / 壊れた UTF-8 / 混在エンコーディングを正規化（R1 レビュー指摘4）
        raise PunchValidationError(
            f"input file is not UTF-8: {path} (hint: re-save as UTF-8, BOM optional)"
        ) from e
    except csv.Error as e:
        # ヘッダ解析段階の致命エラー（例: ヌルバイト混入）も正規化
        raise PunchValidationError(f"failed to parse CSV header: {path} ({e})") from e

def _validate_header(header: list[str], allow_extra: bool) -> dict[str, str]:
    """ヘッダを検証し、raw → canonical のマップを返す。
       R3 Major 3 対応: 行変換に渡すキー正規化ルールを仕様として固定化する。
       - raw: 元ヘッダ（空白・大小文字そのまま）
       - canonical: `strip().lower()` 済みの ALLOWED_COLUMNS 名（`_row_to_punch` が前提とするキー）
       重複 canonical（例: `clock_in` と `Clock_In` の同時指定）は拒否。"""
    normalized = [h.strip().lower() for h in header]
    # 禁止列（ブラックリスト）は常に拒否 → ForbiddenColumnError（R2 Major 2: 階層と擬似コードを一致）
    forbidden_hit = [h for h in normalized if h in FORBIDDEN_COLUMNS]
    if forbidden_hit:
        raise ForbiddenColumnError(f"forbidden column (PII) detected: {forbidden_hit[0]}")
    # 必須列（汎用 PunchValidationError）
    missing = ALLOWED_COLUMNS - set(normalized)
    if missing:
        raise PunchValidationError(f"CSV missing required columns: {sorted(missing)}")
    # 許可列以外 → ColumnNotAllowedError（R2 Major 2）
    extras = [h for h in normalized if h not in ALLOWED_COLUMNS]
    if extras and not allow_extra:
        raise ColumnNotAllowedError(f"unexpected column (not in allowlist): {extras[0]}")
    # R3 Major 3: raw→canonical マップを構築（allowlist 列のみ含める）
    header_map: dict[str, str] = {}
    seen_canonical: set[str] = set()
    for raw, canon in zip(header, normalized):
        if canon not in ALLOWED_COLUMNS:
            continue  # allow_extra=True で通過した追加列は行変換では無視する
        if canon in seen_canonical:
            raise PunchValidationError(
                f"CSV header has duplicate column after normalization: {canon!r}"
            )
        seen_canonical.add(canon)
        header_map[raw] = canon
    return header_map
```

> **ヘッダ正規化ルール（R3 レビュー指摘 Major 3 対応 / 確定仕様）**:
>
> - `_validate_header` は `strip().lower()` で正規化した列名を基準に検査する（ヘッダ側のみ）。
> - 行変換 `_row_to_punch` は **canonical キー** （`date` / `employee_id` / `clock_in` / `clock_out`）しか参照しない。
> - `parse_punch_csv` は `_validate_header` から返る `header_map` を使って `csv.DictReader` の行を `{canonical: value}` 形式の `canonical_row` に詰め直してから `_row_to_punch` に渡す。
> - これにより `"Clock_In"` や `" clock_in "` などのヘッダ揺らぎでも `KeyError` / 全行 skip が発生しない（実装者によるブレを排除）。
> - `allow_extra=True` で通過した追加列は `header_map` から除外し、`_row_to_punch` には渡さない（allowlist 4 列のみ到達する契約）。
> - 重複 canonical（例: `Clock_In` と `clock_in` の同時指定）は `PunchValidationError` で拒否する。

### 6.8 時刻パース

```python
_TIME_RE = re.compile(r"^([0-9]{1,2}):([0-9]{2})$")
_TIME_WITH_SEC_RE = re.compile(r"^([0-9]{1,2}):([0-9]{2}):([0-9]{2})$")

def parse_time(s: str) -> int:
    s_stripped = s.strip()
    m = _TIME_RE.match(s_stripped)
    if not m:
        # HH:MM:SS を専用メッセージで分岐（R1 レビュー指摘 Major 5 対応）
        if _TIME_WITH_SEC_RE.match(s_stripped):
            raise TimeFormatError(
                f"seconds are not supported (use 'HH:MM', got {s!r})"
            )
        raise TimeFormatError(f"invalid time: {s!r}")
    hh, mm = int(m.group(1)), int(m.group(2))
    if hh == 24 and mm == 0:
        raise TimeFormatError("24:00 not allowed as input")
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise TimeFormatError(f"invalid time: {s!r}")
    return hh * 60 + mm

def format_minutes(m: int) -> str:
    if m == 1440:
        return "24:00"
    if not (0 <= m <= 1439):
        raise ValueError(f"minute out of range: {m}")
    return f"{m // 60:02d}:{m % 60:02d}"
```

### 6.9 `--out` パス検証

```python
def validate_out_path(path_str: str) -> Path:
    resolved = Path(path_str).resolve()
    cwd = Path.cwd().resolve()
    try:
        resolved.relative_to(cwd)  # 3.9+ は例外で判定
    except ValueError:
        raise OutPathError("--out path must be under cwd")
    if not resolved.parent.exists():
        raise OutPathError("--out parent directory does not exist")
    return resolved
```

### 6.10 入力ソース排他検査（`main.py` 入口）

```python
def _check_input_sources(args) -> None:
    stdin_piped = not sys.stdin.isatty()
    if stdin_piped and (args.punch or args.punch_file):
        raise InputSourceConflict(
            "input sources are mutually exclusive "
            "(got --punch/--punch-file and piped STDIN)"
        )
    if not stdin_piped and not args.punch and not args.punch_file:
        raise InputSourceMissing(
            "no input: specify --punch, --punch-file or pipe STDIN"
        )
```

### 6.11 `--baseline` 解決規則（統一ルール）

`compare` の `--baseline` は **文字列のみ** を受け取り、以下の順序で解決する（R1 レビュー指摘1に対応）。

```python
def resolve_baseline(rules: list[Rule], baseline: str | int | None) -> int:
    if baseline is None:
        return 0
    # int 型で渡された場合（テストなど内部呼び出し）はそのまま index
    if isinstance(baseline, int):
        idx = baseline
    else:
        s = baseline.strip()
        # 1) 整数変換できる文字列は **常に** index として解釈（name 一致より優先）
        try:
            idx = int(s)
        except ValueError:
            # 2) 整数でない場合のみ name 完全一致を試みる
            for i, r in enumerate(rules):
                if r.name == s:
                    return i
            raise BaselineResolutionError(
                f'--baseline "{s}" does not match any loaded rule'
            )
    # 3) index は 0..len(rules)-1 の範囲チェック
    if not (0 <= idx < len(rules)):
        raise BaselineResolutionError(
            f"--baseline index {idx} out of range (0..{len(rules) - 1})"
        )
    return idx
```

**決定**: 数字だけの文字列（例: `"0"`, `"1"`）は index として解釈する。rule.name として `"1"` のような数字名を設定している場合、`--baseline` では参照できない（代わりに index 指定を使う）。これは擬似コード・§10.2.7 テスト期待値とも一致させる（下記参照）。

---

## 7. CLI 仕様（実装版）

### 7.1 argparse 構造

```
python src/main.py <subcommand> [options]

subcommands:
  simulate   (§7.2)
  compare    (§7.3)
  explain    (§7.4)
  validate   (§7.5)
```

### 7.1.1 共通オプション（すべてのサブコマンドに付与）

| オプション | 型 | デフォルト | 説明 |
|---|---|---|---|
| `--format` | choice(text/json/csv) | text | 出力形式 |
| `--out` | str (path) | None | 出力ファイル。cwd 配下限定 |
| `--quiet` | flag | False | 免責・`[INFO]` 抑制（`[WARN]`/`[ERROR]` は継続） |
| `--no-color` | flag | False | ANSI 色無効化（非TTY時は自動無効） |
| `--debug` | flag | False | 想定外例外時に詳細トレースを stderr 出力 |
| `--deterministic` | flag | False | `meta.run_id` / `meta.generated_at` / `[INFO] summary` 内の `run_id` を固定値化（§4.5 / R3 Major 1）。golden テスト・再現性比較用 |

### 7.2 `simulate`

| オプション | 型 | 必須 | 説明 |
|---|---|---|---|
| `--rule` | str (path) | 必須 | YAMLルール |
| `--punch` | str | `--punch` / `--punch-file` / STDIN いずれか | `"HH:MM,HH:MM"` |
| `--punch-file` | str (path) | 同上 | CSVパス |
| `--break` | int | 任意 | 休憩分（YAML値より優先） |
| `--hourly` | int | 任意 | 時給（指定時 pay_yen 算出） |

- `--punch` と `--punch-file` は argparse の `mutually_exclusive_group` で静的排他。
- STDIN との衝突は `main.py` でランタイム検査（§6.10）。

### 7.3 `compare`

| オプション | 型 | 必須 | 説明 |
|---|---|---|---|
| `--rule` | str (path), `action="append"` | 必須 (2件以上) | 複数回指定 |
| `--punch` / `--punch-file` | 同上 | いずれか | |
| `--hourly` | int | 必須 | |
| `--break` | int | 任意 | 未指定時 0 を全ルール共通適用 |
| `--amount-rounding` | choice(floor/half_up/ceil) | 任意 | 未指定時 floor を共通適用 |
| `--show-gross` | flag | 任意 | Gross列追加 |
| `--baseline` | str | 任意 | rule.name or 0始まりindex（整数変換可能な文字列は常に index として解釈 / §6.11）。未指定時 rules[0] |

- `--rule` が 1 件以下なら argparse 後処理で `ArgumentError` → exit 2。

### 7.4 `explain`

`simulate` と同じオプション + `--demo`（flag、3ステップ短縮）。ただし:
- `--punch` 必須（`--punch-file` / STDIN は不可）。
- `--format text` のみ許可。`json` / `csv` 指定で `[ERROR] explain supports --format text only` → exit 2。

### 7.5 `validate`

| オプション | 型 | 必須 |
|---|---|---|
| `--rule` | str (path) | 必須 |

スキーマ検証のみ。合格 exit 0、不合格 exit 2。

### 7.6 終了コード

| code | 意味 |
|---|---|
| 0 | 正常終了（少なくとも1件の有効データを処理、または `validate` でスキーマ適合） |
| 1 | 想定外の内部例外 |
| 2 | 入力不正による中断（YAMLエラー、必須列欠損、direction/amount_rounding不正、allowlist違反、禁止列検出、`--baseline`解決不能、全行スキップ、`--out` cwd外、24:00 clock_in、入力ソース排他違反、explain の json/csv 指定） |

> `validate` は打刻データを処理しないため「少なくとも1件の有効データ処理」条件は適用しない（R2 レビュー指摘 Minor 1 対応）。`validate` はスキーマ適合で exit 0、`ConfigValidationError` で exit 2。

### 7.7 標準出力/標準エラーの出し分け

| 条件 | stdout | stderr |
|---|---|---|
| `--format text`（デフォルト） | 免責 + 結果 | `[WARN]` / `[ERROR]` / `[INFO] summary` |
| `--format json` | JSON のみ | 免責 1行 + 各種ログ |
| `--format csv` | CSV のみ | 免責 1行 + 各種ログ |
| `--quiet` 付与 | 免責なし | `[WARN]` / `[ERROR]` のみ（`[INFO]` 抑制） |

---

## 8. エラー処理と例外階層

### 8.1 例外階層

```python
# exceptions.py
class DemoError(Exception):
    """本ツールで扱うすべてのドメイン例外の基底。main.py で捕捉し exit 2 に変換。"""

# 設定系
class ConfigValidationError(DemoError):
    """YAML パース失敗、必須キー欠損、direction/amount_rounding/unit_minutes 値域違反、
       break.type 非 fixed。"""

# 打刻入力系
class PunchValidationError(DemoError):
    """CSV 必須列欠損、ヘッダ系の致命エラー（許可列違反・禁止列検出）の最上位。"""

class ColumnNotAllowedError(PunchValidationError):
    """allowlist 違反（許可列以外が含まれる）。"""

class ForbiddenColumnError(PunchValidationError):
    """禁止列（PII）検出。"""

class PunchRowError(DemoError):
    """行単位のエラー。呼び出し側で捕捉して [WARN] ログ + skip する。"""

class TimeFormatError(PunchRowError):
    """時刻フォーマット違反（25:77、abc、HH:MM:SS、24:00 入力）。"""

# 丸め系
class RoundingBoundaryError(DemoError):
    """clock_in rounded to 24:00。致命扱い。"""

# 金額系
class PayrollError(DemoError):
    """calc_pay の不正引数（minutes/hourly 負値・未知 amount_rounding）を一本化。
       exit 2 へマップ。ValueError を投げないことで DemoError 契約を守る。"""

# compare 系
class BaselineResolutionError(DemoError):
    """--baseline 文字列の name 不一致、または index 範囲外。"""

# 出力系
class OutPathError(DemoError):
    """--out が cwd 外 or 親ディレクトリ不存在。"""

# 入力ソース系
class InputSourceConflict(DemoError):
    """--punch/--punch-file と STDIN の同時指定。"""

class InputSourceMissing(DemoError):
    """入力ソース未指定。"""
```

### 8.2 例外 → 終了コード マッピング

| 例外 | exit code | stderr メッセージ |
|---|---|---|
| `ConfigValidationError` | 2 | `[ERROR] <msg>` |
| `PunchValidationError`（ヘッダ系） | 2 | `[ERROR] <msg>` |
| `PunchValidationError`（UTF-8以外） | 2 | `[ERROR] input file is not UTF-8: <path> (hint: re-save as UTF-8, BOM optional)` |
| `ConfigValidationError`（UTF-8以外） | 2 | `[ERROR] rule YAML is not UTF-8: <path> (hint: re-save as UTF-8)` |
| `ColumnNotAllowedError` | 2 | `[ERROR] unexpected column (not in allowlist): <name>` |
| `ForbiddenColumnError` | 2 | `[ERROR] forbidden column (PII) detected: <name>` |
| `PunchRowError` / `TimeFormatError` | 継続 (行 skip) | `[WARN] line N: <msg>` |
| 全行 skip 時 | 2 | `[ERROR] no valid punches after parsing (all rows skipped)` |
| `RoundingBoundaryError` | 2 | `[ERROR] clock_in rounded to 24:00 is invalid` |
| `PayrollError` | 2 | `[ERROR] <msg>`（負値引数・未知 amount_rounding） |
| `BaselineResolutionError` | 2 | `[ERROR] --baseline "<val>" does not match any loaded rule` / `out of range` |
| `OutPathError` | 2 | `[ERROR] --out path must be under cwd` / `parent directory does not exist` |
| `InputSourceConflict` | 2 | `[ERROR] input sources are mutually exclusive ...` |
| `InputSourceMissing` | 2 | `[ERROR] no input: specify --punch, --punch-file or pipe STDIN` |
| その他 `DemoError` | 2 | `[ERROR] <msg>` |
| 未捕捉の `Exception` | 1 | `[ERROR] unexpected error: <type>: <msg>`。`--debug` 時のみトレース追記 |

### 8.3 エラーメッセージ規約
- `[ERROR]` / `[WARN]` / `[INFO]` のプリフィクスを必ず付与。
- 行単位エラーは `line N:` を含める（CSV 入力時のみ）。
- ファイルパスは原則として入力された相対表記で記載（デバッグ容易性）。
- 値域違反は `must be <allowed>, got <actual>` の形式。
- メッセージは英語固定（実装単純化、`logging` 前提）。text フォーマット本体のみ日本語。

---

## 9. ログ仕様

### 9.1 ログレベル
| レベル | 用途 |
|---|---|
| DEBUG | 未実装（MUST 最小） |
| INFO | 実行サマリ（`summary run_id=... subcommand=... processed_count=N skipped_count=M exit_code=C`、設計 §10.1.1 と同一キー）、compare 時の共通設定通知 |
| WARN | 行単位 skip 警告、`overtime` 読み捨て、休憩過大、compare 不一致、`amount_rounding` YAML 無視 |
| ERROR | 致命エラー（exit 2 / 1 直前に出力） |

### 9.2 フォーマット
```
[<LEVEL>] <message>
```
例:
```
[WARN] line 3: invalid time: '25:77'
[WARN] overtime is not applied in this build (SHOULD scope)
[INFO] summary run_id=1c0e... subcommand=simulate rule_name="15分丸め（会社有利）" input_source=csv:samples/punches.csv processed_count=4 skipped_count=0 exit_code=0
[ERROR] --out path must be under cwd
```

### 9.3 出力先
- **stderr のみ**。ファイル出力なし（要件 §5.1 永続ログ禁止）。
- `logging.basicConfig(stream=sys.stderr, format="%(message)s")` 相当。

### 9.4 `--quiet` / `--debug` の挙動
- `--quiet`: `INFO` 抑制、`WARN` / `ERROR` は出力継続（要件 §4.1 M2）。免責も抑制。
- `--debug`: 未捕捉例外時に `traceback.format_exc()` を stderr へ出力。通常は簡潔メッセージのみ。
- 両者同時指定可（`--quiet --debug` では `WARN` / `ERROR` + 致命時トレース）。

### 9.5 PII マスキング
本ツールは匿名ID (`EMP001` 等) のみ扱うため、ログ中にも匿名IDをそのまま出力する。氏名・連絡先は CSV allowlist で入口拒否されるためログに混入しない。マスキング処理は**実装しない**（不要）。

### 9.6 色付け
- ANSI エスケープ: TTY かつ `--no-color` 未指定時のみ。
- `[WARN]` 黄（`\033[33m`）、`[ERROR]` 赤（`\033[31m`）、`[INFO]` シアン（`\033[36m`）。
- 具体 RGB 値は実装時に決定（テンプレート通り）。

### 9.7 `run_id` / `generated_at` 生成

```python
import uuid, datetime

JST = datetime.timezone(datetime.timedelta(hours=9))

def make_run_metadata(deterministic: bool) -> tuple[str, str]:
    """run_id と generated_at を生成。--deterministic 時は固定値。R3 Major 1 対応。"""
    if deterministic:
        return ("000000000000", "1970-01-01T00:00:00+09:00")
    run_id = uuid.uuid4().hex[:12]  # 先頭12文字で十分、短めにして可読性優先
    generated_at = datetime.datetime.now(tz=JST).isoformat(timespec="seconds")
    return (run_id, generated_at)
```

- `deterministic=True` は `--deterministic` フラグで駆動される（§7.1.1）。
- 既定（`False`）は従来通り UUID4 + 現在時刻。要件 §5「再現性」を厳密に求める文脈（CI golden 比較・デモ録画）では必ず `--deterministic` を付与する運用。

---

## 10. テスト設計

### 10.1 単体テスト対象モジュール一覧

| モジュール | テストファイル | 重点 |
|---|---|---|
| `rounding` | `test_rounding.py` | 真理値表全網羅、24:00境界 |
| `payroll` | `test_payroll.py` | amount_rounding 3モード、半端値境界 |
| `punch_parser` | `test_punch_parser.py` | 時刻パース、CSV 読み込み、allowlist |
| `config_loader` | `test_config_loader.py` | YAML 検証、overtime 読み捨て |
| `warnings_detector` | `test_warnings_detector.py` | 条件 (a)(b)、沈黙ケース |
| `comparator` | `test_comparator.py` | 共通 break / amount_rounding、行単位丸め合算、baseline 解決 |
| `engine` | `test_engine.py` | simulate/compare/explain の連結 |
| `main` (CLI) | `test_main_cli.py` | argparse、exit code、input source 排他 |

### 10.2 重要テストケース（代表例）

#### 10.2.1 `round_minutes`（真理値表全網羅）

| 入力 m | unit | direction | 期待値 | 観点 |
|---|---|---|---|---|
| 543 (9:03) | 15 | floor | 540 (9:00) | 真理値表 floor/出勤 |
| 543 (9:03) | 15 | ceil | 555 (9:15) | 真理値表 ceil/出勤 |
| 543 (9:03) | 15 | round | 540 (9:00) | r*2=6 < 15、下に丸め |
| 540 (9:00) | 15 | ceil | 540 (9:00) | 割り切れ時は据え置き |
| 1087 (18:07) | 15 | floor | 1080 (18:00) | 真理値表 floor/退勤 |
| 1087 (18:07) | 15 | ceil | 1095 (18:15) | 真理値表 ceil/退勤 |
| 1087 (18:07) | 15 | round | 1080 (18:00) | r*2=14 < 15 |
| 1088 (18:08) | 15 | round | 1095 (18:15) | r*2=16 >= 15、上に丸め |
| 1432 (23:52) | 15 | ceil | 1440 (24:00) | 24:00 境界（退勤側は許容） |
| 0 (0:00) | 15 | floor | 0 | 最小値 |
| 1439 (23:59) | 60 | ceil | 1440 | 最大→24:00 |

#### 10.2.2 `calc_pay`（amount_rounding 3モード + 境界）

| minutes | hourly | mode | 期待値 | 観点 |
|---|---|---|---|---|
| 484 | 1800 | floor | 14520 | デモ基準（剰余 0） |
| 495 | 1800 | floor | 14850 | 同上 |
| 465 | 1800 | floor | 13950 | 同上 |
| 1 | 1800 | floor | 30 | 1800/60=30 きっかり |
| 1 | 1799 | floor | 29 | r=59、切捨て |
| 1 | 1799 | ceil | 30 | r=59、切上げ |
| 1 | 1799 | half_up | 30 | r*2=118 > 60、上 |
| 1 | 1829 | half_up | 30 | r=29, r*2=58 < 60、下 |
| 1 | 1830 | half_up | 31 | r=30, r*2=60 == 60、上（0.5 境界） |
| 0 | 1800 | floor | 0 | 最小 |

#### 10.2.3 `parse_time`（異常系）

| 入力 | 期待 |
|---|---|
| `"9:03"` | 543 |
| `"09:03"` | 543 |
| `"23:59"` | 1439 |
| `"25:77"` | `TimeFormatError` |
| `"abc"` | `TimeFormatError` |
| `"9:03:00"` | `TimeFormatError`（メッセージに `seconds are not supported` を含む） |
| `"24:00"` | `TimeFormatError`（入力 24:00 拒否） |
| `""` | `TimeFormatError` |

#### 10.2.4 CSV allowlist / 禁止列

| ヘッダ | 期待 |
|---|---|
| `date,employee_id,clock_in,clock_out` | 正常 |
| `date,employee_id,clock_in` | `PunchValidationError`（列欠損） |
| `date,employee_id,clock_in,clock_out,extra` | `ColumnNotAllowedError`（allowlist違反） |
| `date,employee_id,clock_in,clock_out,name` | `ForbiddenColumnError`（PII） |
| `date,employee_id,clock_in,clock_out,Name` | `ForbiddenColumnError`（大文字小文字無視） |
| `date,employee_id,clock_in,clock_out,extra` + `--allow-extra-columns` | 正常（開発ビルド時） |
| `Date,Employee_ID, clock_in ,Clock_Out` | 正常（R3 Major 3 ヘッダ正規化。全行 `_row_to_punch` が canonical キーで値を取得できる） |
| `date,employee_id,clock_in,Clock_In,clock_out` | `PunchValidationError`（canonical 重複） |

#### 10.2.5 警告検出（条件 a/b / 沈黙）

| clock_in | clock_out | unit | 期待警告数 |
|---|---|---|---|
| ceil | floor | 15 | 1（条件a） |
| ceil | floor | 1 | 1（unit条件なし） |
| floor | ceil | 15 | 1（条件b） |
| floor | ceil | 5 | 0（unit<15、沈黙） |
| floor | ceil | 30 | 1（条件b） |
| round | round | 15 | 0（沈黙） |
| ceil | ceil | 15 | 0（沈黙） |
| floor | floor | 30 | 0（沈黙） |

#### 10.2.6 compare の共通化・行単位丸め

- `--break` 未指定時、YAML に異なる `break.minutes` を持つ2ルールを渡すと `[WARN]` が1回出力され、全ルール break=0 適用。
- `--amount-rounding` 未指定時、YAML に `ceil` を持つルールと `floor` を持つルールを混ぜると `[WARN]` 1回、全ルール floor 適用。
- **行単位丸め合算 vs 合計1回丸めで差が出る最小ケース**（設計 C.10）:
  - 2打刻: 各 Net 30 分、時給 1799 円、`ceil`
  - 行単位: `calc_pay(30, 1799, ceil)` = 900 円（30×1799/60=899.5 → ceil → 900）×2 = **1800 円**
  - 合計1回: `calc_pay(60, 1799, ceil)` = 1799 円（60×1799/60=1799 きっかり）
  - テスト期待値 **1800 円**（行単位方式の固定化を担保）。

#### 10.2.7 `--baseline` 解決

§6.11 の解決規則（数字文字列は常に index 優先）に基づく期待値。

| rules | baseline | 期待 | 観点 |
|---|---|---|---|
| [A,B,C] | `None` | index=0 | 未指定デフォルト |
| [A,B,C] | `"B"` (rule.name) | index=1 | 非数字文字列は name 一致 |
| [A,B,C] | `"2"` | index=2 | 数字文字列は index 優先 |
| [A,B,C] | `2` (int 渡し) | index=2 | 内部呼び出しでの int |
| [A,B,C] | `"X"` | `BaselineResolutionError` | name 不一致 |
| [A,B,C] | `"5"` | `BaselineResolutionError` | index 範囲外 |
| [A(name="1"),B,C] | `"1"` | index=1（= B） | **数字文字列優先**。name="1" を狙う場合でも index 解釈され rules[1]=B になる。name="1" 参照は不可（運用上の制約） |
| [A(name="1"),B,C] | `"A"` 等の非数字で name 一致 | index=0 | 数字でなければ name 解決 |

#### 10.2.8 24:00 境界

- `clock_out=23:52, unit=15, ceil` → RoundedPunch.clock_out_min_rounded = 1440、`format_minutes(1440) == "24:00"`。
- `clock_in=23:52, unit=15, ceil` → `RoundingBoundaryError` → exit 2。

#### 10.2.8.1 `gross<0` 反転（R2 レビュー指摘 Major 4 対応）

- `clock_in=9:07, clock_out=9:12, unit=15, clock_in=ceil, clock_out=floor` → in_rounded=1080/9:15？  
  実例: `clock_in=9:07, clock_out=9:12, unit=15, in=ceil, out=floor` → in_rounded=555(9:15), out_rounded=540(9:00), gross = -15。
  - 期待: `gross_min` を 0 にクランプ、`net_min=0`、`[WARN] gross became negative after rounding ...` を1件出力。
  - 休憩過大メッセージは**出ない**こと（`gross<0` ルート専用メッセージのみ）。
- compare でも同じ反転が発生すれば `[WARN] gross became negative ...` を stderr に出力し、`total_gross` には 0 加算。

#### 10.2.9 全行スキップ時の exit code

- 4行すべて時刻違反の CSV を渡すと `[ERROR] no valid punches after parsing` → exit 2。

#### 10.2.10 `--out` パス検証

| 入力 | 期待 |
|---|---|
| `./out/result.csv`（cwd 配下、親あり） | 正常 |
| `/tmp/result.csv`（cwd 外） | `OutPathError` → exit 2 |
| `./nonexistent_dir/result.csv` | `OutPathError`（親なし） → exit 2 |

#### 10.2.11 入力ソース排他

- STDIN パイプ + `--punch` → `InputSourceConflict` → exit 2。
- すべて未指定 + tty → `InputSourceMissing` → exit 2。

#### 10.2.12 文字コード異常系（R1 レビュー指摘4 / R2 レビュー指摘 Critical 1 対応）

要件観点E（異常系）と §2.3 の方針を担保するテスト。**フィクスチャは全て `bytes` リテラルで固定化し、非 ASCII バイト列を必ず含める**（R2 指摘: ASCII のみの CP932 は UTF-8 としても合法なので再現不可）。

| 入力（bytes フィクスチャ） | 期待 |
|---|---|
| CSV を CP932 で保存（`"氏名"`=`b"\x8e\x81\x96\xbc"` をヘッダに含む非 ASCII バイト列） | `PunchValidationError` → exit 2、メッセージに `not UTF-8` を含む |
| CSV を Shift_JIS で保存（`"山田太郎"`=`b"\x8e\x52\x93\x63\x91\xbe\x98\x59"` を行データに含む） | `UnicodeDecodeError` → `PunchValidationError` → exit 2 |
| ヘッダは ASCII だが行データに壊れた UTF-8 を混入（例: `b"date,employee_id,clock_in,clock_out\n2026-04-20,EMP001,\xff\xfe,18:07\n"`） | `PunchValidationError` → exit 2 |
| YAML を CP932 で保存（`name: "日本語"` を cp932 エンコード、非 ASCII バイト列を含む） | `ConfigValidationError` → exit 2、メッセージに `not UTF-8` を含む |
| STDIN にバイト列 CP932 を流し込む（非 ASCII 文字を含む固定 bytes） | `PunchValidationError` → exit 2 |

実装ポイント:

- `open(..., encoding="utf-8"[-sig])` / `bytes.decode("utf-8-sig")` が `UnicodeDecodeError` を投げた時点で `DemoError` 系に正規化する。
- テスト側は `tmp_path / "input.csv"` に `Path.write_bytes(fixture_bytes)` で**固定バイト列**を書き出す。`str.encode("cp932")` をテスト実行時に行う書き方でもよいが、バイト列を直接定義する方が再現性が高い。
- 行単位の `csv.Error` は本節の対象外（§6.7 で `PunchRowError` 相当にラップして skip 継続）。

### 10.3 ハッピーパス統合テスト
デモシナリオ（要件 §6）を再現:
- **ステップ3 の compare**: 3ルール比較で `(14520, 14850, 13950)` と差額 `(0, +330, -570)` を検証。
- **ステップ4 の explain --demo**: 3ステップ出力が生成されること、警告が含まれること。

### 10.4 サンプルデータとの対応
- `samples/punches.csv`（4〜10行、`EMP001`）を使った `simulate` / `compare` の golden 出力を `tests/fixtures/` に配置。
- テスト自動化は MAY だが、少なくとも `pytest tests/` で通るレベルは用意する想定。

---

## 付録A. 設定ファイル完全版

### A.1 `samples/rules/15min_company_friendly.yml`
```yaml
name: "15分丸め（減少方向 / 会社有利）"
description: "出勤ceil（切上げ）×退勤floor（切捨て）。労働時間が減少方向に偏る。"
unit_minutes: 15
clock_in:
  direction: ceil
clock_out:
  direction: floor
break:
  type: fixed
  minutes: 60
amount_rounding: floor
```

### A.2 `samples/rules/15min_employee_friendly.yml`
```yaml
name: "15分丸め（増加方向 / スタッフ有利）"
description: "出勤floor（切捨て）×退勤ceil（切上げ）。労働時間が増加方向に偏る。"
unit_minutes: 15
clock_in:
  direction: floor
clock_out:
  direction: ceil
break:
  type: fixed
  minutes: 60
amount_rounding: floor
```

### A.3 `samples/rules/1min.yml`
```yaml
name: "1分単位（フェア）"
description: "丸めなし相当。端数処理の基準比較用。"
unit_minutes: 1
clock_in:
  direction: round
clock_out:
  direction: round
break:
  type: fixed
  minutes: 60
amount_rounding: floor
```

### A.4 `samples/rules/30min_floor.yml`
```yaml
name: "30分丸め（両側切捨て）"
description: "出勤・退勤とも30分単位で切捨て。参考設定。"
unit_minutes: 30
clock_in:
  direction: floor
clock_out:
  direction: floor
break:
  type: fixed
  minutes: 60
amount_rounding: floor
```

### A.5 `samples/rules/advanced/15min_with_overtime.yml`（SHOULD / WARN で読み捨て）
```yaml
name: "15分丸め + 法定内外別ルール"
description: "法定内は切捨て、法定外（8h超）は切上げ"
unit_minutes: 15
clock_in:
  direction: ceil
clock_out:
  direction: floor
break:
  type: fixed
  minutes: 60
overtime:
  legal_hours_per_day: 8
  inside_legal:
    unit_minutes: 15
    direction: floor
  outside_legal:
    unit_minutes: 15
    direction: ceil
```

---

## 付録B. サンプル打刻CSV（一部）

### B.1 `samples/punches.csv`
```csv
date,employee_id,clock_in,clock_out
2026-04-20,EMP001,9:03,18:07
2026-04-21,EMP001,8:58,18:02
2026-04-22,EMP001,9:12,19:45
2026-04-23,EMP001,8:45,22:18
```

（バイト列: UTF-8、改行 LF、BOM なし）

---

## 付録C. 実装上の決定記録（本書で決めたこと）

### C.1 型ヒントに `Literal` を使う
- **選択**: `Direction = Literal["ceil","floor","round"]` 等の型エイリアスで型ヒントを厳密化。
- **理由**: 実装者が IDE 上で補完 + 型検査を受けられる。Python 3.10+ で `Literal` は軽量、ランタイムコストなし。

### C.2 `logging` 標準ライブラリを採用、独自 logger クラスは作らない
- **選択**: `logging.getLogger(__name__)` で各モジュールから利用。
- **理由**: 標準ライブラリ優先の原則。色付けは `Formatter` のサブクラス1つで十分。

### C.3 `dataclass(frozen=True)` をドメインモデルに使う
- **選択**: `Punch` / `Rule` / `RoundedPunch` は frozen、`SimulationRow` / `ExplainTrace` は可変（後から pay を埋める可能性を残す）。
- **理由**: 再現性（非機能要件 §5）を型レベルで担保。純関数の入出力として安全。

### C.4 PyYAML の依存を受け入れる（再確認）
- **選択**: `PyYAML >= 6.0` を必須依存に。標準ライブラリ代替は作らない。
- **理由**: 要件 §5 と設計 §2.1 の方針。自前YAMLパーサは最小実装の原則に反する。

### C.5 例外階層は `DemoError` 単一ルートで統一
- **選択**: すべてのドメイン例外を `DemoError` から派生させる。
- **理由**: `main.py` の except 節が 1 行で済む（`except DemoError as e: ... sys.exit(2)`）。想定外例外（`Exception` 派生）と明確に分離。

### C.6 整数演算（`divmod`）で `calc_pay` を実装（float/Decimal 不使用）
- **選択**: 設計書 §7.6 / C.2 をそのまま踏襲。
- **理由**: `half_up` の境界値（`x.5`）で float 誤差を出さない。派遣の時給レンジに依存せず堅牢。

### C.7 `run_id` は UUID4 先頭12文字
- **選択**: `uuid.uuid4().hex[:12]`。
- **理由**: 完全一意性は不要（集計基盤なし）、短くて stderr ログで視認性が高い。

### C.8 CLI 実装は argparse（click 不採用）
- **選択**: 標準ライブラリの `argparse` のみ。
- **理由**: 外部依存を PyYAML 以外に増やさない。argparse のサブコマンド + `mutually_exclusive_group` で本要件は十分満たせる。

### C.9 テストフレームワークは pytest（自動化は MAY）
- **選択**: `tests/` 配下に `test_*.py` を配置、`pytest tests/` で実行可能な構造にする。
- **理由**: 標準 `unittest` より記述量が少なく、最小実装でも網羅テストが書きやすい。ただし CI 整備は Phase5 範囲外。

### C.10 モジュール名は技術責務で分割（派遣SaaS文脈をコードに持ち込まない）
- **選択**: 設計 C.6 を踏襲。`rounding` / `payroll` / `explainer` 等の汎用名。
- **理由**: 将来の W2/W5 拡張時の再利用性。派遣文脈は docs・samples・出力文言で表現。

---

## 付録D. 要件・設計との対応表（トレーサビリティ）

| 要件ID | 設計書セクション | 本仕様書セクション |
|---|---|---|
| 真理値表（要§2.4） | §7.1 | §6.1 / §10.2.1 |
| M1 ルール設定 | §3 / §5.2 | §4.3 / §5.2 / §6.6 / §A |
| M2 打刻入力 | §3 / §4 / §8.2 | §4.1 / §5.3 / §6.7-6.8 / §B |
| M3 シミュレーション結果 | §4.1 / §7.2 | §5.9 / §6.4 / §4.4-4.6 |
| M4 逆算チェック / 警告 | §7.3 / §7.4 | §5.7 / §5.6 / §6 |
| M5 ルール比較 / 金額計算 | §7.5 / §7.6 | §5.8 / §5.5 / §6.3 / §6.5 / §10.2.6 |
| 免責表示（要§5） | §6.2 / §9.4 | §5.10 / §7.7 |
| 実データ禁止 / 匿名ID / `--out` | §9 | §5.3 / §6.7 / §6.9 / §8.1 |
| 異常系（要§7.2） | §8 | §8 / §10.2.3-10.2.4 |
| 24:00 境界（設計 C.7） | §7.1 | §6.2 / §10.2.8 |
| compare 公平性（設計 C.8/C.10） | §7.5 | §6.5 / §10.2.6 |
| PII allowlist（設計 C.9） | §5.3 | §4.1 / §6.7 / §10.2.4 |
| 起動時バージョンチェック（設計 C.12） | §2.1 | §2.4 |
| 補助モジュール 3 点（設計§3.1 対象外 / R3 Critical 1） | ― | §3 / §5.11（exceptions） / §5.12（logging_config） / §4.1（build_flags） |
