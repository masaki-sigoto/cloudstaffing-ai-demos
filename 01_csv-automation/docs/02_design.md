# システム設計書: CSV加工の完全自動化（勤怠CSV自動整形デモ）

- バージョン: 1.3（Codex R3 指摘反映版・最終）
- 対応要件定義書: `01_requirements.md`
- 対象プロジェクト: クラウドスタッフィング AIデモ No.01 「CSV加工の完全自動化」
- 最終更新日: 2026-04-23

---

## 1. 設計の目的と範囲

### 1.1 このドキュメントの位置付け
要件定義書（`01_requirements.md`）で定義された「勤怠CSV自動整形CLI」の **構造設計（How）** を中粒度で示す。派遣元ごとにバラバラな勤怠CSVを、クラウドスタッフィングの標準スキーマに **1コマンドで変換** するCLIを、Python標準ライブラリのみで実装するための設計図を提供する。

### 1.2 要件定義書との対応関係
| 要件ID（要件定義書） | 本設計書の主要対応セクション |
|---|---|
| M1 元データ投入 | §3 `CLIDispatcher`、§6.1 CLIサブコマンド体系 |
| M2 自動フォーマット検出 | §3 `EncodingDetector`、§7.1 判定アルゴリズム |
| M3 ヘッダー表記揺れ自動マッピング | §3 `HeaderInferencer`、§7.2 スコアリング設計 |
| M4 日付・時刻正規化 | §3 `TimesheetNormalizer`、§7.3 日付/時刻パーサ |
| M5 全角半角・空白・記号正規化 | §3 `TimesheetNormalizer`、§7.4 値正規化 |
| M6 整形済CSV出力 | §3 `TimesheetWriter`、§4 データフロー |
| M7 エラーハイライト＋件数照合 | §3 `ReviewCollector` / `BillingReportGenerator`、§7.5 件数カウンタ |
| M8 エラー行ポリシー | §3 `ErrorPolicyApplier`、§7.6 ポリシー分岐 |
| M9 PIIマスキング | §3 `PIIMasker`、§9 プライバシー設計 |
| S1 テンプレート保存 | §3 `TemplateStore`、§5.3 テンプレートJSONスキーマ |
| S2/S3/S4/S5 | §6 インタフェース設計、§10 観測可能性 |

### 1.3 技術仕様書との境界
- **本設計書で決める**: モジュール分割／責務／IF シグネチャ（シグネチャレベル）／ディレクトリ配置／CLI体系／中間データ形式／主要アルゴリズムの疑似コード／エラー分類。
- **次フェーズ（技術仕様書）に委ねる**: 関数ごとのシグネチャ詳細（型ヒント確定値）、同義語辞書の具体全エントリ、編集距離の実装（Levenshtein を自前 or `difflib`）、正規表現の最終形、テストケース一覧、サンプルCSVのバイト列。

---

## 2. アーキテクチャ概要

### 2.1 全体像（テキスト図）

```
┌──────────────────────────────────────────────────────────────────┐
│  Claude Code スラッシュコマンド (.claude/commands/*.md)         │
│   /csv-convert / /csv-save-template / /csv-convert-with-template │
└───────────────────────────┬──────────────────────────────────────┘
                            │ shell invoke
                            ▼
                 ┌──────────────────────┐
                 │  src/main.py         │  ← エントリポイント
                 │  (CLIDispatcher)     │
                 └──────────┬───────────┘
                            │
        ┌───────────────────┼────────────────────────────┐
        ▼                   ▼                            ▼
┌───────────────┐  ┌────────────────────┐  ┌────────────────────┐
│ ConvertFlow   │  │ SaveTemplateFlow   │  │ CleanupFlow (MAY)  │
│ (convert)     │  │ (save-template)    │  │ (cleanup)          │
└──────┬────────┘  └──────────┬─────────┘  └────────────────────┘
       │                      │
       ▼                      ▼
┌─────────────────────────────────────────────┐
│  Pipeline（共通パイプライン）               │
│                                             │
│  TimesheetLoader                            │
│    └─ EncodingDetector → DialectDetector    │
│  HeaderInferencer (同義語辞書＋編集距離)    │
│  TimesheetNormalizer (値正規化)             │
│  ReviewCollector (要確認フラグ収集)         │
│  ErrorPolicyApplier (drop/keep/fail分岐)    │
│  TimesheetWriter (標準スキーマで書き出し)   │
│  BillingReportGenerator (レポート生成)      │
│  PIIMasker (標準出力向けマスク)             │
└─────────────────────────────────────────────┘
       │                      │
       ▼                      ▼
   out/*.csv            templates/*.json
   out/*_report.{md,csv}
```

### 2.2 コンポーネント間の関係（要点）
- `CLIDispatcher` が **サブコマンドごとに Flow クラスを起動** するだけの薄い層。
- `Pipeline` は「読み込み → ヘッダー推論 → 値正規化 → 要確認収集 → ポリシー適用 → 出力 → レポート」の **単方向データフロー**。
- すべてのコンポーネントは **純粋関数に近い形**（入力を受けて結果オブジェクトを返す）で設計し、相互の依存を最小化する。
- PIIマスキングは **副作用として標準出力に出る前段**（差分プレビュー生成時と進捗ログ出力時）にのみ挟む。**ファイル書き出しパスには入らない**。

### 2.3 処理の流れ（ハッピーパス：`convert` サブコマンド）
1. `CLIDispatcher` が `argparse` で引数を解釈し、`ConvertFlow.run(args)` を呼ぶ。
2. Flow入口で **dry-run / 非サンプル入力ガード** を判定（`--dry-run` なら以降の書き出し経路を全停止、`samples/` 外入力は `--allow-non-sample-input` 未指定時に拒否）。
3. `TimesheetLoader.load(path)` が `EncodingDetector` で文字コードを固定順判定し、`DialectDetector` で区切り文字/改行を判定、生行列（`list[list[str]]`）を返す。
4. `HeaderInferencer.infer(raw_headers, template=None)` が標準スキーマ列への対応表（`HeaderMapping`）を返す。
5. `TimesheetNormalizer.normalize(rows, mapping)` が各セルを正規化し、**正規化済み行**と **原値を保持したセル単位の要確認メモ** を返す。
6. `ReviewCollector` が要確認メモを行単位に集約し、`ReviewLedger` を生成（行番号・列名・原値・推定理由）。
7. `ErrorPolicyApplier.apply(rows, ledger, policy)` が `drop / keep / fail` に応じて出力行（keep時は要確認セルに原値を採用）と件数カウンタを確定する。
8. `RowCountValidator.validate(counters, policy)` が件数照合（M7 関係式）を **書き出し前に** 検証。不成立（`RowCountMismatchError`）なら fail-fast し、writer/report を一切起動しない。
9. `policy=fail` かつ `review_rows>0` の場合は **writer のみ停止**し、`BillingReportGenerator` は要確認一覧レポートを出力する（差戻し導線確保）。§4.3・§7.5 も同ルールで統一。ただし **`--dry-run` は全書き出し停止を最優先** とし、`fail` 時のレポート出力もこのガードに従って抑止する（dry-run > fail-report）。
10. それ以外（全ポリシーの正常ケース）は `TimesheetWriter.write(rows, out_path)` が UTF-8 (BOMなし) / LF で整形済CSVを書き出し、続いて `BillingReportGenerator.generate(ledger, counters, format)` が Markdown または CSV でレポートを出力する。dry-runガード時は writer/report とも全停止。
11. `PIIMasker` 経由で件数サマリと Before/After 先頭3行を標準出力に表示。

---

## 3. コンポーネント構成

### 3.1 モジュール一覧

| モジュール（クラス/関数） | 責務 | 主な依存 |
|---|---|---|
| `CLIDispatcher` (`src/main.py`) | サブコマンドの振り分け、引数パース | `argparse` |
| `ConvertFlow` (`src/flows/convert.py`) | `convert` サブコマンドのユースケース | `Pipeline` 一式 |
| `SaveTemplateFlow` (`src/flows/save_template.py`) | `save-template` サブコマンドのユースケース（非対話/対話/外部マッピング） | `HeaderInferencer`, `TemplateStore` |
| `CleanupFlow` (`src/flows/cleanup.py`)（MAY） | `out/` と `samples/tmp_*` の削除 | `pathlib` |
| `TimesheetLoader` (`src/io/loader.py`) | ファイル読み込みと生行列の取得 | `EncodingDetector`, `DialectDetector`, `csv` |
| `EncodingDetector` (`src/io/encoding.py`) | 文字コード判定（BOM→UTF-8 strict→CP932→失敗） | `codecs` |
| `DialectDetector` (`src/io/dialect.py`) | 区切り文字・改行コードの判定（Sniffer失敗時は候補固定順でフォールバック: `,` → `\t` → `;`、改行は `\r\n` → `\n`） | `csv.Sniffer` 薄ラッパ |
| `HeaderInferencer` (`src/mapping/inferencer.py`) | 標準スキーマへのヘッダーマッピング推論 | `SynonymDictionary`, `similarity` |
| `SynonymDictionary` (`src/mapping/synonyms.py`) | 派遣業界語彙の同義語辞書 | 組み込みテーブル |
| `similarity` (`src/mapping/similarity.py`) | 編集距離ベース類似度算出 | 標準 `difflib` もしくは自前 |
| `TimesheetNormalizer` (`src/normalize/timesheet.py`) | 行単位の値正規化を統括 | `DateParser`, `TimeParser`, `NumberParser`, `TextNormalizer` |
| `DateParser` (`src/normalize/date_parser.py`) | 和暦・西暦・数字塊など複数形式を `YYYY-MM-DD` に変換 | `datetime`, `re` |
| `TimeParser` (`src/normalize/time_parser.py`) | `9:0` `9時` `9：00` 等を `HH:MM` に変換、`24:00` 扱い | `re` |
| `NumberParser` (`src/normalize/number_parser.py`) | 時給・休憩の数値抽出（`￥` `円` `,` `分` `時間` の剥ぎ取り） | `re`, `unicodedata` |
| `TextNormalizer` (`src/normalize/text.py`) | 全角半角・空白・記号正規化 | `unicodedata` |
| `ReviewCollector` (`src/quality/review.py`) | 要確認メモを行単位に集約して `ReviewLedger` を生成 | ― |
| `ErrorPolicyApplier` (`src/quality/policy.py`) | `drop/keep/fail` 分岐と件数カウンタ確定 | ― |
| `RowCountValidator` (`src/quality/counters.py`) | M7 関係式検証（fail-fast の判断） | ― |
| `TimesheetWriter` (`src/io/writer.py`) | UTF-8 (BOMなし) / LF で整形済CSVを書き出し | `csv` |
| `BillingReportGenerator` (`src/report/generator.py`) | Markdown / CSV レポート生成 | ― |
| `TemplateStore` (`src/template/store.py`) | `templates/<name>.json` の読み書きと重複チェック | `json`, `pathlib` |
| `MappingFileLoader` (`src/template/mapping_file.py`) | `--mapping-file` 指定時の **JSON ロード限定**（YAMLは非対応） | 標準 `json` |
| `PIIMasker` (`src/security/mask.py`) | 標準出力用のマスク変換（氏名・時給） | ― |
| `BatchRunner` (`src/flows/batch.py`) | `--input-dir` のファイル列挙と逐次実行、継続/fail-fast 制御 | `pathlib`, `ConvertFlow` |

### 3.2 依存関係の向き
- **上位（Flow系）→ 下位（IO / Normalize / Quality / Template / Security）** の一方向。
- ドメインモジュール（Normalize / Quality / Template）は **Flow 層に依存しない**（単体テスト容易化）。
- `PIIMasker` は他モジュールに依存されるが、他モジュールに依存しない（最下流の純関数集約）。

### 3.3 分離の根拠
- **文字コード判定** と **区切り文字判定** を独立（EncodingDetector / DialectDetector）: 要件5章の固定順判定アルゴリズムを単体検証可能にするため。
- **HeaderInferencer** と **TimesheetNormalizer** を分離: 「列の対応付け」と「各セルの値変換」は関心が違い、テンプレート適用時はヘッダー段階で完結できる設計にする。
- **ReviewCollector** と **ErrorPolicyApplier** を分離: 要確認の **収集** とポリシー **適用**（drop/keep/fail）を混ぜない。M8 の挙動マトリクス（§7.6）を policy モジュール側に集約できる。
- **PIIMasker** を独立: ファイル書き出しパスに混入させず、標準出力レイヤでのみ適用する責務境界を明確化（M9 の「生値はファイル内のみ」要件を構造で担保）。
- **BillingReportGenerator** 命名: 派遣運用では勤怠→請求の接続が自然。月次レポート作業を想起させる命名で業務文脈を反映。

### 3.4 主要IF（シグネチャレベル、詳細は技術仕様書）
- `TimesheetLoader.load(path: Path) -> LoadedTimesheet`
  - `LoadedTimesheet`: `{headers: list[str], rows: list[list[str]], encoding: str, dialect: Dialect}`
- `HeaderInferencer.infer(headers: list[str], template: Optional[TemplateMapping]) -> HeaderMapping`
  - `HeaderMapping`: `{canonical_to_source_index: dict[str, int], confidence: dict[str, float], needs_review_columns: list[str], unmapped_columns: list[str]}`
- `TimesheetNormalizer.normalize(rows, mapping) -> NormalizedResult`
  - `NormalizedResult`: `{rows: list[NormalizedRow], review_cells: list[ReviewCell]}`
  - `NormalizedRow`: `{source_row_no: int, cells: dict[str, NormalizedCell]}` — `source_row_no` は **入力ファイル行番号**（ヘッダー=1, データ1行目=2）。`ReviewCell.source_row_no` と同じ採番規則で、擬似関数ではなく構造体フィールドとして明示する。
  - `NormalizedCell`: `{normalized_value: str, raw_value: str, is_review: bool}` — 常に原値と正規化値を両持ちする（M8 `keep` で原値採用を可能にするため）
- **`source_row_no` vs `output_row_no` の分離定義**（R3で確定）
  - `source_row_no`: 入力CSV上の物理行番号。`NormalizedRow` / `ReviewCell` / レポートの「入力側参照列」で使用。
  - `output_row_no`: 出力CSV上の物理行番号（ヘッダー=1, データ1行目=2）。sidecar（§6.3）および `BillingReportGenerator` の「出力側参照列」で使用。
  - **sidecar 列名（固定）**: `output_row_no, source_row_no, has_review, review_columns` の4列とし、運用で混乱しないよう仕様上確定する（`row_no` という曖昧名は使用しない）。
- `ErrorPolicyApplier.apply(result, policy) -> PolicyOutcome`
  - `PolicyOutcome`: `{output_rows, ledger, counters, exit_code_hint}`
  - `keep` ポリシー時は review フラグが立ったセルに限り `raw_value` を採用し、クリーンセルは `normalized_value` を採用する

---

## 4. データフロー

### 4.1 ハッピーパス（convert, drop ポリシー既定）

```
[入力]
  samples/timesheet_202604_haken_a.csv
           │
           ▼
  (EncodingDetector) 先頭3byte=EF BB BF? → no
                    UTF-8 strict デコード → success
           │
           ▼
  (DialectDetector) 区切り文字=',', 改行='\r\n'
           │
           ▼
  (TimesheetLoader) raw_headers=["時給","終業","始業","勤務日","氏名","社員コード","休憩（分）"]
                    raw_rows=[["￥1,500","18:00","9:00","令和8年4月23日","山田　太郎","EMP001","60"], ...]
           │
           ▼
  (HeaderInferencer) mapping =
    { "hourly_wage":0, "end_time":1, "start_time":2, "work_date":3,
      "name":4, "employee_id":5, "break_minutes":6 }
    confidence = {hourly_wage:1.0, ..., break_minutes:0.92}
           │
           ▼
  (TimesheetNormalizer)
    row0 → {"employee_id":"EMP001","name":"山田 太郎",
            "work_date":"2026-04-23","start_time":"09:00",
            "end_time":"18:00","break_minutes":"60","hourly_wage":"1500"}
    review_cells=[]
           │
           ▼
  (ReviewCollector) ledger = 空（全行クリーン）
           │
           ▼
  (ErrorPolicyApplier, policy=drop)
    output_rows = 2, dropped_rows = 0, review_rows = 0
    input_rows = output_rows + dropped_rows → 2 = 2 + 0 ✓
           │
           ▼
  (TimesheetWriter) out/timesheet_202604_haken_a.csv を UTF-8/LF で書き出し
  (BillingReportGenerator) out/timesheet_202604_haken_a_report.md を書き出し
  (PIIMasker) 標準出力に "山***" / "****" でサマリ表示
```

### 4.2 中間データの形式

| データ | 形式 | 生成元 | 消費先 |
|---|---|---|---|
| `LoadedTimesheet` | dataclass | `TimesheetLoader` | `HeaderInferencer`, `TimesheetNormalizer` |
| `HeaderMapping` | dataclass | `HeaderInferencer` | `TimesheetNormalizer`, `TemplateStore` |
| `ReviewCell` | dataclass (`row_no, col, raw_value, reason`) | `TimesheetNormalizer` | `ReviewCollector` |
| `ReviewLedger` | list[ReviewCell] + 行番号集合 | `ReviewCollector` | `ErrorPolicyApplier`, `BillingReportGenerator` |
| `Counters` | dataclass (`input/output/dropped/review`) | `ErrorPolicyApplier` | `RowCountValidator`, `BillingReportGenerator` |
| `PolicyOutcome` | dataclass | `ErrorPolicyApplier` | `TimesheetWriter`, `CLIDispatcher`（終了コード決定） |

### 4.3 エラー時の分岐フロー

```
[EncodingDetector 失敗]
  → stderr: "未対応の文字コード: UTF-8/CP932 いずれでもデコードできません"
  → ファイル未出力 / 非ゼロ終了

[HeaderInferencer: REQUIRED 列のいずれかが未確定 / 全列未マッピング / 空CSV（REQUIRED充足不能）]
  → Fatal: stderr に未確定 REQUIRED 列名を列挙（空CSVの場合は「data row = 0, REQUIRED unsatisfied」旨を出力）
  → writer/report とも起動しない
  → 非ゼロ終了（exit=1）
  ※ 任意列（break_minutes）のみ未確定なら既定値で補完して続行可（警告ログ）。
  ※ §8.1 と一貫し、「全列未マッピング」「空CSV」も REQUIRED 未確定の特殊形として Fatal 扱い。

[ErrorPolicyApplier policy=fail, review_rows>0]
  → TimesheetWriter スキップ（整形済CSV 非出力）
  → BillingReportGenerator は要確認一覧レポートを出力（差戻し導線確保）
  → CLIは非ゼロ終了（exit=1）

[RowCountValidator 関係式不成立（RowCountMismatchError）]
  → fail-fast: writer/report とも起動しない（書き出し前に中断）
  → stderr: "件数照合失敗: input=X, output=Y, dropped=Z"
  → 非ゼロ終了（exit=1）
```

---

## 5. データモデル / スキーマ

### 5.1 標準スキーマ（canonical schema）
要件定義書§7 と完全一致。実装上は `src/schema/canonical.py` に定数として保持。

```python
CANONICAL_COLUMNS = [
    "employee_id", "name", "work_date",
    "start_time", "end_time", "break_minutes", "hourly_wage",
]
REQUIRED_COLUMNS = {"employee_id", "name", "work_date",
                    "start_time", "end_time", "hourly_wage"}
OPTIONAL_WITH_DEFAULT = {"break_minutes": "0"}
```

### 5.2 要確認メモ（ReviewCell）のデータモデル
```python
@dataclass
class ReviewCell:
    source_row_no: int  # 入力ファイル行番号（ヘッダー=1, データ1行目=2）
    column: str         # 標準スキーマ列名
    raw_value: str      # 原値
    reason: str         # 推定理由（ユーザー可読文）
    # 出力行番号は ErrorPolicyApplier 後に BillingReportGenerator / sidecar 側で
    # 別フィールド `output_row_no` として付与する（drop/keep でずれるため別管理）。
```

### 5.3 テンプレートJSONスキーマ（`templates/<name>.json`）

```json
{
  "schema_version": 1,
  "name": "haken_a",
  "created_at": "2026-04-23T10:30:00+09:00",
  "source_hint": "timesheet_202604_haken_a.csv",
  "encoding": "utf-8",
  "dialect": { "delimiter": ",", "lineterminator": "\r\n" },
  "header_mapping": [
    { "canonical": "employee_id", "source": "社員コード",
      "source_index": 5, "confidence": 1.00, "needs_review": false },
    { "canonical": "name", "source": "氏名",
      "source_index": 4, "confidence": 1.00, "needs_review": false },
    { "canonical": "work_date", "source": "勤務日",
      "source_index": 3, "confidence": 1.00, "needs_review": false },
    { "canonical": "start_time", "source": "始業",
      "source_index": 2, "confidence": 1.00, "needs_review": false },
    { "canonical": "end_time", "source": "終業",
      "source_index": 1, "confidence": 1.00, "needs_review": false },
    { "canonical": "break_minutes", "source": "休憩（分）",
      "source_index": 6, "confidence": 0.92, "needs_review": false },
    { "canonical": "hourly_wage", "source": "時給",
      "source_index": 0, "confidence": 1.00, "needs_review": false }
  ],
  "unmapped_source_headers": []
}
```

- 命名規則違反（全角・日本語）は `TemplateStore.save` が保存前に弾く。
- `--force` なしで上書きすると `FileExistsError` 相当で非ゼロ終了。

### 5.4 ファイル配置と命名規則

| パス | 用途 | Git管理 |
|---|---|---|
| `src/` | 実装コード | 対象 |
| `samples/` | デモ用ダミーCSV（`timesheet_YYYYMM_haken_*.csv` 命名） | 対象（ただし個人情報ゼロ） |
| `samples/tmp_*` | 一時生成物（`cleanup` 対象） | 対象外 |
| `templates/` | テンプレートJSON | 対象 |
| `mappings/` | `--mapping-file` 用の外部マッピング（**JSON 限定**、`.json`） | 任意 |
| `out/` | 整形済CSV・レポート（既定出力先） | 対象外（`.gitignore`） |
| `.claude/commands/` | Claude Code スラッシュコマンド定義 | 対象 |

---

## 6. インタフェース設計

### 6.1 CLIサブコマンド体系

```
python src/main.py <subcommand> [options]

subcommands:
  convert          単発 or ディレクトリ一括変換
  save-template    テンプレートJSON生成（非対話/対話/外部マッピング指定）
  cleanup          out/ と samples/tmp_* の削除（MAY）
```

#### 6.1.1 `convert` サブコマンド

| オプション | 型 | 既定 | 説明 |
|---|---|---|---|
| `--input` | path | ― | 入力CSVファイル（`--input-dir` と排他） |
| `--input-dir` | path | ― | 入力ディレクトリ（`*.csv` を一括） |
| `--output` | path | `out/<input_basename>.csv` | 単一出力先 |
| `--output-dir` | path | `out/` | バッチ出力先 |
| `--template` | str | ― | 適用テンプレート名（`templates/<name>.json` を読む） |
| `--error-policy` | `drop/keep/fail` | `drop` | 要確認行の扱い |
| `--report-format` | `md/csv` | `md` | レポート出力形式 |
| `--dry-run` | flag | off | **Flow入口で writer/report/template 書き出しを全停止**。件数＋先頭3行のみ標準出力に表示 |
| `--fail-fast` | flag | off | バッチ失敗時に即停止（未指定時は継続がデフォルト。旧 `--continue-on-error` は廃止済み、本設計では `--fail-fast` 前提で記述する） |
| `--allow-external-output` | flag | off | `out/` 外への書き出しを許可（M9: サイレント越境防止。未指定時は `out/` 外の `--output`/`--output-dir` を即エラー終了） |
| `--allow-non-sample-input` | flag | off | `samples/` 外のファイル/ディレクトリを入力として許可（未指定時は拒否、M9実データ投入禁止の技術的ガード） |
| `--verbose` | flag | off | デバッグ用ログ |

- **dry-runガード**: Flow入口で `dry_run=True` なら `TimesheetWriter` / `BillingReportGenerator` / `TemplateStore.save` の実書き出し呼び出しを停止する共通ガードを適用する（個別モジュールで分散判定しない）。
- **非サンプル入力ガード**: `ConvertFlow` / `SaveTemplateFlow` 冒頭で入力パスが `samples/` 配下か判定し、外かつ `--allow-non-sample-input` 未指定なら即エラー終了（stderr: `input must reside under samples/ unless --allow-non-sample-input is given`）。
- **CLI 無効組合せ（argparse 排他グループで担保）**:

  | 組合せ | 判定 | 理由 |
  |---|---|---|
  | `--input` と `--input-dir` | 排他（必須いずれか1つ） | 単発とバッチは別モード |
  | `--input` と `--output-dir` | 警告（`--output` 推奨） | 単発なら `--output` の方が明確 |
  | `--input-dir` と `--output` | **エラー** | バッチは複数出力のため単一 `--output` と矛盾 |
  | `--dry-run` と `--allow-external-output` | 警告 | dry-runなら書き出しが走らずフラグが無意味 |
  | `--template` と `--mapping-file`（save-template側） | — | `convert` では `--template` のみ、`save-template` では `--mapping-file` のみ |

#### 6.1.2 `save-template` サブコマンド

| オプション | 型 | 既定 | 説明 |
|---|---|---|---|
| `--input` | path | 必須 | 推論対象CSV |
| `--name` | str | 必須 | テンプレート名（snake_case 半角英数字＋`_`） |
| `--interactive` | flag | off | 対話式で1列ずつ採否確認 |
| `--mapping-file` | path | ― | 外部マッピング **JSON**（`.json`）を正として採用。YAMLは非対応。 |
| `--force` | flag | off | 既存テンプレート上書き許可 |

- 既定モードでは M3 決定規則（辞書 > 編集距離 > 左側優先）に従い自動採用し、`needs_review=true` を JSON に残す。
- `--interactive` と `--mapping-file` の同時指定は不可（エラー終了）。

#### 6.1.3 `cleanup` サブコマンド（MAY）

| オプション | 型 | 既定 | 説明 |
|---|---|---|---|
| `--dry-run` | flag | off | 削除対象を列挙するだけで削除しない |

### 6.2 終了コード規約

| コード | 条件 |
|---|---|
| 0 | 全成功（または `fail` ポリシーで `review_rows=0`） |
| 2 | バッチで一部失敗（`--fail-fast` 未指定時の継続完了、MAY実装） |
| 1 | 致命的エラー or `fail-fast` or `fail` ポリシーで `review_rows>0` or 件数照合失敗 |

> MUST は「全成功=0 / それ以外=非ゼロ」のみ。2 分岐は MAY。

### 6.3 ファイルI/O規約
- **読み込み対象**: `--input` または `--input-dir` 配下の `*.csv` のみ（**拡張子は大文字小文字非依存**。`.CSV`, `.Csv` も受理）。`*.tsv` や拡張子なしは無視（警告ログ）。
- **書き込み対象**: 既定は `out/` 配下のみ。`--output` / `--output-dir` で `out/` 外を指すには **`--allow-external-output` フラグを明示必須**（サイレント越境なし、M9 担保）。
- **レポートファイル名**: `<input_basename>_report.md`（CSV形式時は `.csv`）を `--output-dir` と同じディレクトリに生成。
- **sidecar（`keep` ポリシー時）**: `<input_basename>_needs_review.csv` を出力先ディレクトリに生成し、**列は `output_row_no, source_row_no, has_review, review_columns` の4列固定**（§3.4 で定義）。`output_row_no` は整形済CSV上の行番号、`source_row_no` は入力CSV上の行番号に対応。整形済CSV本体には要確認フラグ列を追加しない（canonical 7列固定）。
- **テンプレート**: `templates/<name>.json` 固定。別パスへの保存は非対応。

### 6.4 Claude Code スラッシュコマンド
`.claude/commands/` 配下に以下のMarkdownを配置し、CLIを自然言語風に叩ける。

- `csv-convert.md` → `python src/main.py convert --input $1`
- `csv-save-template.md` → `python src/main.py save-template --input $1 --name $2`
- `csv-convert-with-template.md` → `python src/main.py convert --input $1 --template $2`
- `csv-batch.md` → `python src/main.py convert --input-dir $1`

---

## 7. アルゴリズム設計

### 7.1 文字コード判定（EncodingDetector）

```
function detect_encoding(path):
    bytes = read_bytes(path)                  # ★ファイル全バイトを判定対象に使う
    if bytes[:3] == b"\xEF\xBB\xBF":
        return "utf-8-sig"
    try:
        bytes.decode("utf-8", errors="strict"); return "utf-8"
    except UnicodeDecodeError: pass
    try:
        bytes.decode("cp932", errors="strict"); return "cp932"
    except UnicodeDecodeError: pass
    raise UnsupportedEncodingError
```

- 要件定義§5の「UTF-8 strict 優先で曖昧ケース一意化」をそのまま実装。
- **判定確定は常に全バイトで行う**（末尾まで strict デコードが通らなければ UTF-8 と断定しない）。1MB先読みなどの部分読みは判定ロジックには使わない。
- 非機能要件（10万行上限）に対しては、ストリーム判定/Bloomバッファなどの **性能最適化は技術仕様書に委ねる**（判定結果が全バイト判定と完全同値になることを最適化の前提条件とする）。

### 7.2 ヘッダー推論（HeaderInferencer）

#### 同義語辞書（SynonymDictionary、抜粋）
```python
SYNONYMS = {
  "employee_id":  ["従業員id","社員コード","スタッフno","スタッフコード",
                   "従業員番号","社員番号","従業員コード"],
  "name":         ["氏名","名前","スタッフ名","従業員名","ﾅﾏｴ"],
  "work_date":    ["勤務日","日付","出勤日","作業日"],
  "start_time":   ["始業","開始","出勤時刻","開始時刻","始業時刻"],
  "end_time":     ["終業","終了","退勤時刻","終了時刻","終業時刻"],
  "break_minutes":["休憩","休憩時間","休憩（分）","休憩分"],
  "hourly_wage":  ["時給","時間給","単価","時給単価"],
}
```
- 辞書キーは **正規化後（全角→半角・小文字化・記号除去）** で比較。
- 完全辞書は技術仕様書で確定（派遣業界語彙を幅広くカバー）。

#### スコアリング（疑似コード）
```
function infer(headers):
    result = {}
    for canonical in CANONICAL_COLUMNS:
        candidates = []
        for i, h in enumerate(headers):
            norm = normalize_text(h)  # 全角→半角, 小文字, 記号除去
            if norm in SYNONYMS[canonical]:
                candidates.append({idx:i, score:1.0, via:"dict"})
            else:
                score = max(ratio(norm, s) for s in SYNONYMS[canonical])
                candidates.append({idx:i, score:score, via:"edit"})
        best = select_best(candidates,
                 priority=["dict","edit_distance_min","leftmost"])
        if best.score >= 0.80: confirm(canonical, best)
        elif best.score >= 0.60: mark_needs_review(canonical, best)
        else: mark_unmapped(canonical)
    enforce_uniqueness(result)   # ★後述の一意性制約
    return HeaderMapping(...)
```

- `ratio()` は `difflib.SequenceMatcher.ratio()` を想定（標準ライブラリ）。
- `select_best` のタイブレーク: ①辞書ヒット > ②編集距離小 > ③列インデックス小。

#### 一意性制約（conflict resolution）

- **1つの入力列は最大1つの canonical にしか割当てられない**（1対多マッピング禁止）。
- 複数の canonical が同一の入力列を「確定」として選んだ場合は、以下を競合扱いとする:
  - スコア最上位1件のみ `confirmed`、残りは `needs_review` にダウングレードし、`needs_review_columns` に記録。
  - スコアが完全同値のときはタイブレーク（辞書 > 編集距離小 > 列インデックス小）で確定対象を選ぶ。
- 逆に1つの canonical が複数候補を持つ場合は、従来どおりスコア最上位を採用。
- この制約違反を **設計で塞ぐ** ことで、「氏名」列が `name` と `employee_id` の両方に誤マッピングされるケースを防ぐ。

### 7.3 日付パーサ（DateParser）
優先順に以下パターンを正規表現で試行。

| 優先度 | パターン | 例 |
|---|---|---|
| 1 | `YYYY-MM-DD` | `2026-04-23` |
| 2 | `YYYY/MM/DD` または `YYYY/M/D` | `2026/4/23` |
| 3 | 令和漢字: `令和(\d+)年(\d+)月(\d+)日` | `令和8年4月23日` |
| 4 | 略記: `R(\d+)\.(\d+)\.(\d+)` | `R8.4.23` |
| 5 | 数字塊: `^\d{8}$` | `20260423` |

- 令和→西暦: 2018 + 令和年（令和1年=2019）。
- 月が 1-12 外、日が 1-31 外または存在しない日付は **要確認**（例: `令和8年13月5日`）。
- `datetime.date(y, m, d)` で実在性を最終検証。

### 7.4 時刻パーサ（TimeParser）
| パターン | 例 |
|---|---|
| `H:MM` / `HH:MM` | `9:00`, `18:30` |
| `H時MM分` | `9時30分` |
| `H時` | `9時` → `09:00` |
| `HH：MM`（全角コロン） | `9：00` |

- 全角数字・全角コロンは事前に `unicodedata.normalize("NFKC", s)` で半角化。
- `24:00` は受け入れるが要確認フラグ。
- `end_time < start_time` は正規化成功後の後処理で **要確認**（日またぎ自動補正はしない）。

### 7.5 件数カウンタ（RowCountValidator）

```python
@dataclass
class Counters:
    input_rows: int
    output_rows: int
    dropped_rows: int
    review_rows: int

class RowCountMismatchError(Exception): ...
class FailPolicyHalt(Exception): ...

def validate(counters, policy):
    # ★明示例外で判定（assert は使わない。-O 実行時に無効化されるため）
    if policy == "drop":
        if counters.input_rows != counters.output_rows + counters.dropped_rows:
            raise RowCountMismatchError(
                f"drop: input={counters.input_rows} != output+dropped="
                f"{counters.output_rows + counters.dropped_rows}")
        if counters.dropped_rows < counters.review_rows:
            raise RowCountMismatchError(
                f"drop: dropped={counters.dropped_rows} < review={counters.review_rows}")
    elif policy == "keep":
        if counters.input_rows != counters.output_rows:
            raise RowCountMismatchError(
                f"keep: input={counters.input_rows} != output={counters.output_rows}")
        if counters.dropped_rows != 0:
            raise RowCountMismatchError(f"keep: dropped must be 0")
    elif policy == "fail":
        if counters.review_rows > 0:
            raise FailPolicyHalt()  # 出力せず非ゼロ終了
        # review_rows == 0 でも件数整合は必ず検証する（静かな不整合を許容しない）
        if counters.input_rows != counters.output_rows:
            raise RowCountMismatchError(
                f"fail: input={counters.input_rows} != output={counters.output_rows}")
        if counters.dropped_rows != 0:
            raise RowCountMismatchError(
                f"fail: dropped must be 0 (got {counters.dropped_rows})")
```

- 例外発生時は **fail-fast**（stderr＋非ゼロ終了＋出力ファイル未生成）。
- **順序**: `ErrorPolicyApplier` → `RowCountValidator.validate` → 成功時に `TimesheetWriter` / `BillingReportGenerator` を起動。書き出し後検証は行わない（書き出しが走ってから不整合を発見する矛盾を回避）。
- **fail ポリシー例外**: `policy=fail` かつ `review_rows>0`（`FailPolicyHalt`）の場合は、`TimesheetWriter` は停止するが `BillingReportGenerator` は要確認一覧レポートを生成する（再提出導線のため）。`RowCountMismatchError` の場合は writer/report とも停止する。
- `assert` は Python の `-O` オプション起動時に無効化され fail-fast が静かに失われるため、本検証では使用しない。

### 7.6 ポリシー分岐（ErrorPolicyApplier）

入力は §3.4 の `NormalizedResult`（各セルが `NormalizedCell{normalized_value, raw_value, is_review}` を持つ）。ポリシーごとに **どちらの値を出力するか** を決定する。

```
function apply(normalized_result, ledger, policy):
    # row.source_row_no は入力ファイル行番号（NormalizedRow のフィールド、§3.4）。
    # row.cells は {col: NormalizedCell} の dict。
    review_source_row_nos = unique_source_row_nos(ledger)
    review_rows = len(review_source_row_nos)
    match policy:
        case "drop":
            # 要確認行はまるごと落とす。出力行は normalized_value を採用。
            output = [
                {col: cell.normalized_value for col, cell in row.cells.items()}
                for row in normalized_result.rows
                if row.source_row_no not in review_source_row_nos
            ]
            dropped = review_rows
        case "keep":
            # 全行出力。ただし is_review が立ったセルは ★raw_value を採用（原値保持）。
            # クリーンセルは normalized_value。
            # ★出力CSVは常に canonical 7列固定（§5.1）とし、
            #   要確認フラグは CSV 列には追加しない（スキーマ衝突回避）。
            #   行単位の要確認フラグは sidecar（`<basename>_needs_review.csv`、
            #   output_row_no / source_row_no 併記）および レポートで保持する
            #   （§6.3 参照）。
            output = [
                {col: (cell.raw_value if cell.is_review else cell.normalized_value)
                 for col, cell in row.cells.items()}
                for row in normalized_result.rows
            ]
            needs_review_source_row_nos = [
                row.source_row_no for row in normalized_result.rows
                if row.source_row_no in review_source_row_nos
            ]
            dropped = 0
        case "fail":
            if review_rows > 0: return Halt(exit_code=1)
            output = [
                {col: cell.normalized_value for col, cell in row.cells.items()}
                for row in normalized_result.rows
            ]
            dropped = 0
    return PolicyOutcome(output, Counters(
        input_rows=len(normalized_result.rows),
        output_rows=len(output),
        dropped_rows=dropped,
        review_rows=review_rows))
```

- **`keep` の原値保持が M8 の本質要件**。「正規化に失敗したセルを勝手に書き換えた値で出力する」状況を構造で防ぐ。
- ユーザーは `keep` 出力CSVの `__needs_review=true` 行を目視確認し、原値のまま差し戻し判断ができる。

### 7.7 PIIマスキング（PIIMasker）

```python
def mask_name(name: str) -> str:
    if not name: return ""
    return name[0] + "***"  # 先頭1文字＋"***"（空白・非日本語名も同ルール）

def mask_wage(wage: str) -> str:
    if not wage: return ""
    return "****"  # ★固定長 **** に置換（桁数も漏らさない）
```

- 適用場所: 差分プレビュー（S2）、進捗ログ（S5）、件数サマリ内の代表値表示。
- **適用しない場所**: 整形済CSV、レポートファイル、テンプレートJSON。
- `mask_wage` は桁数を保持する設計を見送り、**全面 `****` 固定** に仕様固定（数字のみ `*` 化など可変ルールは誤解を招くため）。

### 7.8 計算例（要件§10.4パターンCの設計観点再定義）

| 行 | 列 | 原値 | 正規化結果 | 判定 |
|---|---|---|---|---|
| 2 | すべて | … | 正常 | クリーン |
| 3 | work_date | `令和8年13月5日` | DateParser失敗（月13不正） | 要確認 |
| 4 | name | (空) | REQUIRED違反 | 要確認 |
| 4 | end_time | `08:00` | `start=09:00 > end=08:00` | 要確認 |
| 5 | break_minutes | (空) | 任意列 → `0` 補完 | クリーン |
| 5 | hourly_wage | `abc円` | NumberParser失敗 | 要確認 |

- 結果（drop 既定）: `input=4, output=1, dropped=3, review=3`。関係式 `4 = 1+3` ✓ / `3 ≧ 3` ✓。

---

## 8. エラーハンドリング・異常系設計

### 8.1 エラー分類

| レベル | 例 | CLI挙動 | 出力への影響 |
|---|---|---|---|
| **致命（Fatal）** | ファイル未存在 / 文字コード判定全滅 / 件数照合失敗 / `fail` ポリシー `review>0` / **全列未マッピング**（REQUIRED列が1つも確定しない） / **空CSV**（データ行0件で REQUIRED が充足不能） | 非ゼロ終了 + stderr + ファイル未出力 | 出力なし |
| **警告（Warning）** | `--force` なし上書き回避 / 任意列のみ未マッピング / `.csv` 以外のファイルスキップ | 続行（スキップまたは既定値補完） | 該当ファイル未更新 |
| **情報（Info）** | 要確認セルあり（policy に従い処理継続） | 正常継続 | レポートに記録 |

- **設計ポリシー**: REQUIRED列が `unmapped_columns` に残存する状態（全列未マッピング／空CSV はその特殊形）は **常に Fatal（exit=1）** として扱い、§4.3・§8.4 と同一ルールで一本化する。「成功したように見えて実質未達」という状態を設計で塞ぐ。
- **`--allow-empty` は現時点では提供しない**（最小実装方針）。将来空CSV許容が必要になった場合は明示フラグ化し、既定は Fatal のまま据え置く。

### 8.2 エラー時の終了コード

| 状況 | 終了コード |
|---|---|
| 全成功 | 0 |
| fail ポリシーで review > 0 | 1 |
| 件数照合失敗（fail-fast） | 1 |
| 文字コード判定失敗 | 1 |
| バッチで一部失敗（継続完了） | 2（MAY） |
| バッチ fail-fast | 1 |
| 入力ファイル不存在 | 1 |
| `save-template` で既存テンプレ上書き拒否 | 1 |

### 8.3 stderr への出力フォーマット
```
[ERROR] <category>: <message>
        hint: <recovery action>
```
例:
```
[ERROR] encoding: UTF-8/CP932 いずれでもデコードできませんでした
        hint: ファイルの文字コードを UTF-8 にしてから再実行してください
```

### 8.4 回復可能 / 不可能の判断基準

- **回復可能**（続行）: ヘッダー一部未マッピング（ただし REQUIRED 列が全て確定している場合のみ） / セル単位の要確認 / 任意列の欠損 / バッチ内の1ファイル失敗（`--fail-fast` 未指定時）。
- **回復不可能**（非ゼロ終了）: 文字コード判定全滅 / **REQUIRED 列未確定**（§5.1 の REQUIRED_COLUMNS のいずれかが `unmapped_columns` に残存） / 件数照合不成立 / ファイル系例外（I/O エラー、権限不足）/ `fail` ポリシーで要確認発生 / `save-template` の命名規則違反 / 非サンプル入力ガード違反 / symlink入力拒否。

---

## 9. セキュリティ・プライバシー設計

### 9.1 PIIマスキングの適用範囲

| 出力先 | マスク適用 | 理由 |
|---|---|---|
| 標準出力（件数サマリ・進捗ログ・差分プレビュー） | **適用** | セミナー画面録画・ログ共有で漏洩しやすい |
| stderr（エラー詳細） | **適用**（該当値が含まれる場合のみ） | 同上 |
| 整形済CSV（`out/*.csv`） | **非適用**（生値） | M6 取り込みのため生値必須 |
| レポート（`out/*_report.*`） | **非適用**（生値） | 差戻し判断のため生値必須 |
| テンプレートJSON（`templates/*.json`） | 値は格納しない（ヘッダー対応のみ） | 仕様上データ値を保持しない |

### 9.2 ファイル出力先の制限
- 既定は `out/` 配下のみ。
- `--output` / `--output-dir` で `out/` 外を指す場合は **`--allow-external-output` フラグ必須**（未指定時は即エラー終了）。ガード判定は `Path.resolve(strict=False)` で実パスに正規化してから行い、`out/` の実パス配下かを比較する。
- `.gitignore` で `out/` を Git 追跡対象外にし、誤コミットを防止。

### 9.3 実データ投入禁止の担保手段

- **技術的ガード（MUST）**: `ConvertFlow` / `SaveTemplateFlow` 入口で入力パスを **`Path.resolve(strict=True)` により実パスに正規化** した上で、リポジトリ直下 `samples/` の **実パス配下**（`resolved_samples_root` を基準にした `is_relative_to` 判定）であるかを比較する。判定は **「resolve前後の文字列差」では行わない**（相対パスや `.` を含むパス指定でも差分が出るため誤拒否の原因になる）。
- **symlink 拒否の明示実装**: resolve 後に、入力パスを構成する各要素（入力ファイル＋その全親ディレクトリを `samples/` 実パスまで遡った範囲）を対象に `Path.lstat()` でリンク判定を行い、**いずれかが symlink の場合は拒否**（非ゼロ終了）。これにより `samples/real_link.csv`（samples配下のsymlinkが外部実体を指す）や `samples/sub` が外部ディレクトリへのリンクになっているケースを両方塞ぐ。
- `samples/` 外の場合は `--allow-non-sample-input` が明示指定されていない限り即エラー終了する（stderr: `input must reside under samples/ unless --allow-non-sample-input is given`、非ゼロ終了）。
- `--input-dir` も同様にディレクトリ自体の実パスが `samples/` 配下かを判定（上記 lstat ベースの symlink 拒否も同ルールで適用）。
- **バッチ時の各ファイル検査（MUST）**: `BatchRunner` が列挙した `*.csv` ファイル **一つずつに対して** 上記の実パス正規化＋各要素 symlink 判定を再適用する。ディレクトリ判定だけに依存すると、配下 CSV が外部実体への symlink の場合に迂回可能になるため、**個別ファイル単位のガードを必ず通す**。
- README 冒頭に **「本CLIはデモ用モックのため、実勤怠データを投入しないこと」** を明示（運用面の重ね掛け）。
- `samples/` 配下は個人情報を含まないダミーのみ配置（命名は業務文脈寄せだが値は完全架空）。
- `--allow-non-sample-input` 指定時は `--verbose` 相当の注意ログを stderr に出し、責任をユーザー側に明示的に移す。

### 9.4 免責表示
- `python src/main.py --version` で「このCLIはセミナーデモ用であり、実運用グレードのバリデーション・監査ログ・権限制御は実装されていない」旨を表示。
- README 冒頭の免責文（要件§7の制約をそのまま転記）。

---

## 10. 観測可能性・運用設計

### 10.1 ログ出力方針

| レベル | 出力先 | 内容 |
|---|---|---|
| Info（既定） | stdout | 進捗ログ（S5）、件数サマリ、Before/After 先頭3行 |
| Warning | stderr | 全列未マッピング、上書き拒否、軽微な異常 |
| Error | stderr | 致命エラー（§8.1） |
| Debug（`--verbose`） | stderr | 各ステップの経過、推論スコア詳細、処理時間 |

- フォーマット: `[<LEVEL>] <component>: <message>`
- ログライブラリ: `logging` 標準モジュールを最小構成で利用。ファイル出力は行わない（デモ用途）。

### 10.2 進捗ログ（S5）のフォーマット
```
[1/5] samples/timesheet_202604_haken_a.csv → out/timesheet_202604_haken_a.csv (input=10 output=9 dropped=1 review=1)
[2/5] samples/timesheet_202604_haken_b.csv → out/timesheet_202604_haken_b.csv (input=8 output=8 dropped=0 review=0)
...
```

- **バッチ列挙順（MUST、デモ再現性担保）**: `BatchRunner` が `--input-dir` 配下の `*.csv` を列挙する際は、`sorted()` によるファイル名昇順（OSロケール非依存のコードポイント順）で確定する。OS依存の列挙順（`os.scandir` の順序等）に依存しないことをセミナーデモ・テストで保証する。

### 10.3 差分プレビュー（S2）の見せ方（セミナー整合）

```
=== Before (masked) ===
時給,終業,始業,勤務日,氏名,社員コード,休憩（分）
****,18:00,9:00,令和8年4月23日,山***,EMP001,60
...

=== After ===
employee_id,name,work_date,start_time,end_time,break_minutes,hourly_wage
EMP001,山***,2026-04-23,09:00,18:00,60,****
...

=== Summary ===
input=2 output=2 dropped=0 review=0 (policy=drop)
関係式: input = output + dropped → 2 = 2 + 0 ✓
```

- デモ時間（約4分）に収まるよう、各メッセージは1行で完結させる。
- S6章のデモシナリオ「3. コマンド実行20秒」「5. エラーハイライト30秒」と整合。

### 10.4 将来拡張への接続点

| 将来拡張項目（要件9章） | 設計上の接続点 |
|---|---|
| 契約CSV・請求集計CSV対応 | `CANONICAL_COLUMNS` を `src/schema/canonical_*.py` で複数種持ち、`--schema contract` 等のオプション追加で切替可能な構造 |
| 36協定・抵触日判定 | `src/quality/compliance.py` を新設し、`ErrorPolicyApplier` の後段に挟むパイプライン拡張点を予約 |
| LLM API連携 | `HeaderInferencer` をインタフェース化（`InferencerProtocol`）し、`RuleBasedInferencer` と将来の `LLMInferencer` を差し替え可能に |
| HTMLレポート（X4） | `BillingReportGenerator` を formatter パターンにし、`md`/`csv` に加え `html` を追加可能に |
| SaaS本体取り込み | `TimesheetWriter` の後段に post-hook を設ける構造（現状は未配線） |

### 10.5 デモ後クリーンアップ運用
- 推奨: `python src/main.py cleanup`（`--dry-run` で事前確認）。
- フォールバック: README の `rm -rf out/ samples/tmp_*` を併記。

---

## 付録A. 想定ディレクトリ構成

```
01_csv-automation/
├── docs/
│   ├── 01_requirements.md       # 要件定義書（既存）
│   ├── 02_design.md             # 本設計書
│   └── context-alignment-notes.md
├── src/
│   ├── main.py                  # CLIDispatcher
│   ├── schema/
│   │   └── canonical.py         # 標準スキーマ定数
│   ├── flows/
│   │   ├── convert.py           # ConvertFlow
│   │   ├── save_template.py     # SaveTemplateFlow
│   │   ├── cleanup.py           # CleanupFlow (MAY)
│   │   └── batch.py             # BatchRunner
│   ├── io/
│   │   ├── loader.py            # TimesheetLoader
│   │   ├── encoding.py          # EncodingDetector
│   │   ├── dialect.py           # DialectDetector
│   │   └── writer.py            # TimesheetWriter
│   ├── mapping/
│   │   ├── inferencer.py        # HeaderInferencer
│   │   ├── synonyms.py          # SynonymDictionary
│   │   └── similarity.py
│   ├── normalize/
│   │   ├── timesheet.py         # TimesheetNormalizer
│   │   ├── date_parser.py
│   │   ├── time_parser.py
│   │   ├── number_parser.py
│   │   └── text.py              # TextNormalizer
│   ├── quality/
│   │   ├── review.py            # ReviewCollector
│   │   ├── policy.py            # ErrorPolicyApplier
│   │   └── counters.py          # RowCountValidator
│   ├── report/
│   │   └── generator.py         # BillingReportGenerator
│   ├── template/
│   │   ├── store.py             # TemplateStore
│   │   └── mapping_file.py      # MappingFileLoader
│   └── security/
│       └── mask.py              # PIIMasker
├── samples/
│   ├── timesheet_202604_haken_a.csv   # パターンA（列順逆転・令和）
│   ├── timesheet_202604_haken_b.csv   # パターンB（BOM+CP932+全角）
│   ├── timesheet_202604_haken_c.csv   # パターンC（エラー混入）
│   └── timesheet_202605_haken_a.csv   # テンプレート再利用デモ用
├── templates/
│   └── .gitkeep                 # 生成物は各デモ実行で作成
├── mappings/                    # --mapping-file オプション用（任意）
├── out/                         # .gitignore で除外
└── .claude/
    └── commands/
        ├── csv-convert.md
        ├── csv-save-template.md
        ├── csv-convert-with-template.md
        └── csv-batch.md
```

## 付録B. 用語定義（要件定義書から継承）

| 用語 | 定義 |
|---|---|
| 標準スキーマ（canonical schema） | `employee_id, name, work_date, start_time, end_time, break_minutes, hourly_wage` の7列で構成される、クラウドスタッフィング取り込み用の正規形 |
| 派遣元企業 | スタッフを派遣する側（入力CSV提供者）。本CLIは操作しない |
| 派遣先企業 | スタッフを受け入れる側（CLI実行主体の候補1） |
| CSチーム | クラウドスタッフィング運用側（CLI実行主体の候補2＋テンプレート管理者） |
| 要確認行 | 変換時に不正・欠損・型違反のセルを1つ以上含む行 |
| エラーポリシー | 要確認行の扱い方針（`drop / keep / fail`） |
| テンプレート | ある派遣元のヘッダーマッピングを再利用可能な形で保存したJSON |
| 件数照合 | `input_rows / output_rows / dropped_rows / review_rows` の関係式検証 |

## 付録C. 設計上の決定記録

### C.1 同義語辞書と編集距離の二段構え
- **選択**: 同義語辞書ヒット=信頼度1.0 で確定、外れた場合のみ編集距離で類似度算出。
- **却下案**: TF-IDF やベクトル類似度。
- **理由**: 派遣業界の表記揺れ（社員コード/従業員ID/スタッフNo.）は **辞書でほぼ解決** でき、辞書外は少数＝編集距離で十分。LLM不使用・標準ライブラリ縛りと整合。

### C.2 `PIIMasker` を独立モジュールにする
- **選択**: 標準出力経路にのみ挟む専用モジュールとして分離。
- **却下案**: 各出力関数内で個別にマスク処理を呼ぶ。
- **理由**: 「ファイルには生値・標準出力にはマスク」という M9 要件を **構造で担保**。後から「ここだけマスク忘れ」が起きにくい。

### C.3 `ErrorPolicyApplier` と `ReviewCollector` の分離
- **選択**: 「要確認の収集」と「ポリシー適用」を別モジュール。
- **却下案**: 一体化して Normalizer 内で完結。
- **理由**: M8 の挙動マトリクス（3ポリシー × dry-run × report-format × batch）を policy 側に集約できる。`fail` ポリシーで書き出さない挙動も、書き出し手前で停止できるこの構造なら自然。

### C.4 テンプレート暗黙保存を禁止
- **選択**: `save-template` サブコマンドでのみ保存。`convert` は保存しない。
- **理由**: 要件定義書 S1 で R3 指摘として明記。テンプレート化は意思決定を伴う操作であり、暗黙生成はデモでも運用でも混乱を招く。

### C.5 `save-template` 既定を非対話に
- **選択**: 既定は非対話で自動採用、`--interactive` で明示対話。
- **却下案**: 既定対話。
- **理由**: セミナーデモでは **止まらずに流れる** ことが価値。対話は「手動確認手段」として別経路で提供（要件 R3 整合）。

### C.6 文字コード判定を自前実装
- **選択**: `codecs` 標準ライブラリで BOM→UTF-8 strict→CP932 の固定順判定。
- **却下案**: `chardet` 等のサードパーティ。
- **理由**: 要件非機能§5で依存なしを明記。固定順で曖昧ケースが一意に決まるため、サードパーティ不要。

### C.7 `BillingReportGenerator` の命名
- **選択**: 一般名の `ReportGenerator` ではなく派遣運用を想起させる `BillingReportGenerator`。
- **理由**: 勤怠→請求の接続は派遣SaaSで自然な業務導線。月次締め・差戻し削減のコンテキストが命名に染み出すことで、セミナー聴衆の業務想起を助ける。
