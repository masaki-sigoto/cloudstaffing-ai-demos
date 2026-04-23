# 技術仕様書: CSV加工の完全自動化（勤怠CSV自動整形デモ）

- バージョン: 1.0（初版）
- 対応要件定義書: `01_requirements.md`
- 対応設計書: `02_design.md`
- 対象プロジェクト: クラウドスタッフィング AIデモ No.01 「CSV加工の完全自動化」
- 最終更新日: 2026-04-23

---

## 1. 仕様書の位置付け

### 1.1 要件定義書・設計書との対応

| 文書 | 粒度 | 主な内容 |
|---|---|---|
| `01_requirements.md` | What（何を作るか） | MUST/SHOULD/MAY 機能要件、非機能要件、成功基準 |
| `02_design.md` | How（どう作るか） | モジュール分割、データフロー、アルゴリズム方針 |
| `03_spec.md`（本書） | Code-ready（コードに落とす直前） | 関数シグネチャ、型、データスキーマ、同義語辞書サンプル、テスト設計 |

### 1.2 カバー範囲

- **含む**: Python ファイル配置、全公開関数/クラスの型ヒント付きシグネチャ、データクラス定義、例外階層、CLI argparse 構造、アルゴリズム近似コード、同義語辞書の初期エントリ、PII マスキング実装、テストケース例。
- **含まない**: 個別関数の完全実装、ユニットテストの網羅実装、サンプルCSVの全バイト列（見本のみ）、パフォーマンス最適化コード。

### 1.3 実装着手の前提条件

- 要件定義書・設計書が Codex レビュー3往復済みで確定済み。
- 本仕様書を読めば **Phase5（実装フェーズ）で迷わず着手できる** 粒度で記述する。
- Python **3.11.9** が開発マシンに導入されていること（pyenv 等で patch 桁まで固定。R3 対応で minor → patch 固定に強化）。
- 標準ライブラリのみで実装する方針が確定していること。

---

## 2. 動作環境と依存

### 2.1 Python バージョン

- **固定バージョン**: Python **3.11.9**（patch 桁まで固定、`match` 文、`dict[str, int]` 表記、改善されたエラーメッセージを前提とする）。R3 指摘対応で再現性向上のため minor ではなく patch まで固定した。
- 開発マシン・CI（任意）・README 表示の 3 箇所で `3.11.9` を明示する。pyenv 利用時は `.python-version` に `3.11.9` を記載。
- 3.10 系 / 3.12 系および 3.11.x の他 patch は実行差異の検証スコープ外（動作する可能性は高いが保証はしない）。
- Phase5 実装前に `python --version` で `Python 3.11.9` を確認する手順を README に記載。

### 2.2 依存ライブラリ方針

**外部依存: なし**（PyPI パッケージは一切追加しない）。以下の標準ライブラリのみを使用する。

| モジュール | 用途 |
|---|---|
| `csv` | CSV 読み書き、Sniffer |
| `argparse` | CLI 引数解析 |
| `pathlib` | パス操作 |
| `datetime` | 日付型・ISO 形式 |
| `json` | テンプレート・マッピングファイル |
| `difflib` | 編集距離ベース類似度（`SequenceMatcher.ratio()`） |
| `unicodedata` | NFKC 正規化（全角→半角） |
| `re` | 日付・時刻パターンマッチ |
| `logging` | ログ出力 |
| `dataclasses` | 中間データクラス |
| `typing` | 型ヒント |
| `enum` | ポリシー・レベル列挙 |

**重要決定**: 設定ファイル形式は **JSON に統一**（PyYAML を使わない）。`--mapping-file` も JSON のみ。要件定義書 5章・設計書 6.1.2 の方針を最終確定する。

### 2.3 OS / ロケール / 文字コード前提

- **対応 OS**: macOS / Linux。Windows は保証外。
- **ロケール**: UTF-8 環境を想定（`LANG=ja_JP.UTF-8` 等）。
- **入力 CSV 文字コード**: UTF-8、UTF-8 with BOM、Shift_JIS (CP932) のみ自動判定対応。
- **出力**: UTF-8 (BOMなし) / LF で固定。

---

## 3. ディレクトリ構成（実装版）

```
01_csv-automation/
├── docs/
│   ├── 01_requirements.md
│   ├── 02_design.md
│   └── 03_spec.md                    # 本書
├── src/
│   ├── __init__.py
│   ├── main.py                       # CLIDispatcher（エントリポイント）
│   ├── schema/
│   │   ├── __init__.py
│   │   └── canonical.py              # 標準スキーマ定数・REQUIRED/OPTIONAL 定義
│   ├── flows/
│   │   ├── __init__.py
│   │   ├── convert.py                # ConvertFlow
│   │   ├── save_template.py          # SaveTemplateFlow
│   │   ├── cleanup.py                # CleanupFlow (MAY)
│   │   └── batch.py                  # BatchRunner
│   ├── io/
│   │   ├── __init__.py
│   │   ├── loader.py                 # TimesheetLoader
│   │   ├── encoding.py               # EncodingDetector
│   │   ├── dialect.py                # DialectDetector
│   │   └── writer.py                 # TimesheetWriter
│   ├── mapping/
│   │   ├── __init__.py
│   │   ├── inferencer.py             # HeaderInferencer
│   │   ├── synonyms.py               # SynonymDictionary（同義語辞書データ）
│   │   └── similarity.py             # ratio() 薄ラッパ
│   ├── normalize/
│   │   ├── __init__.py
│   │   ├── timesheet.py              # TimesheetNormalizer（統括）
│   │   ├── date_parser.py            # DateParser
│   │   ├── time_parser.py            # TimeParser
│   │   ├── number_parser.py          # NumberParser
│   │   └── text.py                   # TextNormalizer
│   ├── quality/
│   │   ├── __init__.py
│   │   ├── review.py                 # ReviewCollector / ReviewCell / ReviewLedger
│   │   ├── policy.py                 # ErrorPolicyApplier / PolicyOutcome
│   │   └── counters.py               # RowCountValidator / Counters
│   ├── report/
│   │   ├── __init__.py
│   │   └── generator.py              # BillingReportGenerator
│   ├── template/
│   │   ├── __init__.py
│   │   ├── store.py                  # TemplateStore
│   │   └── mapping_file.py           # MappingFileLoader（JSON限定）
│   ├── security/
│   │   ├── __init__.py
│   │   └── mask.py                   # PIIMasker
│   └── errors.py                     # 例外階層（DemoError 等）
├── samples/
│   ├── timesheet_202604_haken_a.csv
│   ├── timesheet_202604_haken_b.csv
│   ├── timesheet_202604_haken_c.csv
│   └── timesheet_202605_haken_a.csv
├── templates/
│   └── .gitkeep
├── mappings/
│   └── .gitkeep                      # --mapping-file 用 JSON 置き場（任意）
├── out/                              # .gitignore 対象
├── tests/
│   ├── __init__.py
│   ├── test_encoding.py
│   ├── test_header_inferencer.py
│   ├── test_date_parser.py
│   ├── test_time_parser.py
│   ├── test_number_parser.py
│   ├── test_policy.py
│   ├── test_row_count_validator.py
│   ├── test_pii_masker.py
│   ├── test_template_store.py
│   └── fixtures/
│       ├── haken_a.csv
│       ├── haken_b_bom_cp932.csv
│       └── haken_c_errors.csv
├── .claude/
│   └── commands/
│       ├── csv-convert.md
│       ├── csv-save-template.md
│       ├── csv-convert-with-template.md
│       └── csv-batch.md
├── .gitignore                        # out/ を除外
└── README.md
```

各ディレクトリの役割は設計書 付録A と同一。ファイル単位で設計書 §3.1 の 22 モジュールを `src/` にマップ済み。

---

## 4. データスキーマ（実装レベル）

### 4.1 標準スキーマ（canonical schema）

**実装場所**: `src/schema/canonical.py`

```python
from typing import Final

CANONICAL_COLUMNS: Final[list[str]] = [
    "employee_id",
    "name",
    "work_date",
    "start_time",
    "end_time",
    "break_minutes",
    "hourly_wage",
]

REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset({
    "employee_id", "name", "work_date",
    "start_time", "end_time", "hourly_wage",
})

OPTIONAL_WITH_DEFAULT: Final[dict[str, str]] = {
    "break_minutes": "0",
}

# PII マスキング対象列（標準出力時のみ）
PII_MASKED_COLUMNS: Final[frozenset[str]] = frozenset({"name", "hourly_wage"})

# テンプレートPII防御用: canonical 7列のうち「データ値そのもの」が保存されては困るフィールド名
# （テンプレートは列の対応付けのみを持つため、本来は値を含む経路自体が存在しない。
#  本定数は `TemplateStore.save` の構造ホワイトリスト検証と組み合わせ、防御的に使用する）
PII_VALUE_FIELDS_DENYLIST: Final[frozenset[str]] = frozenset({"name", "hourly_wage"})

# テンプレート JSON で許可されるトップレベルキー（ホワイトリスト）
ALLOWED_TEMPLATE_TOP_KEYS: Final[frozenset[str]] = frozenset({
    "schema_version", "name", "created_at", "source_hint",
    "encoding", "dialect", "header_mapping", "unmapped_source_headers",
})

# header_mapping の各要素で許可されるキー（ホワイトリスト）
ALLOWED_HEADER_MAPPING_KEYS: Final[frozenset[str]] = frozenset({
    "canonical", "source", "source_index", "confidence", "needs_review", "via",
})
```

### 4.2 カノニカル7列の型・制約（整形後 CSV）

| 列名 | 出力型（文字列としての表現） | 制約 | 空欄時の扱い |
|---|---|---|---|
| `employee_id` | `str` (例: `EMP001`) | 必須、非空 | 要確認行 |
| `name` | `str` (例: `山田 太郎`) | 必須、非空 | 要確認行 |
| `work_date` | `YYYY-MM-DD` | 必須、`datetime.date` で実在検証 | 要確認行 |
| `start_time` | `HH:MM` | 必須、`00:00`〜`23:59` または `24:00`（`24:00` は要確認） | 要確認行 |
| `end_time` | `HH:MM` | 必須、`end < start` は要確認 | 要確認行 |
| `break_minutes` | 整数文字列 (例: `60`) | 任意、`>=0` の整数。数値変換不可/負値は要確認（reason: 「数値に変換できない」/「休憩分が負値」） | `0` に補完（クリーン扱い） |
| `hourly_wage` | 整数文字列 (例: `1500`) | 必須、`>=0` の整数。数値変換不可/負値は要確認（reason: 「数値に変換できない」/「時給が負値」） | 要確認行 |

### 4.3 内部データモデル（dataclass）

**実装場所**: 各モジュール配下（`src/io/loader.py`, `src/quality/review.py` 等）。

```python
# src/io/loader.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Dialect:
    delimiter: str           # "," | "\t" | ";"
    lineterminator: str      # "\r\n" | "\n"

@dataclass(frozen=True)
class LoadedTimesheet:
    headers: list[str]
    rows: list[list[str]]    # 生行（データ行のみ、ヘッダー除外）
    encoding: str            # "utf-8" | "utf-8-sig" | "cp932"
    dialect: Dialect
    source_path: Path
```

```python
# src/mapping/inferencer.py
from dataclasses import dataclass, field

@dataclass
class HeaderMapping:
    # canonical 列名 → 入力列インデックス（未マッピング列は含まない）
    canonical_to_source_index: dict[str, int] = field(default_factory=dict)
    # canonical 列名 → スコア（0.0〜1.0）
    confidence: dict[str, float] = field(default_factory=dict)
    # canonical 列名 → 入力側ヘッダー文字列（テンプレート保存用）
    source_headers: dict[str, str] = field(default_factory=dict)
    # 要確認扱い（0.60〜0.80）の canonical 列名
    needs_review_columns: list[str] = field(default_factory=list)
    # 未マッピング（<0.60）の canonical 列名
    unmapped_columns: list[str] = field(default_factory=list)
    # 入力側で一度も canonical にマップされなかったヘッダー
    unmapped_source_headers: list[str] = field(default_factory=list)
```

```python
# src/normalize/timesheet.py
from dataclasses import dataclass

@dataclass
class NormalizedCell:
    normalized_value: str            # 正規化後の値
    raw_value: str                   # 原値（keep ポリシー時に採用）
    is_review: bool                  # セル単位の要確認フラグ
    review_reason: str | None = None # is_review=True 時の日本語理由（例: "月が不正（13月は存在しない）"）。False 時は None

@dataclass
class NormalizedRow:
    source_row_no: int       # 入力ファイル行番号（ヘッダー=1, データ1行目=2）
    cells: dict[str, NormalizedCell]  # canonical 列名 → NormalizedCell

@dataclass
class NormalizedResult:
    rows: list[NormalizedRow]
    # ReviewCell のリストはここで副産物として返さず、ReviewCollector が再構成する
```

```python
# src/quality/review.py
@dataclass(frozen=True)
class ReviewCell:
    source_row_no: int   # 入力ファイル行番号
    column: str          # canonical 列名
    raw_value: str       # 原値
    reason: str          # 日本語の推定理由（例: "月が不正（13月は存在しない）"）

@dataclass
class ReviewLedger:
    cells: list[ReviewCell]
    @property
    def review_source_row_nos(self) -> frozenset[int]:
        return frozenset(c.source_row_no for c in self.cells)
```

```python
# src/quality/counters.py
@dataclass(frozen=True)
class Counters:
    input_rows: int
    output_rows: int
    dropped_rows: int
    review_rows: int
```

```python
# src/quality/policy.py
from enum import Enum

class ErrorPolicy(str, Enum):
    DROP = "drop"
    KEEP = "keep"
    FAIL = "fail"

@dataclass
class OutputRow:
    source_row_no: int
    output_row_no: int        # 出力CSV上の行番号（ヘッダー=1, データ1行目=2）
    has_review: bool
    review_columns: list[str]  # 要確認セルの canonical 列名
    values: dict[str, str]     # canonical 列名 → 出力値

@dataclass
class PolicyOutcome:
    output_rows: list[OutputRow]
    ledger: ReviewLedger
    counters: Counters
    halted: bool = False       # fail ポリシー + review>0 で True
```

### 4.4 テンプレート JSON スキーマ（完全版）

**ファイル**: `templates/<name>.json`（例: `templates/haken_a.json`）

```json
{
  "schema_version": 1,
  "name": "haken_a",
  "created_at": "2026-04-23T10:30:00+09:00",
  "source_hint": "timesheet_202604_haken_a.csv",
  "encoding": "utf-8",
  "dialect": {
    "delimiter": ",",
    "lineterminator": "\r\n"
  },
  "header_mapping": [
    {
      "canonical": "employee_id",
      "source": "社員コード",
      "source_index": 5,
      "confidence": 1.00,
      "needs_review": false,
      "via": "dict"
    }
  ],
  "unmapped_source_headers": []
}
```

**フィールド仕様**:

| キー | 型 | 必須 | 説明 |
|---|---|---|---|
| `schema_version` | `int` | 必須 | 現在は `1` 固定 |
| `name` | `str` | 必須 | snake_case 半角英数字＋`_`（命名規則） |
| `created_at` | `str` (ISO 8601 with tz) | 必須 | `datetime.now(tz=JST).isoformat()` |
| `source_hint` | `str` | 必須 | 推論元 CSV ファイル名（basename） |
| `encoding` | `"utf-8"` / `"utf-8-sig"` / `"cp932"` | 必須 | 判定結果 |
| `dialect.delimiter` | `str` | 必須 | `,` / `\t` / `;` |
| `dialect.lineterminator` | `str` | 必須 | `\r\n` / `\n` |
| `header_mapping[]` | `list` | 必須 | `CANONICAL_COLUMNS` 順。未マッピング列はスキップ |
| `header_mapping[].canonical` | `str` | 必須 | canonical 列名 |
| `header_mapping[].source` | `str` | 必須 | 入力側ヘッダー文字列 |
| `header_mapping[].source_index` | `int` | 必須 | 入力列の 0 始まりインデックス |
| `header_mapping[].confidence` | `float` | 必須 | 0.00〜1.00（小数点以下2桁） |
| `header_mapping[].needs_review` | `bool` | 必須 | 0.60〜0.80 は `true` |
| `header_mapping[].via` | `"dict"` / `"edit"` / `"manual"` / `"mapping_file"` | 必須 | 確定経路 |
| `unmapped_source_headers[]` | `list[str]` | 必須 | canonical にマップされなかった入力側ヘッダー |

**PII 値の保存禁止**: `header_mapping` は「列の対応付け」のみを記録し、**実データ値（氏名・時給等）は絶対に含めない**。`TemplateStore.save` は保存前に値が混入していないかチェックする（§8.1）。

### 4.5 マッピングファイル（`--mapping-file`）スキーマ

**ファイル**: `mappings/<arbitrary>.json`（ユーザー提供）

```json
{
  "schema_version": 1,
  "header_mapping": [
    { "canonical": "employee_id", "source": "社員コード" },
    { "canonical": "name", "source": "氏名" },
    { "canonical": "work_date", "source": "勤務日" },
    { "canonical": "start_time", "source": "始業" },
    { "canonical": "end_time", "source": "終業" },
    { "canonical": "break_minutes", "source": "休憩（分）" },
    { "canonical": "hourly_wage", "source": "時給" }
  ]
}
```

`source` は入力 CSV のヘッダー文字列と**完全一致**で検索する（正規化はしない、ユーザー責任）。

### 4.6 `keep` ポリシー時の出力契約（`__needs_review` 本体列 + sidecar 併用）

要件書 M6/M8（`01_requirements.md:53`, `:66`）との整合のため、`--error-policy keep` では **整形済 CSV 本体の末尾に `__needs_review` 列を必ず追加** する（標準スキーマ 7 列の順序は維持し末尾に追記のみ）。

**本体 CSV**（`out/<basename>.csv`、keep ポリシー時のみ 8 列）:

| 列名 | 型 | 説明 |
|---|---|---|
| `employee_id` 〜 `hourly_wage` | `str` | §4.2 のカノニカル 7 列（順序固定） |
| `__needs_review` | `0` / `1` | 1=要確認行、0=クリーン（M8） |

**sidecar CSV**（`out/<basename>_needs_review.csv`、`keep` 時に併せて出力）:

| 列名 | 型 | 説明 |
|---|---|---|
| `output_row_no` | `int` | 整形済 CSV 上の行番号（ヘッダー=1, データ1行目=2） |
| `source_row_no` | `int` | 入力 CSV 上の行番号 |
| `has_review` | `0` / `1` | 1=要確認行 |
| `review_columns` | `str` | 要確認セルの canonical 列名をパイプ `|` 区切り（例: `work_date|end_time`） |

sidecar は「どの canonical 列が要確認か」を機械可読で提供する補助ファイルで、本体の `__needs_review` 列（行レベルフラグ）を補完する役割を持つ。本体 CSV のみで要件 M8 は満たし、sidecar はレビュー支援用の追加情報である。

**本体 CSV 例**（入力 4 行中 1 行が要確認、keep ポリシー、末尾に `__needs_review`）:

```csv
employee_id,name,work_date,start_time,end_time,break_minutes,hourly_wage,__needs_review
EMP001,山田 太郎,2026-04-23,09:00,18:00,60,1500,0
EMP002,佐藤 花子,令和8年13月5日,10:00,19:00,60,1600,1
EMP003,鈴木 三郎,2026-04-24,09:00,18:00,60,1500,0
EMP004,田中 四郎,2026-04-25,09:00,18:00,60,1500,0
```

**sidecar 例**:

```csv
output_row_no,source_row_no,has_review,review_columns
2,2,0,
3,3,1,work_date|end_time
4,4,0,
5,5,0,
```

### 4.7 レポート Markdown テンプレート

**ファイル**: `out/<basename>_report.md`

```markdown
# 変換レポート: {input_basename}

- 実行日時: {iso_datetime}
- 入力ファイル: {input_path}
- 出力ファイル: {output_path}
- 文字コード: {encoding}
- ポリシー: {policy}

## 件数サマリ
- input_rows: {input_rows}
- output_rows: {output_rows}
- dropped_rows: {dropped_rows}
- review_rows: {review_rows}
- 関係式チェック: {relation_check_line}

## ヘッダーマッピング結果
| canonical | source | confidence | needs_review |
|---|---|---|---|
| employee_id | 社員コード | 1.00 | false |
| ...

## 要確認セル一覧
（行番号はファイル行番号。ヘッダー行=1 とし、データ1行目=2 から始まる）

| 行 | 列 | 元の値 | 推定理由 |
|---|---|---|---|
| 3 | work_date | 令和8年13月5日 | 月が不正（13月は存在しない） |
| ...

## 未マッピング入力ヘッダー
- {unmapped_source_header_1}
- ...
```

**レポート CSV 形式**（`--report-format csv` 指定時）: 上記「要確認セル一覧」のみを以下の列で出力する。

```csv
source_row_no,column,raw_value,reason
3,work_date,令和8年13月5日,月が不正（13月は存在しない）
```

件数サマリは標準出力に必須表示する（M7）。

---

## 5. 関数/クラス仕様

各モジュールの公開 API を型ヒント付きで示す。**詳細な実装は Phase5 に委ねる**が、シグネチャは本書で確定する。

### 5.1 `src/errors.py`（例外階層）

```python
class DemoError(Exception):
    """全例外の基底。ユーザー向けメッセージを持つ。"""
    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

class InputValidationError(DemoError):
    """入力パス・CLI引数の検証エラー（samples/外、symlink、排他違反等）。"""

class EncodingDetectionError(DemoError):
    """UTF-8/CP932 いずれでもデコードできなかった。"""

class DialectDetectionError(DemoError):
    """区切り文字・改行判定に失敗した。"""

class HeaderMappingError(DemoError):
    """REQUIRED 列が確定しない（全列未マッピング、空CSV含む）。"""

class TemplateSchemaError(DemoError):
    """テンプレートJSONのスキーマ不整合、命名規則違反、PII値混入。"""

class MappingFileError(DemoError):
    """--mapping-file の読み込み/スキーマエラー。"""

class RowCountMismatchError(DemoError):
    """M7 件数照合の関係式不成立。"""

class TemplateExistsError(DemoError):
    """--force なしで既存テンプレートを上書きしようとした。"""
```

### 5.2 `src/schema/canonical.py`

定数のみ。§4.1 参照。

### 5.3 `src/io/encoding.py` — EncodingDetector

```python
from pathlib import Path

def detect_encoding(path: Path) -> str:
    """BOM(utf-8-sig) strict→UTF-8 strict→CP932 strict の固定順で文字コードを判定する。

    BOM 検出後も `utf-8-sig` で strict decode し、失敗時は CP932 にフォールバックする
    （R3 対応: 先頭バイトが偶然 BOM 並びの CP932 ファイルを誤認しないため）。
    戻り値: "utf-8-sig" | "utf-8" | "cp932"
    例外: EncodingDetectionError（いずれでもデコード不可）
    副作用: ファイル全バイトを読む
    """
```

### 5.4 `src/io/dialect.py` — DialectDetector

```python
def detect_dialect(sample_text: str) -> Dialect:
    """csv.Sniffer を試行、失敗時は ',' → '\\t' → ';' の固定順にフォールバック。

    改行は '\\r\\n' → '\\n' の優先順で検出。
    sample_text の取得量: 呼び出し側で「先頭 8KiB またはファイル全体のうち小さい方」を
    デコード済み文字列として渡す（100,000行上限でも十分）。実装ブレを避けるため固定。
    例外: DialectDetectionError（全候補で失敗時）
    """
```

### 5.5 `src/io/loader.py` — TimesheetLoader

```python
from typing import Iterator

class TimesheetLoader:
    def load(self, path: Path) -> LoadedTimesheet:
        """CSVファイルを読み込み、ヘッダー・行・文字コード・dialectを返す。

        例外契約（`DemoError` 系で閉じる）:
        - `EncodingDetectionError` — 文字コード判定失敗
        - `DialectDetectionError` — 区切り文字・改行判定失敗
        - `InputValidationError` — ファイル未存在・I/O 不能（内部で `OSError`
          / `FileNotFoundError` を捕捉してラップする。`main()` の `DemoError`
          一元キャッチに到達させるため、素の `OSError` を外へ投げない）
        副作用: ファイル読み込み
        """
```

### 5.6 `src/normalize/text.py` — TextNormalizer

```python
import unicodedata

def normalize_text(s: str) -> str:
    """NFKC 正規化 + 前後空白除去 + 連続空白の単一化。

    - 全角数字→半角、全角英字→半角、全角コロン→半角コロン
    - 記号 '¥'/'￥' は '¥' に統一（wage パーサ用）
    - 内部空白（名前中の全角スペース等）は半角スペース1個に圧縮
    """
```

### 5.7 `src/mapping/synonyms.py`（同義語辞書）

```python
from typing import Final

# 各 canonical 列に対する既知の表記揺れを格納
# 辞書キー比較は normalize_text() 適用後の小文字で行う
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
```

### 5.8 `src/mapping/similarity.py`

```python
from difflib import SequenceMatcher

def similarity_ratio(a: str, b: str) -> float:
    """difflib.SequenceMatcher.ratio() による 0.0〜1.0 の類似度。

    両引数は normalize_text 適用済みを想定。
    """
    return SequenceMatcher(None, a, b).ratio()
```

### 5.9 `src/mapping/inferencer.py` — HeaderInferencer

```python
from typing import Optional

class HeaderInferencer:
    # 閾値は定数として公開
    CONFIRM_THRESHOLD: float = 0.80
    REVIEW_THRESHOLD: float = 0.60

    def __init__(self, synonyms: dict[str, list[str]] = SYNONYMS) -> None: ...

    def infer(
        self,
        headers: list[str],
        template: Optional[HeaderMapping] = None,
    ) -> HeaderMapping:
        """ヘッダー群を canonical にマッピング。template 指定時は推論スキップ。

        アルゴリズム: §6.2
        例外: HeaderMappingError（REQUIRED 列のいずれかが確定できない場合）
        """
```

### 5.10 `src/normalize/date_parser.py` — DateParser

```python
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass(frozen=True)
class DateParseResult:
    value: Optional[str]   # "YYYY-MM-DD" or None
    is_valid: bool
    reason: str            # is_valid=False の場合の日本語理由。成功時は ""

def parse_date(raw: str) -> DateParseResult:
    """多様な日付表記を "YYYY-MM-DD" に変換。失敗時は is_valid=False と reason。

    対応パターン: §6.3
    """
```

### 5.11 `src/normalize/time_parser.py` — TimeParser

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class TimeParseResult:
    value: Optional[str]   # "HH:MM" or None
    is_valid: bool
    is_24_hour: bool       # True の場合は要確認扱い（24:00）
    reason: str            # 成功時は ""

def parse_time(raw: str) -> TimeParseResult: ...
```

### 5.12 `src/normalize/number_parser.py` — NumberParser

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class NumberParseResult:
    value: Optional[int]
    is_valid: bool
    reason: str            # 成功時は ""

def parse_wage(raw: str) -> NumberParseResult:
    """'￥1,500' / '1500円' / '1,500' → 1500 に変換。"""

def parse_minutes(raw: str) -> NumberParseResult:
    """'60分' / '1時間' / '60' → 60 に変換（1時間=60分）。"""
```

### 5.13 `src/normalize/timesheet.py` — TimesheetNormalizer

```python
class TimesheetNormalizer:
    def normalize(
        self,
        loaded: LoadedTimesheet,
        mapping: HeaderMapping,
    ) -> NormalizedResult:
        """全行を正規化し、各セルに is_review フラグを立てる。

        - REQUIRED 列が空 → is_review=True, review_reason="必須項目が空欄"
        - break_minutes が空 → "0" で補完、is_review=False, review_reason=None
        - 時刻整合 (end<start) → end_time セルに is_review=True, review_reason="終業が始業より前"
        - 24:00 → 正規化成功だが is_review=True, review_reason="24:00（要確認）"
        - パーサ失敗時は *ParseResult.reason を review_reason にそのまま格納
        戻り値: NormalizedResult（各セルが review_reason を必ず保持）
        """
```

### 5.14 `src/quality/review.py` — ReviewCollector

```python
class ReviewCollector:
    def collect(self, result: NormalizedResult) -> ReviewLedger:
        """NormalizedResult の is_review セルを ReviewCell に変換して集約。

        - 各 NormalizedCell について is_review=True のものだけを ReviewCell に写像。
        - `ReviewCell.reason` は `NormalizedCell.review_reason`（必須、空文字不可）から取得。
          None の場合は "（理由未設定）" をデフォルト文言として用いる（実装バグ検知用フォールバック）。
        """
```

### 5.15 `src/quality/policy.py` — ErrorPolicyApplier

```python
class ErrorPolicyApplier:
    def apply(
        self,
        result: NormalizedResult,
        ledger: ReviewLedger,
        policy: ErrorPolicy,
    ) -> PolicyOutcome:
        """drop/keep/fail に応じて出力行と Counters を確定。

        - drop: 要確認行を除外、normalized_value を採用
        - keep: 全行出力、要確認セルのみ raw_value を採用
        - fail: review_rows > 0 なら halted=True
        アルゴリズム: §6.6
        """
```

### 5.16 `src/quality/counters.py` — RowCountValidator

```python
class RowCountValidator:
    def validate(self, counters: Counters, policy: ErrorPolicy) -> None:
        """M7 関係式を検証。不成立なら RowCountMismatchError。

        順序: ErrorPolicyApplier.apply → RowCountValidator.validate → (成功時のみ) Writer/Report
        """
```

### 5.17 `src/io/writer.py` — TimesheetWriter

```python
class TimesheetWriter:
    def write(
        self,
        output_rows: list[OutputRow],
        out_path: Path,
        policy: ErrorPolicy,
    ) -> None:
        """canonical 7列（keep ポリシーの場合は +`__needs_review` の 8列）を
        UTF-8(BOMなし)/LF で書き出し。

        - encoding='utf-8', newline=''（csv モジュール要件）, lineterminator='\\n'
        - ヘッダー行を CANONICAL_COLUMNS 順で出力
        - `policy == ErrorPolicy.KEEP` のときのみ、末尾列として `__needs_review`
          （値: `1`=要確認行 / `0`=クリーン）を追加する（§4.6、要件 M6/M8）
        """

    def write_sidecar(
        self,
        output_rows: list[OutputRow],
        sidecar_path: Path,
    ) -> None:
        """keep ポリシー時の sidecar CSV を書き出し（列仕様は §4.6）。

        本体 CSV の `__needs_review` 列（行レベルフラグ）を補完し、
        どの canonical 列が要確認かを機械可読形式で提供する。
        """
```

### 5.18 `src/report/generator.py` — BillingReportGenerator

```python
from typing import Literal

class BillingReportGenerator:
    def generate(
        self,
        input_path: Path,
        output_path: Path,
        loaded: LoadedTimesheet,
        mapping: HeaderMapping,
        outcome: PolicyOutcome,
        policy: ErrorPolicy,
        report_path: Path,
        format: Literal["md", "csv"] = "md",
    ) -> None:
        """Markdown / CSV レポートを書き出し。テンプレートは §4.7。"""
```

### 5.19 `src/template/store.py` — TemplateStore

```python
import re

class TemplateStore:
    NAME_PATTERN: re.Pattern = re.compile(r"^[a-z0-9_]+$")
    TEMPLATES_DIR: Path = Path("templates")

    def save(
        self,
        name: str,
        mapping: HeaderMapping,
        encoding: str,
        dialect: Dialect,
        source_hint: str,
        force: bool = False,
    ) -> Path:
        """templates/<name>.json に保存。

        例外:
        - TemplateSchemaError（命名規則違反、PII値混入）
        - TemplateExistsError（--force なしで既存ファイル）
        """

    def load(self, name: str) -> HeaderMapping:
        """templates/<name>.json を読み込む。

        例外契約（`DemoError` 系で閉じる）:
        - `TemplateSchemaError` — スキーマ不一致、JSON パース不能
        - `InputValidationError` — `templates/<name>.json` が存在しない
          （`FileNotFoundError` を捕捉してラップ。素の `FileNotFoundError` は
          外に投げない）
        """
```

### 5.20 `src/template/mapping_file.py` — MappingFileLoader

```python
class MappingFileLoader:
    def load(self, path: Path, headers: list[str]) -> HeaderMapping:
        """--mapping-file JSON を読み込んで HeaderMapping を構築。

        - source 文字列を入力 headers と完全一致検索
        - 不一致時は MappingFileError
        - YAML は非対応（拡張子 .yml/.yaml は即エラー）
        """
```

### 5.21 `src/security/mask.py` — PIIMasker

```python
def mask_name(name: str) -> str:
    """先頭1文字を残し、以降を '***' に置換。空文字は空のまま。"""
    if not name:
        return ""
    return name[0] + "***"

def mask_wage(wage: str) -> str:
    """全桁を '****' に固定置換（桁数も漏らさない）。"""
    if not wage:
        return ""
    return "****"

def mask_row(row: dict[str, str]) -> dict[str, str]:
    """name, hourly_wage のみマスク、他はそのまま。"""
    masked = dict(row)
    if "name" in masked:
        masked["name"] = mask_name(masked["name"])
    if "hourly_wage" in masked:
        masked["hourly_wage"] = mask_wage(masked["hourly_wage"])
    return masked
```

### 5.22 `src/flows/convert.py` — ConvertFlow

```python
from argparse import Namespace

class ConvertFlow:
    def run(self, args: Namespace) -> int:
        """convert サブコマンドのユースケース。

        戻り値: 終了コード（0=成功, 1=致命, 2=バッチ一部失敗）
        ステップ: §6.8
        """

    def _validate_convert_args(self, args: Namespace) -> None:
        """CLI 引数の論理検証と既定値補完（§6.13）。"""

    def _resolve_paths(self, args: Namespace) -> tuple[Path, Path, Path]:
        """output_path / report_path / sidecar_path を §6.12 の規約で決定する。"""
```

### 5.23 `src/flows/save_template.py` — SaveTemplateFlow

```python
class SaveTemplateFlow:
    def run(self, args: Namespace) -> int:
        """save-template サブコマンド。

        - 既定: 非対話、自動採用
        - --interactive: 対話式
        - --mapping-file: 外部JSON採用
        戻り値: 終了コード
        """
```

### 5.23b `src/flows/cleanup.py` — CleanupFlow（MAY）

```python
class CleanupFlow:
    def run(self, args: Namespace) -> int:
        """cleanup サブコマンド（要件 S6、MAY）。

        - `out/` 配下の整形済CSV・レポートと `samples/tmp_*` を削除
        - `--dry-run` 指定時は削除対象一覧を stdout に出すのみでファイルは触らない
        - 削除先は `out/` 配下と `samples/tmp_*` に限定（他パスは走査しない）
        戻り値: 0=成功（dry-run 含む）, 1=I/O 例外発生
        例外契約: 内部の `OSError` は `InputValidationError` にラップ
        """
```

### 5.24 `src/flows/batch.py` — BatchRunner

```python
class BatchRunner:
    def run(
        self,
        input_dir: Path,
        output_dir: Path,
        args: Namespace,
    ) -> int:
        """--input-dir 配下を 2 パスで走査する。

        - **Pass 1（全ファイル列挙 + warning）**:
          `all_files = sorted(p for p in input_dir.iterdir() if p.is_file())`
          このうち `p.suffix.lower() != ".csv"` のものは
          `[WARNING] loader: skipping non-csv file: <path>` を stderr に出して除外
          （Fatalにはしない）。`.csv` / `.CSV` / `.Csv` はすべて受理。
        - **Pass 2（処理対象確定）**:
          Pass 1 で warning 対象にならなかった CSV のみを
          コードポイント昇順でそのまま処理対象リストとする。
        - 各ファイル単位で samples/ 配下検証＋symlink 検証を再適用。
        - **出力先ガード（R3 対応）**: Pass 2 開始前に `output_dir` に対して
          `_guard_output_dir_for_batch(output_dir, allow_external=args.allow_external_output)`
          を 1 回だけ実行する（各ファイル毎ではなく冒頭で共通検証）。
          このガードは次を保証する:
            1. `output_dir` の親経路に symlink が無い（単発と同じ lstat ベース検査）
            2. `output_dir.resolve()` が `out/` 配下か、または `--allow-external-output` 指定あり
            3. `output_dir` 自体が存在しない場合は `mkdir(parents=True)` で作成可能な
               「親まで存在かつ親が symlink でない」状態であること
          これにより、`--input-dir` + `--output-dir` の組み合わせで出力先が外部に逃げる
          経路（例: `--output-dir /tmp/evil_symlink`）を単発と同等の強度で遮断する。
        戻り値: 0=全成功, 2=一部失敗, 1=fail-fast 中断
        """
```

### 5.25 `src/main.py` — CLIDispatcher

```python
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: list[str] | None = None) -> int: ...

if __name__ == "__main__":
    import sys
    sys.exit(main())
```

argparse 構造は §7 参照。

---

## 6. アルゴリズム詳細

### 6.1 文字コード判定（`src/io/encoding.py`）

```python
def detect_encoding(path: Path) -> str:
    data = path.read_bytes()   # ★全バイト取得

    # Step 1: BOM 検査（BOM 検出後も strict decode 成否で確定させる）
    #   - R3 指摘対応: BOM 先頭でも本体バイトが UTF-8 として不正な場合（例: BOM + CP932 本体）は
    #     utf-8-sig として decode 失敗する。その場合は CP932 にフォールバックさせる。
    #   - BOM つき CP932 は仕様としては非対応（macOS/Linux CSV 実務では稀）だが、
    #     誤判定の握り潰しは避け、decode 検証で確実に振り分ける。
    if data.startswith(b"\xEF\xBB\xBF"):
        try:
            data.decode("utf-8-sig", errors="strict")
            return "utf-8-sig"
        except UnicodeDecodeError:
            # 先頭 3 バイトが偶然 BOM 並びだが本体が UTF-8 ではない。CP932 判定にフォールバック
            pass

    # Step 2: UTF-8 strict
    try:
        data.decode("utf-8", errors="strict")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Step 3: CP932 strict
    try:
        data.decode("cp932", errors="strict")
        return "cp932"
    except UnicodeDecodeError:
        pass

    # Step 4: 失敗
    raise EncodingDetectionError(
        message="UTF-8/CP932 いずれでもデコードできませんでした",
        hint="ファイルの文字コードを UTF-8 にしてから再実行してください",
    )
```

**性能最適化は Phase5 後の課題**（100,000行上限に対する全バイト読みは現状 OK）。

**fixture 方針**: `tests/fixtures/haken_b_bom_cp932.csv` は「本体が UTF-8 で BOM あり」（すなわち `utf-8-sig` として正しく decode できるもの）を真の CP932+BOM ケースと誤認しないよう、名称に反して UTF-8(BOM) データを格納する。真の「BOM 擬似 + CP932 本体」ケースは §6.1 Step 1 のフォールバック経路で CP932 として処理される想定で、専用の異常系 fixture（`haken_b_fakebom_cp932.csv`）を任意で用意する（R3 対応の補助 fixture、実装必須ではない）。

### 6.2 ヘッダー推論（`src/mapping/inferencer.py`）

```python
def infer(self, headers: list[str], template: Optional[HeaderMapping] = None) -> HeaderMapping:
    if template is not None:
        return self._apply_template(headers, template)

    normalized_headers = [normalize_text(h).lower() for h in headers]
    # 候補を (canonical, source_index, score, via) タプルで列挙
    all_candidates: list[tuple[str, int, float, str]] = []

    for canonical in CANONICAL_COLUMNS:
        synonyms_norm = [normalize_text(s).lower() for s in self.synonyms[canonical]]
        for i, norm_h in enumerate(normalized_headers):
            if norm_h in synonyms_norm:
                all_candidates.append((canonical, i, 1.0, "dict"))
            else:
                best_score = max(
                    similarity_ratio(norm_h, s) for s in synonyms_norm
                )
                all_candidates.append((canonical, i, best_score, "edit"))

    # 一意性制約（§7.2.4 conflict resolution）
    # 1) 各 canonical について最良候補を選ぶ
    # 2) 入力列インデックスの重複を検出し、最上位スコアの canonical にだけ割当
    # 3) 負けた canonical は再計算対象として2位以降を採用（再帰的に）
    mapping = HeaderMapping()
    self._assign_uniquely(all_candidates, mapping, headers)

    # REQUIRED 検証
    missing_required = REQUIRED_COLUMNS - set(mapping.canonical_to_source_index.keys())
    if missing_required:
        raise HeaderMappingError(
            message=f"REQUIRED 列が確定できませんでした: {sorted(missing_required)}",
            hint="同義語辞書に存在しないヘッダーです。--mapping-file で明示してください",
        )
    return mapping

def _assign_uniquely(...):
    # ① タイブレーク優先度: dict > edit_distance_min > leftmost_column_index
    # ② 1入力列=最大1canonical 制約を守るため、競合時はスコア最上位のみ確定、
    #    敗者側は候補リストから該当列を除外して再選出
    # ③ 閾値判定:
    #     score >= 0.80 → confirmed
    #     0.60 <= score < 0.80 → needs_review_columns に追加＆確定
    #     score < 0.60 → unmapped_columns に追加（確定しない）
    ...
```

**テンプレート適用時**（`template is not None`）:
- `template.source_headers` と入力 `headers` を **完全一致**で照合。
- 入力側のヘッダー順序が変わっていても、`source` 文字列さえ見つかれば OK。
- 見つからなかった canonical は `unmapped_columns` に入れ、REQUIRED 違反で Fatal。

### 6.3 日付パーサ（`src/normalize/date_parser.py`）

```python
import re
from datetime import date

PATTERN_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
PATTERN_SLASH = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
PATTERN_REIWA_KANJI = re.compile(r"^令和(\d+)年(\d+)月(\d+)日$")
PATTERN_REIWA_ABBR = re.compile(r"^R(\d+)\.(\d+)\.(\d+)$")
PATTERN_DIGITS_8 = re.compile(r"^(\d{4})(\d{2})(\d{2})$")

REIWA_BASE_YEAR = 2018  # 令和1年 = 2019 → base=2018

def parse_date(raw: str) -> DateParseResult:
    s = normalize_text(raw)  # 全角→半角、空白除去

    if not s:
        return DateParseResult(None, False, "日付が空欄")

    for pattern, handler in [
        (PATTERN_ISO, _handle_ymd),
        (PATTERN_SLASH, _handle_ymd),
        (PATTERN_REIWA_KANJI, _handle_reiwa),
        (PATTERN_REIWA_ABBR, _handle_reiwa),
        (PATTERN_DIGITS_8, _handle_ymd),
    ]:
        m = pattern.match(s)
        if m:
            return handler(m, raw)

    return DateParseResult(None, False, f"認識できない日付形式: {raw}")

def _handle_ymd(m, raw):
    y, mo, d = map(int, m.groups())
    return _validate_ymd(y, mo, d, raw)

def _handle_reiwa(m, raw):
    ry, mo, d = map(int, m.groups())
    y = REIWA_BASE_YEAR + ry
    return _validate_ymd(y, mo, d, raw)

def _validate_ymd(y, mo, d, raw):
    if not (1 <= mo <= 12):
        return DateParseResult(None, False, f"月が不正（{mo}月は存在しない）")
    try:
        dt = date(y, mo, d)
    except ValueError:
        return DateParseResult(None, False, f"日付が実在しない: {y}-{mo}-{d}")
    return DateParseResult(dt.strftime("%Y-%m-%d"), True, "")
```

### 6.4 時刻パーサ（`src/normalize/time_parser.py`）

```python
PATTERN_HHMM = re.compile(r"^(\d{1,2}):(\d{1,2})$")
PATTERN_H_KANJI_M_KANJI = re.compile(r"^(\d{1,2})時(\d{1,2})分$")
PATTERN_H_KANJI = re.compile(r"^(\d{1,2})時$")

def parse_time(raw: str) -> TimeParseResult:
    s = normalize_text(raw).replace("：", ":")  # 全角コロン対応
    if not s:
        return TimeParseResult(None, False, False, "時刻が空欄")

    for pattern, use_minutes in [
        (PATTERN_HHMM, True),
        (PATTERN_H_KANJI_M_KANJI, True),
        (PATTERN_H_KANJI, False),
    ]:
        m = pattern.match(s)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2)) if use_minutes else 0
            return _validate_hm(h, mi, raw)

    return TimeParseResult(None, False, False, f"認識できない時刻形式: {raw}")

def _validate_hm(h, mi, raw):
    if h == 24 and mi == 0:
        return TimeParseResult("24:00", True, True, "24:00（要確認）")
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return TimeParseResult(None, False, False, f"時刻の範囲が不正: {h}:{mi}")
    return TimeParseResult(f"{h:02d}:{mi:02d}", True, False, "")
```

### 6.5 数値パーサ（`src/normalize/number_parser.py`）

```python
import re

STRIP_WAGE = re.compile(r"[￥¥,円\s]")
STRIP_MINUTES = re.compile(r"[分\s]")

def parse_wage(raw: str) -> NumberParseResult:
    s = normalize_text(raw)
    s_clean = STRIP_WAGE.sub("", s)
    if not s_clean:
        return NumberParseResult(None, False, "時給が空欄")
    try:
        n = int(s_clean)
    except ValueError:
        return NumberParseResult(None, False, f"数値に変換できない: {raw}")
    # R3 対応: 非負制約（時給は 0 円含め負値不可）
    if n < 0:
        return NumberParseResult(None, False, f"時給が負値: {raw}")
    return NumberParseResult(n, True, "")

def parse_minutes(raw: str) -> NumberParseResult:
    s = normalize_text(raw)
    # "1時間" → 60, "1時間30分" → 90 を許容
    m = re.match(r"^(\d+)時間(\d+)?分?$", s)
    if m:
        hours = int(m.group(1))
        mins = int(m.group(2)) if m.group(2) else 0
        # ここは正規表現で `\d+` 限定のため非負保証済
        return NumberParseResult(hours * 60 + mins, True, "")
    s_clean = STRIP_MINUTES.sub("", s)
    if not s_clean:
        return NumberParseResult(0, True, "")  # 空欄は 0 補完
    try:
        n = int(s_clean)
    except ValueError:
        return NumberParseResult(None, False, f"数値に変換できない: {raw}")
    # R3 対応: 非負制約（休憩分は 0 以上、負値不可）
    if n < 0:
        return NumberParseResult(None, False, f"休憩分が負値: {raw}")
    return NumberParseResult(n, True, "")
```

**制約まとめ（R3 対応）**: `parse_wage` / `parse_minutes` ともに値は `>= 0` の整数に限定する。負値・マイナス記号付き数値は `is_valid=False` として要確認行へ。上限は設けない（セミナーデモでの実運用に合わせて拡張しやすくするため）。

### 6.6 ポリシー分岐（`src/quality/policy.py`）

```python
def apply(self, result, ledger, policy):
    review_src_rows = ledger.review_source_row_nos
    review_rows = len(review_src_rows)
    output_rows: list[OutputRow] = []

    if policy == ErrorPolicy.FAIL and review_rows > 0:
        return PolicyOutcome(output_rows=[], ledger=ledger,
                             counters=Counters(len(result.rows), 0, 0, review_rows),
                             halted=True)

    output_idx = 2  # ヘッダー=1, データ1行目=2
    for row in result.rows:
        is_review_row = row.source_row_no in review_src_rows
        if policy == ErrorPolicy.DROP and is_review_row:
            continue
        # 値選択
        if policy == ErrorPolicy.KEEP:
            values = {
                col: (cell.raw_value if cell.is_review else cell.normalized_value)
                for col, cell in row.cells.items()
            }
        else:
            # drop（クリーン行のみここに来る）/ fail（review=0 確定後）
            values = {col: cell.normalized_value for col, cell in row.cells.items()}

        review_columns = [
            col for col, cell in row.cells.items() if cell.is_review
        ]
        output_rows.append(OutputRow(
            source_row_no=row.source_row_no,
            output_row_no=output_idx,
            has_review=is_review_row,
            review_columns=review_columns,
            values=values,
        ))
        output_idx += 1

    dropped = review_rows if policy == ErrorPolicy.DROP else 0
    return PolicyOutcome(
        output_rows=output_rows, ledger=ledger,
        counters=Counters(len(result.rows), len(output_rows), dropped, review_rows),
        halted=False,
    )
```

### 6.7 件数検証（`src/quality/counters.py`）

```python
def validate(self, c: Counters, policy: ErrorPolicy) -> None:
    if policy == ErrorPolicy.DROP:
        if c.input_rows != c.output_rows + c.dropped_rows:
            raise RowCountMismatchError(
                message=f"drop: input={c.input_rows} != output+dropped={c.output_rows + c.dropped_rows}",
                hint="件数カウンタの実装に不具合があります。--verbose で詳細確認してください",
            )
        if c.dropped_rows < c.review_rows:
            raise RowCountMismatchError(
                message=f"drop: dropped={c.dropped_rows} < review={c.review_rows}",
            )
    elif policy == ErrorPolicy.KEEP:
        if c.input_rows != c.output_rows:
            raise RowCountMismatchError(f"keep: input={c.input_rows} != output={c.output_rows}")
        if c.dropped_rows != 0:
            raise RowCountMismatchError(f"keep: dropped must be 0 (got {c.dropped_rows})")
    elif policy == ErrorPolicy.FAIL:
        # halted=True なら既に apply 段で処理済み、ここには来ない（書き出しスキップ）
        if c.input_rows != c.output_rows:
            raise RowCountMismatchError(f"fail: input={c.input_rows} != output={c.output_rows}")
        if c.dropped_rows != 0:
            raise RowCountMismatchError(f"fail: dropped must be 0 (got {c.dropped_rows})")
```

### 6.8 ConvertFlow 全体ステップ（`src/flows/convert.py`）

```python
def run(self, args: Namespace) -> int:
    # 0a. 追加 CLI バリデーション（§6.13、R3 対応）
    #     - --input-dir と --output の併用禁止
    #     - --input 単発で --output 未指定時の既定パス補完（out/<stem>.csv）
    self._validate_convert_args(args)

    # 0b. 単発 / バッチ分岐（argparse の mutually_exclusive_group で片方のみ必須）
    #    --input-dir 指定時は BatchRunner.run に委譲し、その戻り値をそのまま終了コードとする。
    #    BatchRunner.run の戻り値規約は §5.24（0=全成功 / 2=一部失敗 / 1=fail-fast 中断）。
    if getattr(args, "input_dir", None) is not None:
        return BatchRunner().run(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            args=args,
        )

    # --- 以下は単発 (--input) パスの処理 ---

    # 1. 入力パスガード（samples/ 配下、symlink 拒否）
    self._guard_input_path(args)

    # 2. dry-run ガードフラグ
    dry_run = args.dry_run

    # 3. 読み込み
    loader = TimesheetLoader()
    loaded = loader.load(args.input)

    # 3b. 出力系パス確定（§6.12、R3 対応）
    output_path, report_path, sidecar_path = self._resolve_paths(args)

    # 4. ヘッダー推論 or テンプレート適用
    if args.template:
        template_mapping = TemplateStore().load(args.template)
        mapping = HeaderInferencer().infer(loaded.headers, template=template_mapping)
    else:
        mapping = HeaderInferencer().infer(loaded.headers)

    # 5. 正規化
    result = TimesheetNormalizer().normalize(loaded, mapping)

    # 6. 要確認集約
    ledger = ReviewCollector().collect(result)

    # 7. ポリシー適用
    policy = ErrorPolicy(args.error_policy)
    outcome = ErrorPolicyApplier().apply(result, ledger, policy)

    # 8. fail ポリシーで halted の場合はレポートだけ出す（writer 停止）
    if outcome.halted:
        if not dry_run:
            BillingReportGenerator().generate(
                input_path=args.input,
                output_path=output_path,
                loaded=loaded,
                mapping=mapping,
                outcome=outcome,
                policy=policy,
                report_path=report_path,
                format=args.report_format,
            )
        self._print_summary_masked(outcome, policy)
        return 1

    # 9. 件数検証（書き出し前）
    RowCountValidator().validate(outcome.counters, policy)

    # 10. 書き出し（dry-run なら全停止）
    if not dry_run:
        self._guard_output_path(args)  # out/ 外は --allow-external-output 必須
        TimesheetWriter().write(outcome.output_rows, output_path, policy)
        if policy == ErrorPolicy.KEEP:
            TimesheetWriter().write_sidecar(outcome.output_rows, sidecar_path)
        BillingReportGenerator().generate(
            input_path=args.input,
            output_path=output_path,
            loaded=loaded,
            mapping=mapping,
            outcome=outcome,
            policy=policy,
            report_path=report_path,
            format=args.report_format,
        )

    # 11. 標準出力（マスク済み）
    self._print_summary_masked(outcome, policy)
    self._print_before_after_preview_masked(loaded, outcome)
    return 0
```

### 6.9 samples/ 配下検証と symlink 拒否（`src/flows/convert.py::_guard_input_path`）

```python
import stat

def _guard_input_path(self, args: Namespace) -> None:
    if args.allow_non_sample_input:
        logging.warning("--allow-non-sample-input 指定: 実データ投入禁止の責任はユーザーにあります")
        return

    input_path: Path = (args.input or args.input_dir)

    # --- Stage 1: resolve 前の経路要素を lstat で symlink チェック ---
    # resolve() は symlink を解決してしまうため、symlink検知は resolve 前に行う必要がある。
    # 入力パスを絶対化（symlink解決はしない）してから、samples/ までの各要素を遡ってチェック。
    try:
        absolute_input = input_path.absolute()  # resolve せず相対→絶対化のみ
    except OSError as e:
        raise InputValidationError(
            message=f"入力パスを絶対化できません: {input_path} ({e})",
        )
    samples_root_absolute = Path("samples").absolute()

    # 入力パス自身から samples/ までの各要素について lstat を評価
    p = absolute_input
    checked: list[Path] = []
    while True:
        checked.append(p)
        try:
            st = p.lstat()
        except FileNotFoundError:
            raise InputValidationError(
                message=f"input path does not exist: {p}",
            )
        if stat.S_ISLNK(st.st_mode):
            raise InputValidationError(
                message=f"symlink detected in input path: {p}",
                hint="samples/ 配下の symlink は拒否されます（経路途中含む）",
            )
        if p == samples_root_absolute or p.parent == p:
            break
        p = p.parent

    # --- Stage 2: resolve 後に samples/ 配下であることを確認 ---
    # symlink が無いことを確認済みなので、ここで resolve(strict=True) しても
    # 実体が samples/ 外に逃げていることは起こらない前提。二重防壁として配下判定を実施。
    resolved_input = absolute_input.resolve(strict=True)
    samples_root = samples_root_absolute.resolve(strict=True)
    try:
        resolved_input.relative_to(samples_root)
    except ValueError:
        raise InputValidationError(
            message=f"input must reside under samples/ unless --allow-non-sample-input is given: {input_path}",
            hint="実勤怠データは投入しないでください（デモ用モック）",
        )
```

**注**: 出力側 `_guard_output_path` は入力ガードとは異なり「**親ディレクトリの存在＋leaf（新規出力ファイル）の非存在を許容**」する。入力側の `lstat` による存在必須チェックを出力にそのまま転用すると、新規ファイルの書き出しが常に拒否されてしまうため分離する。

```python
def _guard_output_path(self, args: Namespace) -> None:
    """--allow-external-output 未指定時、出力パスが out/ 配下に収まることを保証。
    経路上の symlink も拒否するが、leaf（出力ファイル自身）は「まだ存在しない」ケースを許容する。
    """
    if args.allow_external_output:
        logging.warning("--allow-external-output 指定: out/ 外への書き出しを許可します")
        return

    output_path: Path = args.output
    try:
        absolute_output = output_path.absolute()
    except OSError as e:
        raise InputValidationError(message=f"出力パスを絶対化できません: {output_path} ({e})")
    out_root_absolute = Path("out").absolute()

    # --- Stage 1: 親ディレクトリ以上の経路要素のみ lstat で symlink チェック ---
    # leaf はまだ存在しない前提で検査対象から外す（親ディレクトリは存在必須）。
    parent = absolute_output.parent
    p = parent
    while True:
        try:
            st = p.lstat()
        except FileNotFoundError:
            raise InputValidationError(
                message=f"出力先の親ディレクトリが存在しません: {p}",
                hint="mkdir で作成するか --output-dir を正しい既存ディレクトリに指定してください",
            )
        if stat.S_ISLNK(st.st_mode):
            raise InputValidationError(
                message=f"symlink detected in output path: {p}",
                hint="out/ 配下の symlink は拒否されます（経路途中含む）",
            )
        if p == out_root_absolute or p.parent == p:
            break
        p = p.parent

    # --- Stage 2: resolve 後に out/ 配下であることを確認（leaf 非存在を許容）---
    # leaf が未作成のため parent を resolve(strict=True) した上で leaf 名を付け直す。
    resolved_parent = parent.resolve(strict=True)
    resolved_output = resolved_parent / absolute_output.name
    out_root = out_root_absolute.resolve(strict=True)
    try:
        resolved_output.relative_to(out_root)
    except ValueError:
        raise InputValidationError(
            message=f"output must reside under out/ unless --allow-external-output is given: {output_path}",
            hint="--allow-external-output を付けるか、--output を out/ 配下に指定してください",
        )
```

**バッチ時の出力先ディレクトリガード（R3 対応）**: `BatchRunner.run` から冒頭で呼ばれる共通ガード。

```python
def _guard_output_dir_for_batch(output_dir: Path, allow_external: bool) -> None:
    """--input-dir 運用時の出力先ディレクトリを symlink + out/ 配下制約で検証する。

    単発の `_guard_output_path` を leaf=ファイル名ではなく leaf=ディレクトリに対して適用した版。
    ディレクトリが未作成の場合は親まで存在＋親が symlink でないことまで保証する。
    """
    if allow_external:
        logging.warning("--allow-external-output 指定: out/ 外の output_dir を許可します")
        return
    absolute = output_dir.absolute()
    out_root_absolute = Path("out").absolute()
    # 経路 symlink 検査（leaf=output_dir は未存在許容）
    start = absolute if absolute.exists() else absolute.parent
    p = start
    while True:
        try:
            st = p.lstat()
        except FileNotFoundError:
            raise InputValidationError(
                message=f"--output-dir の親ディレクトリが存在しません: {p}",
                hint="既存ディレクトリを指定するか、事前に mkdir してください",
            )
        if stat.S_ISLNK(st.st_mode):
            raise InputValidationError(
                message=f"symlink detected in --output-dir path: {p}",
                hint="バッチ出力先の経路上に symlink は置けません",
            )
        if p == out_root_absolute or p.parent == p:
            break
        p = p.parent
    # resolve 後 out/ 配下判定（leaf 未存在時は parent を resolve）
    resolved = (absolute if absolute.exists() else absolute.parent).resolve(strict=True)
    if not absolute.exists():
        resolved = resolved / absolute.name
    out_root = out_root_absolute.resolve(strict=True)
    try:
        resolved.relative_to(out_root)
    except ValueError:
        raise InputValidationError(
            message=f"--output-dir must reside under out/ unless --allow-external-output is given: {output_dir}",
            hint="--allow-external-output を付けるか、--output-dir を out/ 配下に指定してください",
        )
```

### 6.10 テンプレート保存時の PII 混入防止（`src/template/store.py::save`）

```python
def save(self, name, mapping, encoding, dialect, source_hint, force=False):
    # 命名規則検証
    if not self.NAME_PATTERN.match(name):
        raise TemplateSchemaError(
            message=f"テンプレート名は snake_case 半角英数字+_ のみ: {name}",
        )

    out_path = self.TEMPLATES_DIR / f"{name}.json"
    if out_path.exists() and not force:
        raise TemplateExistsError(
            message=f"テンプレートが既に存在: {out_path}",
            hint="--force で上書き、または _v2 サフィックスで別名保存",
        )

    # PII 混入防止は「構造ホワイトリスト検証」で行う（全文字列走査は誤検知/漏れが両方発生するため廃止）
    payload = self._build_payload(name, mapping, encoding, dialect, source_hint)
    self._verify_structure_whitelist(payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path

def _verify_structure_whitelist(self, payload: dict) -> None:
    """テンプレート payload の構造をホワイトリストで検証する。

    - トップレベルのキーは ALLOWED_TEMPLATE_TOP_KEYS のみ許可（未知キー混入で TemplateSchemaError）
    - header_mapping 要素のキーは ALLOWED_HEADER_MAPPING_KEYS のみ許可
    - 各フィールドの型を厳密検査（dict/list/str/int/float/bool のいずれか）
    - 文字列値のネストは header_mapping[*].source（入力側ヘッダー名）と source_hint（ファイル名）のみ
      → "データ値"（氏名や時給の値）を保持する経路が構造上存在しないことを保証する

    この構造検証を通過した payload は「列対応付けメタデータのみ」を含み、
    PII_VALUE_FIELDS_DENYLIST に示される "値" を含まないことが保証される。
    """
    # トップレベル検査
    extra = set(payload.keys()) - ALLOWED_TEMPLATE_TOP_KEYS
    if extra:
        raise TemplateSchemaError(
            message=f"テンプレート payload に未許可のキーが含まれています: {sorted(extra)}",
            hint="header_mapping は列の対応付けのみを保持します。データ値を混入しないでください",
        )
    # header_mapping 要素検査
    for entry in payload.get("header_mapping", []):
        if not isinstance(entry, dict):
            raise TemplateSchemaError(message="header_mapping の要素は dict である必要があります")
        extra = set(entry.keys()) - ALLOWED_HEADER_MAPPING_KEYS
        if extra:
            raise TemplateSchemaError(
                message=f"header_mapping エントリに未許可のキー: {sorted(extra)}",
            )
        # canonical 列名が PII_VALUE_FIELDS_DENYLIST の "値" キー（例: "name_value"）を持つ経路を遮断
        # ここでは entry.keys() がすでに ALLOWED_HEADER_MAPPING_KEYS に限定されているため追加検査は不要

    # 値検証: header_mapping[*].source / source_hint に "データ値"（氏名・数値）が
    #          紛れ込んでいないか、ヘッダー妥当性チェックを行う。
    #          R3 指摘への対応: 構造ホワイトリストだけでは許可キーの "値" に PII が入り得るため、
    #          値側もデータ値っぽい文字列を拒否する防御層を追加。
    _HEADER_VALUE_SANITY_MAX_LEN = 64
    _HEADER_VALUE_REJECT_PATTERNS = [
        re.compile(r"^\d{3,}$"),                          # 純数値（社員番号・時給の値など）
        re.compile(r"^[¥￥]?[\d,]+円?$"),                  # 金額表記
        re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"),     # 日付値
        re.compile(r"^\d{1,2}:\d{2}$"),                    # 時刻値
    ]

    def _assert_header_string_is_not_data_value(self, label: str, value: str) -> None:
        """ヘッダー文字列（入力CSVのヘッダー名）として妥当か軽く検査する。

        "値" と判定されたら PII 混入の可能性があるため拒否する（TemplateSchemaError）。
        """
        if not isinstance(value, str) or not value:
            raise TemplateSchemaError(message=f"{label} は非空文字列である必要があります")
        if len(value) > self._HEADER_VALUE_SANITY_MAX_LEN:
            raise TemplateSchemaError(
                message=f"{label} がヘッダー名として長すぎます（{len(value)}字）。データ値の混入を疑います",
            )
        for pat in self._HEADER_VALUE_REJECT_PATTERNS:
            if pat.match(value):
                raise TemplateSchemaError(
                    message=f"{label} がデータ値に見えます: {value!r}",
                    hint="header_mapping[].source はヘッダー名のみを保存します。データ行の値を渡さないでください",
                )
```

`_verify_structure_whitelist` の後半で、`header_mapping[*].source` と `source_hint`
の各文字列について `_assert_header_string_is_not_data_value` を適用する（構造検証 +
値検証の二段構え）。これにより、R3 指摘のとおり許可キー内の "値" 側での PII 混入経路も閉じる。

### 6.11 拡張子判定の統一仕様

- **判定式**: `path.suffix.lower() == ".csv"`（大文字小文字非依存）。
- **単発 `--input` 指定**: 上記に合致しない場合は `InputValidationError`（`[ERROR] input: 拡張子は .csv である必要があります: <path>`）。
- **`--input-dir` 指定**: 合致しないファイルは **warning skip**（§5.24 参照）。Fatal にはしない。
- `glob("*.csv")` は大文字小文字依存なので使わない。`iterdir() + suffix.lower()` で統一する。

### 6.12 出力パス・レポートパス・sidecar パスの生成規約

R3 指摘対応: `report_path` / `sidecar_path` の決定ロジックを仕様で固定し、実装者依存を排する。

**単発実行（`--input`）**:

| 種別 | 既定パス | 決定ロジック |
|---|---|---|
| 本体出力 | `out/<input_basename>.csv` | `--output` が None のとき `Path("out") / f"{args.input.stem}.csv"` |
| レポート | `<output_path.with_name(output_path.stem + "_report" + ext)>` | ext は `args.report_format` が `md` のとき `.md`、`csv` のとき `.csv` |
| sidecar | `<output_path.with_name(output_path.stem + "_needs_review.csv")>` | `keep` ポリシー時のみ |

**バッチ実行（`--input-dir`）**:

| 種別 | 既定パス |
|---|---|
| 本体出力 | `<args.output_dir>/<file.stem>.csv` |
| レポート | `<args.output_dir>/<file.stem>_report.{md,csv}` |
| sidecar | `<args.output_dir>/<file.stem>_needs_review.csv` |

**命名衝突時**: 本体出力・レポート・sidecar のいずれも、既存ファイルがあれば上書きする（デモ用途、`--force` 扱いの強制フラグは設けない）。ユーザーは `cleanup` サブコマンドか手動削除で事前整理する前提。

**決定タイミング**: `ConvertFlow.run` の Step 3（読み込み）直後、Step 10（書き出し）の前に上記 3 変数を確定させる。`_resolve_paths(args) -> tuple[Path, Path, Path]` を内部ヘルパとして実装し、`output_path, report_path, sidecar_path` を返す。

### 6.13 CLI 引数バリデーション（`build_parser` 後に `ConvertFlow` 冒頭で実行）

R3 指摘対応: 仕様本文だけでなく疑似コードで `--input` / `--input-dir` / `--output` / `--output-dir` の排他・既定を強制する。

```python
def _validate_convert_args(self, args: Namespace) -> None:
    """argparse の mutually_exclusive_group 後に残る論理矛盾を検査する。"""
    # --input-dir と --output は併用不可（§7.2）
    if args.input_dir is not None and args.output is not None:
        raise InputValidationError(
            message="--input-dir と --output は併用できません",
            hint="ディレクトリ一括の出力先は --output-dir を使ってください",
        )
    # --input 指定時、--output 未指定なら既定パスを補完（§6.12）
    if args.input is not None and args.output is None:
        args.output = Path("out") / f"{args.input.stem}.csv"
    # --input-dir 指定時は --output-dir が必須（argparse の default=Path("out") により常に設定済）
    # ここで追加チェックは不要。
```

この関数は `ConvertFlow.run` の **Step 0 の直前** で呼ぶ（§6.8 先頭）。

### 7.1 argparse 構造

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-automation",
        description="勤怠CSV自動整形デモ（クラウドスタッフィング AIデモ No.01）",
    )
    parser.add_argument("--version", action="version", version=_version_message())

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # --- convert ---
    p_conv = sub.add_parser("convert", help="単発 or ディレクトリ一括変換")
    grp = p_conv.add_mutually_exclusive_group(required=True)
    grp.add_argument("--input", type=Path)
    grp.add_argument("--input-dir", type=Path)
    p_conv.add_argument("--output", type=Path)
    p_conv.add_argument("--output-dir", type=Path, default=Path("out"))
    p_conv.add_argument("--template", type=str)
    p_conv.add_argument("--error-policy", choices=["drop", "keep", "fail"], default="drop")
    p_conv.add_argument("--report-format", choices=["md", "csv"], default="md")
    p_conv.add_argument("--dry-run", action="store_true")
    p_conv.add_argument("--fail-fast", action="store_true")
    p_conv.add_argument("--allow-external-output", action="store_true")
    p_conv.add_argument("--allow-non-sample-input", action="store_true")
    p_conv.add_argument("--verbose", action="store_true")

    # --- save-template ---
    p_tpl = sub.add_parser("save-template", help="テンプレートJSON生成")
    p_tpl.add_argument("--input", type=Path, required=True)
    p_tpl.add_argument("--name", type=str, required=True)
    mode = p_tpl.add_mutually_exclusive_group()
    mode.add_argument("--interactive", action="store_true")
    mode.add_argument("--mapping-file", type=Path)
    p_tpl.add_argument("--force", action="store_true")
    p_tpl.add_argument("--allow-non-sample-input", action="store_true")
    p_tpl.add_argument("--verbose", action="store_true")

    # --- cleanup ---
    p_cln = sub.add_parser("cleanup", help="out/ と samples/tmp_* の削除（MAY）")
    p_cln.add_argument("--dry-run", action="store_true")

    return parser
```

### 7.2 CLI オプション一覧（convert）

| オプション | 型 | 既定 | バリデーション |
|---|---|---|---|
| `--input` | `Path` | ― | `--input-dir` と排他、少なくとも片方必須 |
| `--input-dir` | `Path` | ― | 同上 |
| `--output` | `Path` | `out/<basename>.csv` | `--input-dir` と併用で**エラー** |
| `--output-dir` | `Path` | `out/` | バッチ出力先 |
| `--template` | `str` | ― | `templates/<name>.json` 存在必須 |
| `--error-policy` | `drop`/`keep`/`fail` | `drop` | choices 制限 |
| `--report-format` | `md`/`csv` | `md` | choices 制限 |
| `--dry-run` | flag | off | 書き出し全停止 |
| `--fail-fast` | flag | off | バッチ失敗時即停止 |
| `--allow-external-output` | flag | off | `out/` 外書き出し許可 |
| `--allow-non-sample-input` | flag | off | `samples/` 外入力許可（警告出力） |
| `--verbose` | flag | off | DEBUG ログ stderr |

### 7.3 終了コード表

| コード | 意味 | 発生条件 |
|---|---|---|
| `0` | 全成功 | 正常完了、または `fail` ポリシーで `review_rows=0` |
| `1` | 致命的エラー | 以下のいずれか |
| | | - ファイル未存在 / I/O エラー |
| | | - `EncodingDetectionError` |
| | | - `HeaderMappingError`（REQUIRED 未確定） |
| | | - `RowCountMismatchError` |
| | | - fail ポリシー + `review_rows>0`（`PolicyOutcome.halted=True`。例外ではなく戻り値で `ConvertFlow.run` が 1 を返す） |
| | | - `InputValidationError`（samples/外、symlink、排他違反） |
| | | - `TemplateSchemaError` / `TemplateExistsError` |
| | | - `MappingFileError` |
| | | - バッチ `--fail-fast` で1件でも失敗 |
| `2` | バッチ一部失敗（MAY） | `--fail-fast` 未指定かつ継続完了でエラー1件以上 |
| `130` | ユーザー中断 | `KeyboardInterrupt`（Ctrl+C）。`main()` 一元キャッチで出力 |

### 7.4 標準出力/標準エラーの出し分け

- **stdout**: 進捗ログ（S5）、件数サマリ（M7）、Before/After 先頭3行プレビュー（S2）。
- **stderr**: 警告、エラー、`--verbose` の DEBUG。
- 両方とも `[LEVEL] component: message` 形式（§9）。

---

## 8. エラー処理と例外階層

### 8.1 例外と発生条件

| 例外クラス | 発生条件 | 終了コード |
|---|---|---|
| `InputValidationError` | CLI 引数不整合、`samples/` 外入力、symlink 検出、単発 `--input` で非CSV指定 | 1 |
| `EncodingDetectionError` | UTF-8/CP932 両方失敗 | 1 |
| `DialectDetectionError` | 区切り文字・改行判定失敗 | 1 |
| `HeaderMappingError` | REQUIRED 列のいずれかが未確定（空CSV・全列未マッピング含む） | 1 |
| `TemplateSchemaError` | テンプレートJSONスキーマ違反、命名規則違反、PII値混入 | 1 |
| `TemplateExistsError` | `--force` なし上書き | 1 |
| `MappingFileError` | `--mapping-file` の読み込み/スキーマ/source 不一致 | 1 |
| `RowCountMismatchError` | M7 関係式不成立 | 1 |

**fail ポリシー + `review_rows>0` の扱い（例外非使用、戻り値規約）**:
`FailPolicyHalt` は廃止。`ErrorPolicyApplier.apply` が `PolicyOutcome.halted=True` を返し、`ConvertFlow.run` が writer を停止してレポートのみ出力の上 `return 1` する（§6.6 / §6.8）。例外を投げないため、`_CATEGORY_BY_EXC` にも載せない。標準エラーへのカテゴリ出力は `[ERROR] policy: review_rows>0 でfailポリシーが停止しました` を `ConvertFlow` 側で明示 print する。

### 8.2 エラーメッセージ規約

```
[ERROR] <category>: <message>
        hint: <recovery action>
```

- `<category>`: `encoding` / `dialect` / `header` / `policy` / `counters` / `template` / `mapping_file` / `input`
- `<message>`: 日本語または英語（技術的詳細）
- `<hint>`: 日本語のユーザー向け復旧手順

**実装例**:

```python
try:
    loaded = loader.load(path)
except EncodingDetectionError as e:
    print(f"[ERROR] encoding: {e.message}", file=sys.stderr)
    if e.hint:
        print(f"        hint: {e.hint}", file=sys.stderr)
    return 1
```

### 8.3 `main()` での一元キャッチ

```python
# 例外クラス→ §8.2 のカテゴリ文字列の明示マップ（class名からの lower() 変換だと
# `rowcountmismatch` 等、規約外カテゴリ名になるため明示マップで固定する）
_CATEGORY_BY_EXC: dict[type, str] = {
    InputValidationError: "input",
    EncodingDetectionError: "encoding",
    DialectDetectionError: "dialect",
    HeaderMappingError: "header",
    TemplateSchemaError: "template",
    TemplateExistsError: "template",
    MappingFileError: "mapping_file",
    RowCountMismatchError: "counters",
}

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose if hasattr(args, "verbose") else False)
    try:
        if args.subcommand == "convert":
            return ConvertFlow().run(args)
        elif args.subcommand == "save-template":
            return SaveTemplateFlow().run(args)
        elif args.subcommand == "cleanup":
            return CleanupFlow().run(args)
    except DemoError as e:
        category = _CATEGORY_BY_EXC.get(type(e), "error")
        print(f"[ERROR] {category}: {e.message}", file=sys.stderr)
        if e.hint:
            print(f"        hint: {e.hint}", file=sys.stderr)
        return 1
    except (FileNotFoundError, OSError) as e:
        # 各モジュールで DemoError 系へラップし損ねた I/O 例外の最終セーフティネット。
        # 通常ルートでは ①loader が InputValidationError にラップ、②TemplateStore.load も
        # InputValidationError にラップし、ここには到達しない設計。到達した場合も
        # §7.3 / §8 の終了コード規約（1）と §8.2 のメッセージ形式を保つため整形する。
        print(f"[ERROR] input: {e}", file=sys.stderr)
        print("        hint: 入力/出力パスと権限を確認してください", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("[ERROR] interrupted by user", file=sys.stderr)
        return 130
```

---

## 9. ログ仕様

### 9.1 ログレベル定義

| レベル | 用途 | 出力先 |
|---|---|---|
| DEBUG | `--verbose` 時のみ。各ステップ詳細、推論スコア | stderr |
| INFO | 進捗（S5）、件数サマリ、Before/After プレビュー | stdout |
| WARNING | `--allow-non-sample-input` 注意、任意列未マッピング、`.csv` 以外スキップ | stderr |
| ERROR | 致命エラー | stderr |

### 9.2 ログフォーマット

```
[INFO] convert: [1/5] samples/timesheet_202604_haken_a.csv → out/timesheet_202604_haken_a.csv (input=10 output=9 dropped=1 review=1)
[WARNING] loader: skipping non-csv file: samples/tmp_note.txt
[ERROR] encoding: UTF-8/CP932 いずれでもデコードできませんでした
        hint: ファイルの文字コードを UTF-8 にしてから再実行してください
```

### 9.3 `logging` 設定実装

```python
import logging
import sys

def _configure_logging(verbose: bool) -> None:
    fmt = "[%(levelname)s] %(name)s: %(message)s"
    level = logging.DEBUG if verbose else logging.INFO
    # INFO は stdout、WARNING 以上は stderr
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(lambda r: r.levelno < logging.WARNING)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)

    fmt_obj = logging.Formatter(fmt)
    stdout_handler.setFormatter(fmt_obj)
    stderr_handler.setFormatter(fmt_obj)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(stdout_handler)
    root.addHandler(stderr_handler)
```

### 9.4 PII マスキング適用箇所

| 箇所 | マスク適用 | 実装関数 |
|---|---|---|
| 件数サマリ stdout | N/A（件数のみ） | ― |
| Before/After プレビュー stdout | **適用** | `PIIMasker.mask_row` |
| 進捗ログ stdout | N/A（ファイル名のみ） | ― |
| DEBUG ログ stderr | **適用**（値が含まれる場合） | `PIIMasker.mask_row` |
| エラーメッセージ stderr | **適用**（値が含まれる場合） | 必要箇所で `mask_name` / `mask_wage` |
| 整形済 CSV / レポート / テンプレート | **非適用** | ― |

---

## 10. テスト設計

### 10.1 方針

- **既定**: 標準ライブラリ `unittest` を用いる（外部依存ゼロ方針 §2.2 と整合）。実行は `python -m unittest discover tests`。
- pytest は **任意 dev 依存**として README に記載のみ行う（プロジェクトの `requirements.txt` / `pyproject.toml` には載せない）。
- **§10.3 のサンプルコード記法について**: 本書のサンプルは読みやすさ優先で `assert` / `pytest.raises` / `...` プレースホルダ記法で示しているが、**実装は `unittest.TestCase` ベースで行う**。対応表:
  - `assert x == y` → `self.assertEqual(x, y)`
  - `with pytest.raises(E):` → `with self.assertRaises(E):`
  - `tmp_path` フィクスチャ → `tempfile.TemporaryDirectory()` を setUp/tearDown で使用
  - `...` が残るテスト本体 → Phase5 実装時に具体化
- テスト自動化は MAY。最小実装前提で、重要ケースのみ手動＋自動で確認。
- fixture CSV は `tests/fixtures/` に配置し、要件§10.2〜10.4 のサンプルから抜粋。

### 10.2 単体テスト対象モジュール

| モジュール | 重要テスト |
|---|---|
| `src/io/encoding.py` | UTF-8, UTF-8-BOM, CP932 それぞれの判定、不明文字コードで例外 |
| `src/mapping/inferencer.py` | 辞書ヒット、編集距離、閾値境界（0.80/0.60）、一意性制約、REQUIRED 未確定で例外 |
| `src/normalize/date_parser.py` | ISO / スラッシュ / 令和漢字 / R略記 / 8桁塊 / 不正月 / 実在しない日付 |
| `src/normalize/time_parser.py` | HH:MM / H:M / 全角コロン / H時M分 / H時 / 24:00（要確認） |
| `src/normalize/number_parser.py` | `¥1,500` / `1500円` / 全角 / 分・時間 / 空欄（break_minutes は 0） |
| `src/quality/policy.py` | drop/keep/fail それぞれで行選択・値選択が正しいこと |
| `src/quality/counters.py` | 関係式不成立時に RowCountMismatchError |
| `src/security/mask.py` | `山田 太郎` → `山***`, `Alice` → `A***`, `1500` → `****` |
| `src/template/store.py` | 命名規則違反、上書き拒否、PII 値混入検知 |
| `src/template/mapping_file.py` | JSON 読み込み、YAML 拒否、source 不一致で例外 |

### 10.3 重要テストケース（入力 → 期待出力）

#### ハッピーパス

```python
def test_encoding_utf8():
    assert detect_encoding(Path("tests/fixtures/haken_a.csv")) == "utf-8"

def test_header_inferencer_dict_hit():
    mapping = HeaderInferencer().infer(["社員コード", "氏名", "勤務日", "始業", "終業", "休憩", "時給"])
    assert mapping.canonical_to_source_index == {
        "employee_id": 0, "name": 1, "work_date": 2,
        "start_time": 3, "end_time": 4, "break_minutes": 5, "hourly_wage": 6,
    }
    assert all(s == 1.0 for s in mapping.confidence.values())

def test_date_parser_reiwa_kanji():
    r = parse_date("令和8年4月23日")
    assert r.is_valid and r.value == "2026-04-23"
```

#### エッジケース

```python
def test_date_parser_invalid_month():
    r = parse_date("令和8年13月5日")
    assert not r.is_valid and "月が不正" in r.reason

def test_time_parser_24_hour_is_review():
    r = parse_time("24:00")
    assert r.is_valid and r.is_24_hour and r.value == "24:00"

def test_number_parser_break_empty_is_zero():
    r = parse_minutes("")
    assert r.is_valid and r.value == 0

def test_mask_name_japanese():
    assert mask_name("山田 太郎") == "山***"

def test_mask_name_empty():
    assert mask_name("") == ""

def test_mask_wage_fixed_length():
    assert mask_wage("1500") == "****"
    assert mask_wage("99999999") == "****"  # 桁数を漏らさない
```

#### 異常系

```python
def test_encoding_detection_failure(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_bytes(b"\xff\xfe\x00\x00invalid")  # UTF-32 BOM等
    with pytest.raises(EncodingDetectionError):
        detect_encoding(p)

def test_row_count_mismatch_drop():
    counters = Counters(input_rows=4, output_rows=1, dropped_rows=2, review_rows=3)
    with pytest.raises(RowCountMismatchError):
        RowCountValidator().validate(counters, ErrorPolicy.DROP)

def test_header_mapping_required_missing():
    # employee_id のみ消した状態
    with pytest.raises(HeaderMappingError):
        HeaderInferencer().infer(["氏名", "勤務日", "始業", "終業", "時給"])

def test_template_name_invalid():
    store = TemplateStore()
    with pytest.raises(TemplateSchemaError):
        store.save("派遣元A", ...)  # 日本語不可

def test_template_exists_without_force(tmp_path):
    # 既存ファイルを置いた状態で force=False → TemplateExistsError
    ...

def test_empty_csv_raises_header_mapping_error(tmp_path):
    # 空CSV（0バイトまたはヘッダー行のみ）は REQUIRED 未確定で Fatal
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8")
    with pytest.raises(HeaderMappingError):
        ConvertFlow().run(_build_args(input=p))  # 実装では main 経由でも可

def test_input_path_with_symlink_is_rejected(tmp_path):
    # samples/ 配下の symlink は拒否（--allow-non-sample-input 未指定）
    target = tmp_path / "real.csv"
    target.write_text("a,b\n", encoding="utf-8")
    link = tmp_path / "samples" / "link.csv"
    link.parent.mkdir(parents=True)
    link.symlink_to(target)
    with pytest.raises(InputValidationError):
        ConvertFlow()._guard_input_path(_build_args(input=link))

def test_external_output_rejected_without_flag(tmp_path):
    # --allow-external-output 未指定かつ out/ 配下外への書き出しは InputValidationError
    out_outside = tmp_path / "somewhere_else" / "foo.csv"
    with pytest.raises(InputValidationError):
        ConvertFlow()._guard_output_path(_build_args(
            output=out_outside, allow_external_output=False,
        ))
```

**E2E 側にも以下3ケースを追加**（§10.5 手動チェックリスト末尾に追記）:

- [ ] 空CSV（0バイト）を `--input` に渡して `exit=1` かつ `HeaderMappingError` が stderr に出る
- [ ] `samples/` 配下に symlink を作って `--input` に渡して `exit=1` かつ `[ERROR] input: symlink detected ...`
- [ ] `--output /tmp/foo.csv --allow-external-output` 未指定で `exit=1` かつ `[ERROR] input:` 系のエラーが出る

### 10.4 サンプルデータとの対応

| サンプル | 検証観点 |
|---|---|
| `tests/fixtures/haken_a.csv`（要件§10.2相当） | 列順逆転・令和表記、全列クリーン変換 |
| `tests/fixtures/haken_b_bom_cp932.csv`（§10.3相当） | BOM 検出、CP932 decode、全角半角混在 |
| `tests/fixtures/haken_c_errors.csv`（§10.4相当） | エラー検出率 4/4（要件成功基準） |

### 10.5 E2E テスト（手動チェックリスト）

セミナー本番前に必須で実行する手動確認:

- [ ] `python src/main.py convert --input samples/timesheet_202604_haken_a.csv` が 5 秒以内に成功し `out/timesheet_202604_haken_a.csv` が生成される
- [ ] `out/timesheet_202604_haken_a_report.md` にヘッダーマッピング結果・件数サマリが記載されている
- [ ] `samples/timesheet_202604_haken_c.csv` で `drop` ポリシー実行時、要確認行 3 件がレポートに検出される
- [ ] `save-template` → 翌月ファイルに `--template haken_a` 適用が成功
- [ ] 標準出力の Before/After に氏名・時給のマスクが適用されている
- [ ] `--dry-run` 指定時は `out/` にファイルが一切生成されない
- [ ] `--error-policy fail` + 要確認行ありで `exit=1` かつ整形済CSV未出力・レポート出力あり

---

## 付録A. 同義語辞書の初期エントリ（サンプル）

§5.7 参照。Phase5 初期はこのエントリで着手し、派遣業界固有の表記揺れが見つかり次第追記する。追記方針は「派遣元実例をセミナー後にヒアリング→`src/mapping/synonyms.py` に追加→テストケース追加」の順。

## 付録B. サンプル CSV バイト列（抜粋）

### B.1 `samples/timesheet_202604_haken_a.csv`（UTF-8, LF）

```
時給,終業,始業,勤務日,氏名,社員コード,休憩（分）
"￥1,500",18:00,9:00,令和8年4月23日,山田　太郎,EMP001,60
"￥1,600",19:00,10:00,R8.4.23,佐藤　花子,EMP002,60
```

### B.2 `samples/timesheet_202604_haken_b.csv`（CP932, BOM + CRLF）

バイト冒頭: `EF BB BF` (BOM) → `93 5C 8B C6 88 F5 49 44` (`従業員ID` の CP932) → ...

```
従業員ID,ﾅﾏｴ,日付,開始,終了,休憩,時給
ＥＭＰ００１,山田太郎,2026/4/23,9：00,18：00,1時間,"1,500円"
EMP002, 佐藤花子 ,2026-4-23,10時,19時,60分,￥1600
```

### B.3 `samples/timesheet_202604_haken_c.csv`（UTF-8, LF, エラー混入）

```
社員コード,氏名,勤務日,始業,終業,休憩,時給
EMP001,山田太郎,2026-04-23,09:00,18:00,60,1500
EMP002,佐藤花子,令和8年13月5日,10:00,19:00,60,1600
EMP003,,2026-04-23,09:00,08:00,60,1500
EMP004,鈴木一郎,2026-04-23,09:00,18:00,,abc円
```

---

## 付録C. 実装上の決定記録

### C.1 設定ファイル形式は JSON に統一（PyYAML 不採用）

- **選択**: テンプレート・マッピングファイルともに JSON のみ。
- **却下案**: PyYAML を採用して YAML も許容する。
- **理由**: 要件非機能§5「外部依存なし」との整合。JSON は標準ライブラリで完結。
- **影響**:
  - 設計書 6.1.2 の `--mapping-file <yaml>` 記述は本仕様で **JSON 限定** に確定（CLI ヘルプにも `JSON file only` と明記）。
  - 要件書 `01_requirements.md:90` の `--mapping-file <yaml>` は本仕様を正として **JSON 限定** に読み替える（要件書の次回改訂時に文面修正予定）。仕様書・設計書・要件書の3文書間の食い違いは本仕様書 §4.5 / §5.20 / 付録C.1 を最終トリガーとして解消する。
  - 拡張子 `.yml` / `.yaml` を指定された場合は `MappingFileLoader.load` が即 `MappingFileError` を送出する（§5.20）。

### C.2 編集距離に `difflib.SequenceMatcher.ratio()` を採用（Levenshtein 自前不採用）

- **選択**: `difflib` 標準ライブラリ。
- **却下案**: Levenshtein を自前実装。
- **理由**: 派遣業界の表記揺れは辞書でほぼ解決する前提で、編集距離はフォールバック用途。`difflib` の 0.0〜1.0 正規化スコアがそのまま閾値判定に使える。

### C.3 CLI ライブラリは `argparse`（click/typer 不採用）

- **選択**: 標準 `argparse`。
- **却下案**: click / typer（型ヒントからの自動生成など便利）。
- **理由**: 外部依存ゼロ方針。本デモのオプション数では `argparse` で十分読める。

### C.4 件数検証は `assert` ではなく明示例外

- **選択**: `RowCountMismatchError` を raise。
- **却下案**: `assert` 文で簡潔に書く。
- **理由**: Python `-O` 起動で assert が無効化されると fail-fast が静かに失われる。本機能は「壊れた結果を出さない」ことが価値の中核なので、実行時に必ず検証される明示例外を採用（設計書 7.5 の方針を本仕様で確定）。

### C.5 `mask_wage` は桁数保持しない固定長 `****`

- **選択**: 全桁を 4 文字の `****` に置換。
- **却下案**: 桁数保持（`1500` → `****`、`99999` → `*****`）。
- **理由**: 桁数情報自体が漏洩リスク（5桁 = 1万円以上等を推測可能）。セミナーでの誤解を避けるため固定長に仕様固定（設計書 7.7 と整合）。

### C.6 dataclass を全面採用（TypedDict/Pydantic 不採用）

- **選択**: 標準 `dataclasses`。`frozen=True` を不変データに適用。
- **却下案**: Pydantic（バリデーション自動化）、TypedDict（軽量）。
- **理由**: Pydantic は外部依存になるため却下。TypedDict はメソッド生やせないのでロジックを持つ型で不便。`dataclass` が標準＋機能のバランスで最適。

### C.7 Python `match` 文の活用範囲

- **選択**: `ErrorPolicyApplier.apply` のポリシー分岐など、3以上の選択肢で使用。
- **却下案**: すべて `if/elif` で統一。
- **理由**: Python 3.11.x 固定（§2.1）を明記しており、`match` 文の可読性向上が明確な箇所に限定採用。

---

以上で Phase5 実装着手条件を満たす。実装者は本仕様書のシグネチャ通りにモジュールを作成し、§6 のアルゴリズム近似コードを具体化すればよい。
