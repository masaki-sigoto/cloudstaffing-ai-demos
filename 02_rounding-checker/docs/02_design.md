# システム設計書: 端数処理チェッカー

> **プロジェクトコード**: 02_rounding-checker
> **バージョン**: 0.1（初版 / 要件定義書 v0.4 対応）
> **作成日**: 2026-04-23
> **対象**: クラウドスタッフィング（人材派遣管理SaaS）セミナー デモ

---

## 1. 設計の目的と範囲

### 1.1 位置付け
本書は要件定義書 `01_requirements.md` (v0.4) に対し、**どう作るか**を中粒度で定義する設計書である。セミナー実演用モックのため「動けば正義・最小実装」を貫くが、**真理値表（§2.4）・金額計算式（§4.1 M5）・警告発火条件（§4.1 M4）・異常系定義（§7.2）** は要件書の記述を設計レベルでも正とし、揺らぎを一切入れない。

本ツールの主ユーザーは**派遣元の請求担当・給与担当**であり、CS（クラウドスタッフィング）上のルール設定が月次請求・給与の根拠値になるという業務連動を前提として、コンポーネント名・サンプル名・説明文言は派遣管理SaaS文脈に寄せる。

### 1.2 要件定義書との対応

#### 1.2.1 概観マッピング
| 要件 | 設計書での対応セクション |
|---|---|
| 真理値表（要§2.4） | §7.1 丸めエンジン擬似コード |
| M1 ルール設定（YAML） | §3 設定ローダ / §5.2 YAMLスキーマ |
| M2 打刻パターン入力 | §3 打刻パーサ / §4 データフロー |
| M3 シミュレーション結果表示 | §6.1 simulate 出力 / §7.2 Net算出 |
| M4 逆算チェック / 警告 | §7.3 explain / §7.4 警告検出 |
| M5 ルール比較 / 金額計算 | §7.5 比較エンジン / §7.6 金額計算式 |
| 免責表示（非機能 §5） | §6.2 出力ストリーム設計 / §9.4 |
| 実データ禁止 / 匿名ID / `--out` | §9 セキュリティ・プライバシー |
| 異常系（要§7.2） | §8 エラーハンドリング |

#### 1.2.2 要件ID別トレーサビリティ（SHOULD/MAY 採否状態込み / Codex R2 Major 指摘）

| 要件ID | 区分 | 状態 | 参照セクション / 見送り理由 |
|---|---|---|---|
| M1 | MUST | Implemented | §3 / §5.2 |
| M2 | MUST | Implemented | §3 / §4 / §8.2（行単位スキップ継続） |
| M3 | MUST | Implemented | §4.1 / §7.2 |
| M4 | MUST | Implemented | §7.3 / §7.4 |
| M5 | MUST | Implemented | §7.5 / §7.6 |
| 真理値表（要§2.4） | MUST | Implemented | §7.1 |
| 異常系（要§7.2） | MUST | Implemented | §8.2 |
| 免責表示（非機能§5） | MUST | Implemented | §9.4 |
| S1 法定内外別ルール（overtime 適用） | SHOULD | Deferred | §10.3（将来接続点）。MUSTでは YAML `overtime:` を WARN 付き読み捨て（§5.2 / 付録C.3） |
| S2 深夜割増 | SHOULD | Deferred | §10.3（将来接続点） |
| S3 月次集計 | SHOULD | Deferred | §10.3（将来接続点）。MUST では日次結果のみ |
| S4 打刻ベース休憩 | SHOULD | Deferred | §10.3。`break.type=fixed` 以外は exit 2（§5.2） |
| W1 Web UI | MAY | Deferred | §10.3。engine 純関数化で接続点は確保済み |
| W2 既存勤怠CSV取込 | MAY | Deferred | §10.3。`--allow-extra-columns` が将来の橋渡し（§5.3） |
| W4 影響額シミュレーション | MAY | Deferred | §10.3。compare を月跨ぎ打刻で呼べば動く |
| W5 請求/給与同時出力 | MAY | Deferred | §10.3。compare 派生コマンドとして後日追加 |
| 永続ログ（`--log-file`等） | MAY | Rejected | §9.3。セミナーデモ用途では常時 stderr で十分、永続化は PII 再流入リスクを生むため不採用 |
| `validate` を後回し（R1 指摘9） | — | Rejected | §10.4。YAML 読込＋スキーマ検証のみで実装コストが極小、CS オンボーディング支援として残置（R1 履歴参照） |
| `--demo` を全サブコマンドに展開 | — | Rejected | 付録 C.5。7分枠ボトルネックは explain のみであり、設計ノイズ回避のため explain 専用 |

状態語義: **Implemented**（本書で具体設計あり）/ **Deferred**（将来拡張として接続点のみ提示、実装なし）/ **Rejected**（理由明記で採用しない）。

### 1.3 技術仕様書との境界
- **本書で決めること**: モジュール分割、主要インタフェース（関数シグネチャ水準）、データモデル、CLI引数体系、出力ストリーム設計、主要アルゴリズムの擬似コード
- **次フェーズ（技術仕様書 / 実装）に委ねること**: 具体的な型ヒント、例外クラス階層、テストケース網羅、色コード（ANSI）の具体値、ロギングレベルの詳細閾値、依存バージョン固定

---

## 2. アーキテクチャ概要

### 2.1 全体像
単一 Python プロセスで完結する CLI。外部サービス連携なし。標準ライブラリ＋ `PyYAML` のみ。

**実行環境要件**（Codex R3 Major 指摘2）:
- **Python**: `>= 3.10`（`match` 文・`Path.is_relative_to` ・`str | None` 型表記の利用を前提）
- **PyYAML**: `>= 6.0`（`yaml.safe_load` のセキュリティ挙動を前提）
- 起動時に `main.py` 先頭で `sys.version_info` と `yaml.__version__` を検査し、満たさない場合 exit 2 + `[ERROR] requires Python >=3.10 and PyYAML >=6.0` を stderr 出力。環境差分による実装揺らぎを排除する。

```
           ┌─────────────────────────────────────────────────────────┐
           │                   src/main.py (CLI ルーター)              │
           │   argparse: simulate / compare / explain / validate      │
           └──────────────┬──────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬────────────────┐
          ▼               ▼               ▼                ▼
  ┌───────────────┐ ┌──────────────┐ ┌───────────────┐ ┌──────────────┐
  │ config_loader │ │ punch_parser │ │  rounding     │ │  payroll     │
  │ (YAML→Rule)   │ │ (CSV/CLI/STDIN│ │  (丸めエンジン)│ │ (金額計算)   │
  │               │ │  → Punch[])  │ │               │ │              │
  └───────┬───────┘ └──────┬───────┘ └───────┬───────┘ └──────┬───────┘
          │                │                 │                │
          └────────────────┼─────────────────┴────────────────┘
                           ▼
             ┌──────────────────────────────┐
             │      engine (集約処理)        │
             │  simulate / compare / explain│
             └──────────┬───────────────────┘
                        │
          ┌─────────────┼─────────────┬──────────────┐
          ▼             ▼             ▼              ▼
  ┌─────────────┐ ┌────────────┐ ┌─────────────┐ ┌──────────────┐
  │ comparator  │ │ explainer  │ │ warnings    │ │  formatter    │
  │ (2ルール以上 │ │ (逆算説明)  │ │ (警告検出)   │ │ (text/json/   │
  │  の並列計算) │ │            │ │             │ │  csv 出力)    │
  └─────────────┘ └────────────┘ └─────────────┘ └──────┬───────┘
                                                        │
                                         stdout / stderr / --out
```

### 2.2 処理の流れ（ハッピーパス / simulate）
1. CLI ルーターが `simulate` を受信、引数パース
2. `config_loader` が `--rule` の YAML を読み込み `Rule` オブジェクト化
3. `punch_parser` が `--punch` or `--punch-file` or STDIN から `Punch[]` を生成
4. `engine.simulate` が各 `Punch` について `rounding.apply` → Gross算出 → 休憩控除 → Net算出
5. `warnings.check` が適用ルールに対し警告条件 (a)(b) を判定
6. `formatter` が指定フォーマット（text/json/csv）で出力
7. text なら stdout 先頭に免責、json/csv なら stderr 1行に免責（§9.4）

### 2.3 コンポーネント設計方針
- **純関数優先**: 丸め・金額計算・警告判定は I/O を持たない純関数とし、テスト容易性と再現性（非機能要§5 再現性）を担保
- **I/O 境界の集約**: 標準入出力・ファイル I/O は `punch_parser` と `formatter` に閉じ込める
- **サブコマンドは薄い**: `main.py` の各サブコマンドハンドラは 20〜50 行以内。ロジックは `engine` 配下に集約

---

## 3. コンポーネント構成

### 3.1 モジュール一覧

| モジュール | ファイル | 責務 | 主要依存 |
|---|---|---|---|
| CLI ルーター | `src/main.py` | argparse 定義、サブコマンド分岐、exit code 管理 | 全モジュール |
| 設定ローダ | `src/config_loader.py` | YAML → `Rule` オブジェクト変換、スキーマ検証 | `PyYAML` |
| 打刻パーサ | `src/punch_parser.py` | CLI文字列 / CSV / STDIN → `Punch[]` 変換、匿名ID検証、時刻フォーマット検証 | `csv`, `datetime` |
| 丸めエンジン | `src/rounding.py` | 分単位丸め計算、真理値表の実装（ceil/floor/round） | 標準ライブラリのみ |
| 金額計算 | `src/payroll.py` | `支払額 = round_by(時給 × 分 / 60, amount_rounding)` の実装 | 標準ライブラリのみ |
| 警告検出 | `src/warnings_detector.py` | §4.1 M4 警告条件(a)(b) の判定 | なし |
| 説明生成 | `src/explainer.py` | explain サブコマンドの逆算トレース生成、`--demo` 短縮モード | `rounding` |
| 比較エンジン | `src/comparator.py` | 複数ルール並列計算、Net基準の差分算出、共通 amount_rounding 適用 | `rounding`, `payroll` |
| 集約エンジン | `src/engine.py` | simulate / compare / explain の高レベル手続き | 上記全部 |
| 出力フォーマッタ | `src/formatter.py` | text（色付き）/ json / csv 出力、免責表示の出力先制御、`--out` パス検証 | 標準ライブラリのみ |

> モジュール名について: 要件書 §付録のディレクトリ構成には `main.py / rounding.py / explainer.py / comparator.py` のみ明記されているが、責務分離のため **最小追加** で `config_loader / punch_parser / payroll / warnings_detector / engine / formatter` を分ける。要件書付録の構成は「最低限」とみなし、派遣管理SaaSの計算責任境界（打刻入力・丸め・金額）を明確化する意図。

### 3.2 主要インタフェース（擬似シグネチャ）

```python
# config_loader.py
def load_rule(path: str) -> Rule: ...
    # YAMLパース失敗 → RuleLoadError
    # direction が ceil/floor/round 以外 → RuleLoadError
    # amount_rounding が floor/half_up/ceil 以外 → RuleLoadError
    # overtime キー検出時 → WARN を stderr に出力し、ブロックは読み捨て（C.3）

# punch_parser.py
def parse_punch_arg(s: str) -> Punch: ...            # "9:03,18:07" 1件
def parse_punch_csv(path_or_stdin) -> list[Punch]: ...# 不正行は warn して skip（要§7.2）
    # 返り値: 有効な Punch のみ。警告は stderr。

# rounding.py
def round_minutes(minute_of_day: int, unit: int, direction: str) -> int:
    """HH:MM を当日0時からの分数で受け取り、unit分単位で direction 方向に丸め、
       丸め後の分数を返す。ceil=上方向、floor=下方向、round=half-up（0.5=上）。
       真理値表（要§2.4）はこの関数の呼び出し側（=engine）で clock_in/clock_out
       それぞれに適用することで自然に再現される。"""

def round_punch(punch: Punch, rule: Rule) -> RoundedPunch: ...

# payroll.py
def calc_pay(minutes: int, hourly_yen: int, amount_rounding: str) -> int:
    """支払額 = round_by(hourly_yen * minutes / 60, amount_rounding)
       amount_rounding: 'floor'（デフォルト）/ 'half_up' / 'ceil'"""

# warnings_detector.py
def check_rule_warnings(rule: Rule) -> list[Warning]:
    """(a) clock_in=ceil & clock_out=floor → 労働時間 減少方向
       (b) clock_in=floor & clock_out=ceil & unit_minutes>=15 → 増加方向
       上記以外は空リスト（要§4.1 M4）。"""

# comparator.py
def compare_rules(punches: list[Punch], rules: list[Rule],
                  hourly: int, break_minutes: int | None,
                  amount_rounding: str,
                  baseline: str | int | None = None) -> ComparisonResult:
    """amount_rounding は全ルール共通で適用（要§4.1 M5 公平性担保）。
       YAMLの amount_rounding 値は無視し、不一致があれば stderr に1回 [WARN]。
       break_minutes=None は compare 時の共通 break=0 を意味する（Codex R2 Critical 指摘2）。
       baseline は rule.name 文字列 or rules のインデックス（0始まり）。
       解決不能（該当 name なし / index 範囲外）なら exit 2（Codex R2 Major 指摘）。"""

# explainer.py
def explain(punch: Punch, rule: Rule, demo: bool) -> ExplainTrace: ...
```

### 3.3 分離の根拠
- **設定ローダと丸めエンジンの分離**: YAML は将来 JSON 化（要§4.3 W拡張）もあり得るため、設定読込を差し替え可能に
- **金額計算の独立モジュール化**: `amount_rounding` の仕様（要§4.1 M1, M5）が比較エンジンと simulate 両方で使われるため単一実装源にする
- **警告検出の独立モジュール化**: 要件書で条件が厳密定義されており、将来の警告追加（SHOULD深夜帯 等）に備えて集約
- **フォーマッタの独立モジュール化**: text/json/csv 3系統の出力制御、免責の出力ストリーム分岐、`--out` パス検証を一箇所に集約

---

## 4. データフロー

### 4.1 simulate の詳細フロー

```
[入力]
  --rule *.yml
  --punch "9:03,18:07"  または  --punch-file *.csv  または  STDIN
  （オプション）--break N, --hourly Y, --format {text|json|csv}, --out PATH

[処理]
  (1) config_loader.load_rule(path) → Rule
  (2) punch_parser.parse_*()        → list[Punch]
        ├─ 不正行 → stderr 警告、当該行のみ skip（要§7.2）
        └─ 全列欠損・YAMLエラー → exit 2
  (3) for each Punch:
        a) rounding.round_punch(p, rule) → RoundedPunch（丸め後出勤・退勤・差分）
        b) gross_min = rounded.clock_out_min - rounded.clock_in_min
        c) break_min = 優先順位: --break → rule.break.minutes → 0（要§7.1）
        d) net_min = max(0, gross_min - break_min)
        e) （--hourly 指定時）pay_yen = payroll.calc_pay(net_min, hourly, rule.amount_rounding_or_default)
           ※ 複数打刻の合計額を表示する場合も **打刻1行ごとに calc_pay を適用してから合算**（Codex R3 Critical 指摘で compare と統一）
  (4) warnings_detector.check_rule_warnings(rule) → 警告リスト
  (5) formatter.emit(results, warnings, fmt, out_path)

[出力]
  text: stdout に免責＋結果テーブル
  json: stdout に構造化データ、stderr 1行に免責
  csv:  stdout に表形式、stderr 1行に免責
  --out 指定時: 指定ファイル（cwd配下チェック、範囲外は exit 2）
```

### 4.2 compare の詳細フロー

```
(1) 各 --rule 要素ごとに load_rule → list[Rule]
(2) comparator.compare_rules(punches, rules, hourly, break_min, amount_rounding, baseline):
      a) 共通 amount_rounding を決定:
           CLI --amount-rounding 指定 → それを採用
           未指定 → 'floor'（デフォルト）
         各ルールの amount_rounding と不一致なら stderr に1回警告（要§4.1 M5 / [WARN]）
      b) 休憩分数の共通化（Codex R2 Critical 指摘2）:
           --break 指定 → 全ルールに同一値を適用
           --break 未指定 → **全ルール break=0 を共通適用**（各 rule.break_minutes は無視）
         これにより「ルール差」＝「丸め方式差」のみを純粋比較でき、要§4.1 M5 の公平性要件と整合する。
         各ルールの break_minutes と共通適用値が異なるルールが1件以上あれば stderr に1回 [WARN] を出力。
      c) 各 Rule について simulate と同じ丸め＋ (b) の共通 break で Net を出す
      d) pay は **打刻1行ごとに** calc_pay(net_min, hourly, 共通amount_rounding) を適用して合算（Codex R3 Critical 指摘で simulate と統一）
      e) 基準ルール（§6.1.3 の baseline 解決規則に従う。デフォルト rules[0]）との差額を算出
(3) formatter.emit_comparison(...):
      デフォルトは Net 列のみ。--show-gross で Gross 列追加（要§4.1 M5）
```

### 4.3 explain の詳細フロー

```
(1) load_rule + parse_punch_arg
(2) explainer.explain(punch, rule, demo=args.demo):
      通常モード（5ステップ）: 出勤丸め / 退勤丸め / Gross算出 / 休憩控除 / Net算出
      --demo（3ステップ）:     丸め / 控除 / 最終値
(3) warnings_detector.check_rule_warnings(rule) を末尾に追記
(4) formatter は text 専用（json/csv 出力は MUST 外とする）
```

### 4.4 エラー時分岐（詳細は §8）
- パース不能な行: warn → skip → 他の行は継続
- YAML不正 / `direction` 不明 / `amount_rounding` 不明 / CSV必須列欠損 / `--out` cwd外: **exit 2 で中断**
- **全行スキップ（有効行 0 件）**: **exit 2 で中断**し、`[ERROR] no valid punches after parsing (all rows skipped)` を stderr に出力する（Codex R2 Major 指摘）。「警告が大量に出ているのに exit 0 で成功扱い」は誤解を招くため、入力不正扱いとする。
- その他想定外例外: stderr にエラーメッセージ、exit 1

---

## 5. データモデル / スキーマ

### 5.1 ドメインオブジェクト（内部表現）

```python
# dataclass 想定。可変状態を持たせない（非機能要件の再現性を担保）。

@dataclass(frozen=True)
class Punch:
    date: str | None            # "YYYY-MM-DD" or None（CLI単発時）※Codex R2 Minor
    employee_id: str | None     # 匿名ID（"EMP001" 等）or None（CLI単発時）※Codex R2 Minor
    clock_in_min: int           # 当日0時からの分数（例: 9:03 → 543）。範囲 0..1439
    clock_out_min: int          # 範囲 0..1439（入力値。24:00/1440 は RoundedPunch のみ許容、§7.1 / Codex R3 Minor 指摘1）

@dataclass(frozen=True)
class RoundingSide:
    direction: str      # "ceil" | "floor" | "round"

@dataclass(frozen=True)
class Rule:
    name: str
    description: str
    unit_minutes: int           # 1 / 5 / 15 / 30 / 60
    clock_in: RoundingSide
    clock_out: RoundingSide
    break_minutes: int          # fixed のみ対応（MUST）
    amount_rounding: str        # "floor" | "half_up" | "ceil"（デフォルト "floor"）

@dataclass(frozen=True)
class RoundedPunch:
    original: Punch
    clock_in_min_rounded: int
    clock_out_min_rounded: int
    delta_in_min: int           # 丸め後 - 丸め前
    delta_out_min: int

@dataclass
class SimulationRow:
    punch: Punch
    rounded: RoundedPunch
    gross_min: int
    break_min: int
    net_min: int
    pay_yen: int | None
```

### 5.2 YAML スキーマ（MUSTスコープ）

```yaml
# 必須キー
name: string                      # 表示用ルール名
unit_minutes: int                 # 1 / 5 / 15 / 30 / 60
clock_in:
  direction: string               # ceil | floor | round
clock_out:
  direction: string               # ceil | floor | round

# 任意キー
description: string
break:
  type: "fixed"                   # MUSTは fixed のみ
  minutes: int                    # 未指定時は 0
amount_rounding: string           # floor（デフォルト） | half_up | ceil
```

**スキーマ検証ルール**:
- 必須キー欠損 → `RuleLoadError`（exit 2）
- `direction` が ceil/floor/round 以外 → exit 2（要§7.2）
- `amount_rounding` が許容値以外 → exit 2（要§7.2）
- `break.type` が `fixed` 以外 → exit 2（MUST範囲外、SHOULDは `clock` 等を後日追加）
- `overtime:` ブロックは**読み捨てるが WARN を必ず出力**（「このビルドでは `overtime` は未適用」）。非対応機能を静かに無視する隠蔽を避ける（Codex R1 Critical 指摘3）。将来 SHOULD 対応時に有効化。

### 5.3 CSV スキーマ（入力）
- **許可列のみ受理（allowlist 方式 / Codex R2 Critical 指摘3）**: ヘッダは原則として以下の**許可列セットのみ**を受理する。
  - 許可列: `date`, `employee_id`, `clock_in`, `clock_out`（必須列、順不同、列名で判定）
  - それ以外の列がヘッダに含まれる場合、`punch_parser` は処理開始前に exit 2 で中断し、`[ERROR] unexpected column (not in allowlist): <name>` を stderr に出力する。
- エンコード: UTF-8（BOM可）
- `employee_id` 正規表現: `^[A-Z]{2,4}\d{3,6}$`（要§7.1）
- **例外解除フラグ**: `--allow-extra-columns` を明示指定した場合のみ、許可列以外の列を**無視**して処理を継続する。ただし従来の禁止リスト（氏名・連絡先・取引先名等）は `--allow-extra-columns` 指定時でも常に exit 2 で拒否する（多層防御）。
  - 禁止列名（大文字小文字・前後空白無視で判定）: `name` / `employee_name` / `staff_name` / `full_name` / `client_name` / `company_name` / `dispatch_destination` / `email` / `phone` / `address` / `birth_date`
  - 検出時: `[ERROR] forbidden column (PII) detected: <name>` を出力し exit 2。
- **デモビルドでの無効化**（Codex R3 Major 指摘1）: セミナー登壇用のデモビルド（`DEMO_BUILD=1` 環境変数 or ビルド時定数）では `--allow-extra-columns` フラグ自体を argparse レベルで**未登録**とし、指定しても `unrecognized arguments` で exit 2 となる。これにより「実データ投入禁止」の設計担保を運用時もフラグ面でも担保する。開発・検証ビルドでのみフラグが有効化される。
- **設計意図**: R1 で採用したブラックリスト単独では「列名の自由度が高い日本の勤怠CSV」に対しPII流入を網羅できないため、R2 で**デフォルト拒否（許可列のみ）** に切替。R3 ではデモビルドでフラグ自体を無効化し、「実データ禁止」要件を設計レベルで閉じる。`--allow-extra-columns` は既存勤怠システムCSVとのブリッジ用エスケープハッチで、セミナーデモでは利用不能。

### 5.4 出力ファイル（`--out`）
- text の `--out`: UTF-8 プレーンテキスト（カラーコードは除去）
- json の `--out`: UTF-8 JSON（整形済み、`ensure_ascii=False`）
- csv の `--out`: UTF-8 CSV（BOMなし、ヘッダ付き）
- パス規約: **正規化後の絶対パスが `cwd` 配下**（§9.2）

---

## 6. インタフェース設計

### 6.1 CLI サブコマンド体系

```
python src/main.py <subcommand> [options]

subcommand:
  simulate   1つのルールで打刻データをシミュレーション（M1〜M3相当）
  compare    複数ルールで比較、時給から支払額差分を算出（M5相当）
  explain    逆算チェック、「なぜこの結果か」を説明（M4相当）
  validate   YAMLルール定義の構文・値域チェック（M1支援）
```

#### 6.1.1 共通オプション

| オプション | 値 | 説明 | 優先順位 |
|---|---|---|---|
| `--format` | text / json / csv | 出力形式。デフォルト text | — |
| `--out` | path | 出力ファイル（cwd配下限定） | §9.2 検証 |
| `--quiet` | flag | 免責表示と `[INFO]` のみ抑制。`[WARN]` / `[ERROR]` は常時出力（要 M2） | §9.4 |
| `--no-color` | flag | ANSIカラー無効化（非TTY時は自動無効） | — |
| `--debug` | flag | 想定外例外時に詳細トレースを stderr へ出力（Codex R3 Minor 指摘2）。未指定時は簡潔なエラーメッセージのみ | §8.1 / §8.2 |

#### 6.1.2 `simulate` オプション

| オプション | 必須 | 説明 |
|---|---|---|
| `--rule PATH` | 必須 | YAMLルール |
| `--punch "HH:MM,HH:MM"` | いずれか | 単発打刻 |
| `--punch-file PATH` | いずれか | CSV |
| `--break MIN` | 任意 | 休憩分数。YAML値より優先（要§7.1） |
| `--hourly YEN` | 任意 | 時給。指定時は pay_yen を算出 |

未指定で STDIN がパイプの場合は STDIN を CSV として読む。

**入力ソースの排他制約**（Codex R2 Major 指摘で明確化）:
- `--punch` と `--punch-file` の同時指定は argparse の `mutually_exclusive_group` で静的に排他化する。
- **STDIN の扱いはランタイム検査**で行う。argparse では STDIN の有無を表現できないため、`main.py` の入口で `sys.stdin.isatty()` を判定し「STDIN が pipe（非 tty）かつ `--punch` / `--punch-file` のいずれかが指定されている」場合は exit 2 で中断する。
- 違反時のメッセージ: `[ERROR] input sources are mutually exclusive (got --punch/--punch-file and piped STDIN)`
- 3ソースとも未指定かつ STDIN が tty の場合は `simulate`/`compare` は exit 2、`[ERROR] no input: specify --punch, --punch-file or pipe STDIN`。`explain` は `--punch` 必須（単発打刻のみ / §6.1.4）。

#### 6.1.3 `compare` オプション

| オプション | 必須 | 説明 |
|---|---|---|
| `--rule PATH` | 必須 | YAMLパス。**複数回指定可**（2件以上必須）。R1までの `--rules P1,P2,...` 方式はパス中のカンマに弱いため R2 で `--rule` 多重指定へ変更（Codex R2 Minor 指摘）。 |
| `--punch` / `--punch-file` | いずれか | simulate と同じ |
| `--hourly YEN` | 必須 | 時給（比較の核） |
| `--break MIN` | 任意 | 休憩分数（全ルール共通適用）。**未指定時は 0 を共通適用**（§4.2 / Codex R2 Critical 指摘2） |
| `--amount-rounding` | 任意 | floor / half_up / ceil。未指定時 floor（要§4.1 M5） |
| `--show-gross` | 任意 | Gross列を追加表示 |
| `--baseline NAME_OR_INDEX` | 任意 | 基準ルール。`rule.name` 文字列 or 0始まりインデックス。未指定時は `rules[0]` |

**`--baseline` 解決規則**（Codex R2 Major 指摘）:
- 文字列指定時: 入力された `--rule` 群の `rule.name` と一致するものを基準に採用。一致しない場合 exit 2、`[ERROR] --baseline "<NAME>" does not match any loaded rule`。
- 整数指定時: 0始まりインデックスで `rules[i]` を基準に採用。範囲外は exit 2、`[ERROR] --baseline index out of range`。
- 両方解釈可能な値（例: 数字のみの rule.name）は**整数指定を優先**し、その上で範囲外なら上記エラー。
- 省略時: `rules[0]` を基準として黙示的に採用する。

#### 6.1.4 `explain` オプション
simulate と同じ + `--demo`（3ステップ短縮）。ただし `--punch-file` は MUST 外とし、単発打刻のみ対応（要§6 デモシナリオに合わせる）。

**`--format` の制約**: `explain` は逐次説明を目的とするため **`--format text` のみ許可**する。`json` / `csv` が指定された場合は CLI 層で即座に exit 2 とし、`[ERROR] explain supports --format text only` を stderr に出力する（Codex R1 Major 指摘5: §4.3 と §6.1.1 の内部矛盾解消）。

#### 6.1.5 `validate` オプション
- `--rule PATH`: YAML を読み込み、スキーマ検証のみ実施。合格なら exit 0、不合格なら exit 2 + stderr にエラー内容。

### 6.2 exit code

| code | 意味 |
|---|---|
| 0 | 正常終了 |
| 1 | 想定外の実行時エラー（予期せぬ例外） |
| 2 | 入力不正による中断（YAMLエラー、必須列欠損、direction/amount_rounding不正、allowlist違反、`--baseline`解決不能、全行スキップ、`--out` cwd外） |

行単位スキップ（要§7.2）は**少なくとも1行が有効**である限り exit 0（stderr に警告あり）。**全行スキップ時は exit 2**（§4.4 / Codex R2 Major 指摘）。

### 6.3 出力ストリーム設計

| フォーマット | stdout | stderr |
|---|---|---|
| text（デフォルト） | 免責 1行 + 結果 | 行スキップ警告等のみ |
| json | JSON オブジェクトのみ | 免責 1行 + 行スキップ警告 |
| csv | CSV のみ | 免責 1行 + 行スキップ警告 |
| `--quiet` 付与時 | 免責なし | 免責・`[INFO]` は抑制。`[WARN]` / `[ERROR]` は**常時出力**（§9.4） |

### 6.4 Claude Code スラッシュコマンド
要件書 §10.4 の対応表に準拠。スラッシュコマンドのマッピングは Claude Code 側の設定ファイル（本プロジェクト外）で定義し、CLI 側は特別な処理を持たない（exit code 透過）。

---

## 7. アルゴリズム設計

### 7.1 丸めエンジン（`rounding.round_minutes`）

真理値表（要§2.4）は、**「clock_in/clock_out に ceil/floor/round を独立に適用する」という一本化した関数**で実現できる。方向性（増加/減少）は applied-to-in と applied-to-out の組み合わせで自然に現れるため、分岐不要。

```
関数 round_minutes(m: int, unit: int, direction: str) -> int:
    # m: 入力範囲 0..1439 の分数（当日0時基点）
    # 戻り値: 0..1440 の分数（1440 は 24:00 を表す特殊値、退勤側 ceil のみ発生）
    # unit: 1 / 5 / 15 / 30 / 60
    if direction == "floor":
        return (m // unit) * unit
    if direction == "ceil":
        q, r = divmod(m, unit)
        return (q + 1) * unit if r else m    # ちょうど割り切れるときは据え置き
    if direction == "round":
        # half-up（0.5 は上方向へ）
        q, r = divmod(m, unit)
        return (q + 1) * unit if r * 2 >= unit else q * unit
    raise ValueError(direction)   # 事前検証済みだが防御的に
```

**24:00 境界の扱い**（Codex R2 Critical 指摘1）:
- 入力 `clock_in_min` / `clock_out_min` は `HH:MM` パース時点で `0..1439`。`24:00` 表記は入力拒否（`punch_parser` が `[WARN] line N: invalid time (24:00 not allowed as input)` で skip）。
- 丸め結果の戻り値は `0..1440` を許容する。**`1440` は 24:00（＝当日末尾）を表す特殊値**とし、退勤 `ceil` で `23:xx` が 1440 に繰り上がる場合のみ発生する。日またぎ（1441 以上）は MUST 範囲外。
- 出勤側 `ceil` で 1440 になる入力（= `23:xx` 出勤）は業務上あり得ないため、`clock_in_rounded == 1440` を検出した場合は致命扱いとし `[ERROR] clock_in rounded to 24:00 is invalid` で exit 2。
- `HH:MM` 文字列への再変換では `1440` を `"24:00"` として表示する（`formatter` および `explainer` で統一）。`25:xx` 以降は発生しない。

**真理値表との対応**（適用後の時刻 vs 元時刻）:
- 出勤 + `ceil` → 後ろにずれる → 労働時間 減少方向
- 出勤 + `floor` → 前にずれる（＝等値のまま or 分数減） → 労働時間 増加方向
- 退勤 + `ceil` → 後ろにずれる → 労働時間 増加方向
- 退勤 + `floor` → 前にずれる → 労働時間 減少方向

> 設計上の決定: 時刻を「分のみの整数」として扱う。日本の勤怠は分粒度で完結（要§7.1 秒非対応MUST）、日またぎなし（MUST）のため、当日0時基点の 0〜1439 の int で十分。時刻 ⇔ 分の変換は `punch_parser` に閉じ込める。

### 7.2 Net（支払対象時間）算出
```
gross_min = rounded.clock_out_min - rounded.clock_in_min
break_min = --break 指定値 or rule.break_minutes or 0
net_raw   = gross_min - break_min
net_min   = max(0, net_raw)
if net_raw < 0:
    emit_warning(f"[WARN] break_minutes ({break_min}) exceeds gross ({gross_min}); "
                 f"net clamped to 0 (punch={punch.date} {punch.employee_id})")
```
`gross_min <= 0` は要§7.2 により上流の `punch_parser` でスキップ済み（「退勤<=出勤」は当該行スキップ）。`net_raw < 0` となる設定不整合（例: 休憩 > Gross）は 0 に丸めた上で **WARN を必ず出力**し、原因追跡可能にする（Codex R1 Major 指摘8: 休憩過大を静かに 0 化しない）。

### 7.3 explain（逆算説明）

```
通常モード（5ステップ）:
  [ステップ1] 出勤時刻の丸め
    原時刻、ルール文言、計算過程（"9:03 → 15分単位で上に丸め → 9:15"）、差分と方向
  [ステップ2] 退勤時刻の丸め
  [ステップ3] Gross労働時間の算出
  [ステップ4] 休憩控除
  [ステップ5] 支払対象時間（Net）
  最後に warnings_detector の結果を付記

--demo（3ステップ短縮）:
  [1] 丸め: 出勤と退勤の丸め結果を1行にまとめる
  [2] 控除: Gross − 休憩 = Net を1行
  [3] 最終: Net のみ
  最後に warnings を1行付記
```

**設計意図**: 派遣先への金額説明・スタッフへの給与説明という**説明責任**に直結する機能であり、「何分が、どのルールで、どちら向きに動いたか」を1打刻ずつ追えることを最優先する。`--demo` は7分デモ枠（要§6）制約から生まれた**プレゼン専用ビュー**で、通常運用では冗長な通常モードを使う想定。

### 7.4 警告検出（`warnings_detector.check_rule_warnings`）

```
def check_rule_warnings(rule: Rule) -> list[str]:
    warnings = []
    ci = rule.clock_in.direction
    co = rule.clock_out.direction
    unit = rule.unit_minutes

    # 条件(a): 労働時間 減少方向
    if ci == "ceil" and co == "floor":
        warnings.append("出勤ceil × 退勤floor は労働時間 減少方向に偏った設定です")

    # 条件(b): 労働時間 増加方向 かつ unit_minutes >= 15
    if ci == "floor" and co == "ceil" and unit >= 15:
        warnings.append("出勤floor × 退勤ceil (unit>=15) は労働時間 増加方向に偏った設定です")

    return warnings
```

**設計意図**: 要件書で「曖昧な『強く偏っている』判定は廃止」と明示されており、条件 (a)(b) 以外では**沈黙**させる。これにより「1分単位（フェア）」「round × round」「floor × floor 1min」等に余計な警告が付かない。

### 7.5 比較エンジン（`comparator.compare_rules`）

```
def compare_rules(punches, rules, hourly, break_min_cli, amount_rounding_cli, baseline):
    # 1. 共通 amount_rounding を確定
    effective_ar = amount_rounding_cli or "floor"

    # 2. YAML 値と有効値（effective_ar）の不一致があれば必ず1回だけ stderr 警告
    #    レベル: [WARN]（Codex R2 Minor 指摘で [INFO] → [WARN] に格上げ）
    yaml_ars = {r.amount_rounding for r in rules}
    if any(ar != effective_ar for ar in yaml_ars):
        stderr.write(
            "[WARN] compare では共通 amount_rounding を適用します "
            f"(有効値={effective_ar}, YAML値は無視): "
            f"{sorted(yaml_ars)}\n"
        )

    # 3. 共通 break を確定（Codex R2 Critical 指摘2）
    effective_break = break_min_cli if break_min_cli is not None else 0
    yaml_breaks = {r.break_minutes for r in rules}
    if any(b != effective_break for b in yaml_breaks):
        stderr.write(
            f"[WARN] compare では共通 break={effective_break} を適用します "
            f"(YAML値は無視): {sorted(yaml_breaks)}\n"
        )

    # 4. baseline を解決（§6.1.3 の規則に従う）
    baseline_index = resolve_baseline(rules, baseline)  # 解決不能なら exit 2

    # 5. 各 Rule について全打刻を計算（Codex R3 Critical 指摘: simulate と同一の
    #    「行単位で支払額を丸めて合算」方式に統一。合計分を1回丸める方式とは結果が
    #    異なる場合があるため、仕様として固定する）
    per_rule_results = []
    for rule in rules:
        total_net_min = 0
        total_pay = 0
        for p in punches:
            rp = round_punch(p, rule)
            gross = rp.clock_out_min_rounded - rp.clock_in_min_rounded
            net = max(0, gross - effective_break)
            total_net_min += net
            total_pay += calc_pay(net, hourly, effective_ar)  # 行単位で丸めて加算
        per_rule_results.append((rule.name, total_net_min, total_pay))

    # 6. 基準との差を算出
    baseline_pay = per_rule_results[baseline_index][2]
    return [(name, net, pay, pay - baseline_pay) for name, net, pay in per_rule_results]
```

**公平性担保**（要§4.1 M5）: 比較時は全ルールに同じ `amount_rounding` を適用するため、「ルール差による金額差」から「丸め方式差による金額差」を分離できる。これが派遣元の担当者が「設定違いの影響額」だけを純粋に評価できる根拠となる。

**支払額の集計単位**（Codex R3 Critical 指摘）: `simulate` と `compare` の両方で **「打刻1行ごとに `calc_pay` で丸めてから合算」** 方式に統一する。合計分数を1回だけ丸める方式とは `floor` / `half_up` / `ceil` いずれの設定でも結果が異なり得るため（例: 1日あたり剰余が複数日累積することで日次丸めと月次丸めで差が出る）、仕様として行単位丸めに固定する。技術仕様書のテストケースでは `floor` / `half_up` / `ceil` の3方式で「行単位合算」と「合計1回丸め」の差が出る最小ケースを必須項目として含める。

### 7.6 金額計算式（`payroll.calc_pay`）

`hourly_yen`（整数円）と `minutes`（整数分）は常に整数のため、**整数演算のみで厳密に計算**し、float を排除する。`half_up` の境界値（例: `x.5`）で float 誤差により丸め方向が揺れるリスクを設計段階で排除する（Codex R1 Critical 指摘1）。

```
def calc_pay(minutes: int, hourly: int, amount_rounding: str) -> int:
    # numerator = hourly × minutes （整数）
    # denominator = 60            （整数）
    # すべて整数の商・剰余のみで丸め方向を決定する
    num = hourly * minutes
    q, r = divmod(num, 60)     # num == q*60 + r, 0 <= r < 60
    if amount_rounding == "floor":
        return q                         # 切り捨て
    if amount_rounding == "ceil":
        return q + (1 if r > 0 else 0)   # 割り切れない時のみ +1
    if amount_rounding == "half_up":
        # 0.5 相当（=r*2==60）は上方向へ。r*2 > 60 も上方向。
        return q + (1 if r * 2 >= 60 else 0)
    raise ValueError(amount_rounding)
```

**検算**（要§6 ステップ3、整数演算）:
- 1分単位: 1800 × 484 = 871200、÷60 の商 14520、剰余 0 → floor → 14,520円 ✓
- employee_friendly: 1800 × 495 = 891000、商 14850、剰余 0 → floor → 14,850円 ✓
- company_friendly: 1800 × 465 = 837000、商 13950、剰余 0 → floor → 13,950円 ✓
- 差額: 14,850 − 13,950 = 900円/日、×20日 = 18,000円/月 ✓

> **float を使わない判断**: 整数演算（`divmod`）で厳密に丸め方向を確定できるため、float 誤差に起因する境界値の揺れを設計段階で排除する。`half_up` で `r*2 == 60`（= 0.5 相当）が上方向に倒れることが明示でき、派遣の時給レンジに依存しない堅牢な実装になる。Decimal も不要。

---

## 8. エラーハンドリング・異常系設計

### 8.1 エラー分類

| 分類 | 判断基準 | 挙動 |
|---|---|---|
| **致命（exit 2）** | ツールとして処理続行が意味をなさない入力不正 | 即時中断、stderr にエラー内容 |
| **致命（exit 1）** | 想定外の内部例外 | stderr にトレース、終了 |
| **警告（継続）** | 1件単位でスキップ可能な入力不正 | stderr に1行、処理継続 |
| **情報** | 設定選択の注意喚起（compare の共通丸め等） | stderr に1行、処理継続 |

### 8.2 具体的マッピング（要§7.2 完全対応）

| 事象 | 分類 | 挙動詳細 |
|---|---|---|
| YAML に `overtime:` ブロック検出 | 警告 | ブロック読み捨て、`[WARN] overtime is not applied in this build (SHOULD scope)`（C.3） |
| CSV ヘッダに禁止列名検出 | 致命 | exit 2、`[ERROR] forbidden column (PII) detected: <name>`（§5.3 / §9.1） |
| 休憩 > Gross で Net を 0 に丸め | 警告 | 処理継続、`[WARN] break_minutes exceeds gross; net clamped to 0`（§7.2） |
| 時刻フォーマット違反（`25:77`, `abc`） | 警告 | `punch_parser` が skip、`[WARN] line N: invalid time ...` |
| `HH:MM:SS`（秒付き） | 警告 | skip、`[WARN] line N: seconds not supported in MUST (§7.1)` |
| `clock_out <= clock_in` | 警告 | skip、`[WARN] line N: clock_out must be > clock_in` |
| `clock_in`/`clock_out` 空欄 | 警告 | skip、`[WARN] line N: empty clock_in/clock_out` |
| `date` フォーマット不正 | 警告 | skip、`[WARN] line N: invalid date format` |
| `employee_id` パターン違反 | 警告 | skip、`[WARN] line N: employee_id must match ^[A-Z]{2,4}\d{3,6}$` |
| CSV必須列欠損 | 致命 | exit 2、`[ERROR] CSV missing required columns: ...` |
| CSVヘッダに許可外列（allowlist 違反） | 致命 | exit 2、`[ERROR] unexpected column (not in allowlist): <name>`（§5.3 / Codex R2 Critical 指摘3） |
| 全行スキップ（有効行 0 件） | 致命 | exit 2、`[ERROR] no valid punches after parsing (all rows skipped)`（§4.4 / Codex R2 Major 指摘） |
| `clock_in_rounded == 1440`（24:00 出勤） | 致命 | exit 2、`[ERROR] clock_in rounded to 24:00 is invalid`（§7.1 / Codex R2 Critical 指摘1） |
| `--baseline` 解決不能 | 致命 | exit 2、`[ERROR] --baseline "<NAME>" does not match any loaded rule` or index out of range（§6.1.3 / Codex R2 Major 指摘） |
| YAML パースエラー | 致命 | exit 2、`[ERROR] failed to parse YAML: ...` |
| `direction` 不明 | 致命 | exit 2、`[ERROR] unknown direction: X (must be ceil/floor/round)` |
| `amount_rounding` 不明 | 致命 | exit 2、`[ERROR] unknown amount_rounding: X (must be floor/half_up/ceil)` |
| `--out` パスが cwd 外 | 致命 | exit 2、`[ERROR] --out path must be under cwd` |
| `--out` 親ディレクトリ不存在 | 致命 | exit 2、`[ERROR] --out parent directory does not exist` |
| 想定外例外 | 致命 | exit 1、stderr に簡潔なエラーメッセージ（`[ERROR] unexpected error: <type>: <msg>`）。**詳細トレースは `--debug` 指定時のみ**出力（Codex R3 Minor 指摘2 / デモ運用でのトレース過多を回避） |

### 8.3 警告メッセージ形式
```
[WARN] <source>:<line> <description>
[ERROR] <description>
[INFO] <description>
```
色付き（TTY時）は `[WARN]` 黄、`[ERROR]` 赤、`[INFO]` シアン。`--no-color` or 非TTY で無効。

### 8.4 回復可能性の判断
- **1行スキップで全体処理が意味を持つもの** → 警告（CSV の行単位エラー）
- **1行の不正が全体整合性を崩すもの** → 致命（必須列欠損、YAMLパース失敗）
- 派遣の月次打刻は「1日でも欠けたら請求計算不可」ではなく「他の日は計算したい」が自然なため、行単位スキップを採用（要§4.1 M2）

---

## 9. セキュリティ・プライバシー設計

### 9.1 実データ投入禁止の担保
- **技術的担保（多層防御）**:
  1. `employee_id` 正規表現 `^[A-Z]{2,4}\d{3,6}$` による匿名IDパターン強制（要§7.1）。違反行はスキップ＋ WARN。
  2. **禁止列名検知**（§5.3 / Codex R1 Major 指摘7）: ヘッダに `name` / `employee_name` / `client_name` / `email` 等を検出した時点で処理開始前に exit 2 中断。追加列による氏名・企業名・連絡先の誤流入を設計レベルで阻止する。
  3. **デモビルドでのフラグ無効化**（§5.3 / Codex R3 Major 指摘1）: `--allow-extra-columns` はデモビルドでは argparse 未登録とする。セミナー登壇時の操作ミスでも許可列以外を素通しできない。
- **運用的担保**: サンプル `samples/rules/` `samples/punches.csv` はすべて架空データで構成（要§5.1）。セミナー登壇時はこれらのみ使用。
- **設計原則**: 「列名ベースの入口防御」と「値パターンベースの行防御」の二段で、`employee_id` 正規表現だけに依存しない構造にする。

### 9.2 ファイル出力先の制限（`--out`）
```
def validate_out_path(path_str: str) -> Path:
    resolved = Path(path_str).resolve()       # シンボリックリンクも解決
    cwd = Path.cwd().resolve()
    # Codex R2 Minor 指摘: 文字列 prefix 依存を廃し、Path.is_relative_to 相当で判定
    try:
        resolved.relative_to(cwd)             # Python 3.9+ で例外にならなければ配下
    except ValueError:
        raise OutPathError("--out path must be under cwd")
    if not resolved.parent.exists():
        raise OutPathError("--out parent directory does not exist")
    return resolved
```
- **対象**: `simulate`/`compare`/`explain` の `--out` オプションのみ
- **対象外**: シェルリダイレクト（`>`, `>>`, `tee`）はOSレベルのため制御不可（要§5.1 に明記済み）。運用上の注意事項として README に転記予定。
- **失敗時**: exit 2、stderr にエラー

### 9.3 ログ保持ポリシー
- **永続ログなし**: `--log-file` 等は実装しない（要§5.1）
- **一時出力のみ**: 警告・エラーは stderr へ。セッション終了で消える
- **入力打刻データ**: メモリ上のみ、プロセス終了で消える

### 9.4 免責表示（要§5 非機能要件）
```
固定文言: "※本ツールは設定ルール通り計算するだけの補助ツールです。
           36協定・同一労働同一賃金・抵触日等の法令適合判定は行いません。"

出力先制御:
  --format text  (default) → stdout 先頭に表示
  --format json           → stderr に1行（stdout は JSON のみ）
  --format csv            → stderr に1行（stdout は CSV のみ）
  --quiet 明示            → 免責表示と [INFO] のみ抑制。
                             [WARN]（行スキップ警告・overtime 非対応警告等）と
                             [ERROR] は要§4.1 M2 により常時 stderr 出力する。
```

**設計意図**: 機械可読出力（json/csv）を他ツールにパイプする際、免責行が混入すると後続処理が破綻するため自動的に stderr へ逃がす（自動 `--quiet` 相当 / 要§5）。一方、**不正行スキップの警告は MUST 要件 M2 により可観測性を維持**する必要があるため、`--quiet` でも抑制しない（Codex R1 Critical 指摘2）。

### 9.5 派遣業務特有の配慮
- **派遣先企業名・案件名**: CSV スキーマに含めず、運用側メタデータとして外部管理（要§10.2）
- **スタッフ氏名**: CSV スキーマに含めない（列名 `name` を定義しない）
- **派遣先への金額説明**: explain の出力は**外部共有を前提としたフォーマット**（個人特定情報なし、匿名IDのみ）

---

## 10. 観測可能性・運用設計

### 10.1 ログ出力方針
- **レベル**: `[INFO]` / `[WARN]` / `[ERROR]`（`DEBUG` は実装しない。MUST最小）
- **フォーマット**: 単一行テキスト（JSON ログは MAY 拡張）
- **保存先**: stderr のみ。ファイル出力なし（§9.3）
- **色付け**: TTY かつ `--no-color` 未指定時のみ ANSI エスケープ付与

#### 10.1.1 実行サマリ共通項目（Codex R2 Major 指摘）
将来の観測可能性拡張を見越し、以下の最小共通項目を実行終了時に stderr へ 1 行のサマリとして出力する（`--quiet` 時は抑制、ただし `[WARN]/[ERROR]` は常時出力）。

| 項目 | 型 / 例 | 説明 |
|---|---|---|
| `run_id` | string | 実行単位の一意ID（UUID4 もしくはタイムスタンプベース） |
| `subcommand` | string | `simulate` / `compare` / `explain` / `validate` |
| `rule_name` | string / list | 適用した `rule.name`。compare 時は list |
| `input_source` | string | `cli` / `csv:<path>` / `stdin` |
| `processed_count` | int | 有効として集計した打刻行数 |
| `skipped_count` | int | パース不能等で skip した行数 |
| `exit_code` | int | 最終 exit code |

サマリ行フォーマット例（単一行）:
```
[INFO] summary run_id=<id> subcommand=<sub> rule_name=<name> input_source=<src> processed=<N> skipped=<M> exit=<code>
```
これにより、将来の JSON ログ化・集計基盤接続時もキー名を不変で拡張できる。

### 10.2 デモ時の見せ方との整合
| デモ要件（要§6） | 設計上の対応 |
|---|---|
| 7分±1分で完走 | `--demo` で explain 出力を3ステップに短縮、compare もデフォルトNetのみで視認性優先 |
| 「衝撃演出」ステップ3 | compare テーブルの「基準との差」列で ±330円 / −570円 / 合計900円を1画面表示 |
| 色付き強調 | text フォーマット時、差額の符号で色を切替（+ 赤 / − 青 等、色コードは技術仕様書で定義） |
| 技術トラブルなし | 標準ライブラリ＋PyYAML のみ。外部API・ネットワーク不要、再現性100%（非機能要§5） |

### 10.3 将来拡張への接続点

| 要件書での将来拡張 | 設計上の接続点 |
|---|---|
| S1 法定内外別ルール | `Rule` モデルに `overtime` フィールドを後付け可能。`rounding.round_punch` の呼び出し側で日次8h閾値判定を追加する形 |
| S2 深夜割増 | `warnings_detector` の拡張＋ `payroll.calc_pay` に割増係数を注入 |
| S3 月次集計 | `engine.simulate` の結果を日次→月次集計する `aggregator.py` を追加 |
| S4 打刻ベース休憩 | `Rule.break` の `type` を `fixed` 以外に拡張、`engine` で分岐 |
| W1 Web UI | `engine.*` が純関数に近いため、Streamlit ラッパーから直接呼べる |
| W2 既存勤怠CSV取込 | `punch_parser` にアダプタ層を追加（KING OF TIME等のマッパー） |
| W4 影響額シミュレーション | `comparator.compare_rules` を過去複数月分に展開。現設計でも打刻を月跨ぎで渡せば動作する |
| W5 請求/給与同時出力 | ルールを2つ（派遣先用/派遣スタッフ用）受け取る compare の派生コマンドとして追加可能 |

### 10.4 運用観点の留意
- **派遣元の月次締め前運用**: 1回の実行で100件の打刻（要§5 性能要件）を1秒以内。シェルスクリプト or Claude Code スラッシュコマンドから案件別に連続実行する想定
- **CS導入支援のオンボーディング**: `validate` サブコマンドで顧客設定ファイルの事前チェックを自動化可能
- **説明責任の現場**: explain 出力を派遣先へそのまま共有しても個人情報が漏れない設計（§9.5）

---

## 付録A. 想定ディレクトリ構成

要件書 §付録の構成を責務分離に合わせて拡張（最小追加）。

```
02_rounding-checker/
├── docs/
│   ├── 01_requirements.md         ← 要件定義書 v0.4
│   ├── 02_design.md               ← 本書
│   ├── context-alignment-notes.md ← CS文脈寄せメモ
│   └── review-log.md              ← Codexレビュー履歴
├── src/
│   ├── main.py                    ← CLI ルーター
│   ├── engine.py                  ← 集約エンジン (simulate/compare/explain)
│   ├── config_loader.py           ← YAML → Rule
│   ├── punch_parser.py            ← 打刻入力パーサ
│   ├── rounding.py                ← 丸めエンジン
│   ├── payroll.py                 ← 金額計算
│   ├── warnings_detector.py       ← 警告検出
│   ├── explainer.py               ← 逆算説明
│   ├── comparator.py              ← 比較エンジン
│   └── formatter.py               ← 出力フォーマッタ
├── samples/
│   ├── rules/
│   │   ├── 1min.yml
│   │   ├── 15min_employee_friendly.yml
│   │   ├── 15min_company_friendly.yml
│   │   └── 30min_floor.yml
│   ├── rules/advanced/
│   │   └── 15min_with_overtime.yml
│   └── punches.csv
└── out/                           ← --out 出力先（任意・.gitignore 対象）
```

---

## 付録B. 用語定義（要件定義書から継承）

| 用語 | 定義 |
|---|---|
| 打刻時刻（生データ） | スタッフが実際に打刻した時刻（丸め前） |
| 丸め後時刻 | 設定ルールに基づき丸められた後の出退勤時刻 |
| Gross労働時間 | 丸め後の (退勤 − 出勤)。休憩控除**前** |
| 支払対象時間（Net） | Gross − 休憩控除 |
| 差分 | 丸め前後の分差（±分、丸め後 − 丸め前） |
| 労働時間 増加方向 / 減少方向 | 真理値表（要§2.4）の正式表記。現場口語の「スタッフ有利/会社有利」と対応 |
| amount_rounding | 支払額の円未満処理（floor/half_up/ceil） |

---

## 付録C. 設計上の決定記録

### C.1 時刻の内部表現を「当日0時基点の分 int」にする
- **選択肢**: (a) `datetime.time`、(b) `timedelta`、(c) **分 int**
- **選択**: (c) 分 int
- **理由**: 丸め計算が `//` と `divmod` の単純算術になり、真理値表の実装が最小行数で済む。MUSTでは日またぎなし（要§7）のため 0〜1439 の範囲で十分。time オブジェクトは丸め計算との親和性が低い。

### C.2 float vs Decimal（金額計算）
- **選択**: **整数演算（`divmod`）のみ**で `floor` / `half_up` / `ceil` を実装。float / Decimal のいずれも使わない。
- **理由**: `hourly_yen` も `minutes` も整数のため、`num = hourly * minutes` と `q, r = divmod(num, 60)` で厳密に丸め方向を決定できる。float を経由すると `half_up` の境界値（`x.5`）で誤差により方向が揺れるリスクがあり、デモの数値信頼性を損なう（Codex R1 Critical 指摘1）。詳細は §7.6 を参照。

### C.3 `overtime` ブロックの扱い（SHOULD範囲）
- **選択**: MUSTでは**読み捨てるが WARN を必ず出力**（「このビルドでは `overtime` は未適用」）
- **理由**: パース失敗させず将来拡張時の互換性は維持するが、SHOULD 機能を含む YAML を**静かに無視**すると「設定したルールが適用されている」と誤解される恐れがある（Codex R1 Critical 指摘3）。非対応機能の存在を WARN で可視化することで、運用上の隠蔽を避ける。

### C.4 compare の共通 `amount_rounding` ポリシー
- **選択**: CLI > デフォルト(floor)。YAML 値は compare 時のみ無視、不一致あれば stderr 1回警告
- **理由**: 要件書 §4.1 M5「公平性担保」の直接実装。派遣元担当者が「設定違いの影響金額」だけを純粋に見たいシーン（月次締め前）に合致。

### C.5 `--demo` モードを explain 専用にする
- **選択**: simulate/compare には `--demo` を設けない
- **理由**: 7分デモ枠のボトルネックは explain の逐次説明であり、compare は既にテーブル1枚で完結、simulate は複数行でもスクロール可。`--demo` を全サブコマンドに散らすと設計ノイズ。

### C.6 モジュール名に派遣管理SaaS文脈を反映するか
- **選択**: 反映しない（`rounding`, `payroll`, `explainer` 等の汎用名を採用）
- **理由**: モジュール境界は**技術的責務**で区切るほうが再利用性が高い。派遣文脈はドキュメント・サンプルデータ・出力文言で表現し、コード構造には持ち込まない（将来 W2/W5 の拡張時にモジュールを使い回しやすい）。

### C.7 24:00 境界と内部分表現レンジ（Codex R2 Critical 指摘1）

- **選択**: 入力は `0..1439` に限定、**丸め結果は `0..1440` を許容**（1440 は 24:00 特殊値）。`clock_in` 側で 1440 になった場合は exit 2。
- **理由**: 退勤 `ceil` で `23:50` のような打刻が `24:00` に繰り上がるケースは実在するため、`clock_out` 側は 1440 を受け入れる必要がある。一方、`clock_in` の 1440 化は業務上ありえないため拒否する。レンジを拡張することで `HH:MM` 再変換時の表示も `"24:00"` に固定でき、実装者解釈の揺れを排除する。

### C.8 compare 時の break 共通化ポリシー（Codex R2 Critical 指摘2）

- **選択**: `--break` 未指定時は **全ルール break=0 を共通適用**（各 rule.break_minutes は無視）。不一致があれば [WARN] 1回。
- **理由**: 要§4.1 M5「公平性担保」は amount_rounding だけでなく break にも及ぶ。「ルール差」＝「丸め方式差」のみを純粋比較できる状態をデフォルトにする。rule 固有の break を使いたいなら `simulate` を個別に使う方が業務モデルに素直。

### C.9 PII 防御を allowlist 中心へ（Codex R2 Critical 指摘3）

- **選択**: CSV ヘッダは**許可列のみ受理**（デフォルト拒否）。`--allow-extra-columns` で緩和可、ただし禁止列（氏名・連絡先・取引先）は常時拒否。
- **理由**: ブラックリスト（禁止列名列挙）単独では日本の勤怠CSVで使われる任意列名を網羅できず、PII 流入の取りこぼしが発生しうる。allowlist（許可列のみ）へ反転することで「知らない列は通さない」を設計レベルで強制する。エスケープハッチは明示フラグのみ。

### C.10 支払額の集計単位を「行単位丸め合算」に固定（Codex R3 Critical 指摘）

- **選択**: `simulate` / `compare` ともに **打刻1行ごとに `calc_pay` を適用し、その結果を合算**する方式に統一。合計分を1回丸める方式は採らない。
- **理由**: `floor` / `half_up` / `ceil` いずれの丸めでも、日次で生じる剰余が積み上がるため「行単位合算」と「合計1回丸め」で結果が異なるケースが存在する。simulate と compare で異なる方式を採ると、compare の差額表示が simulate の日次和と一致しなくなり、業務説明性が崩れる。行単位丸めに固定することで、explain の逐次説明（1打刻ずつの支払額）と compare の合計額が必ず整合する。

### C.11 `--allow-extra-columns` をデモビルドで無効化（Codex R3 Major 指摘1）

- **選択**: デモビルドでは argparse レベルでフラグ未登録。開発・検証ビルドでのみ有効。
- **理由**: セミナー登壇時の操作ミスや悪意ある操作で許可列外を素通しできてしまうと、「実データ投入禁止」要件（要§5.1）が運用面で綻ぶ。フラグ自体が受理されないよう設計レベルで閉じることで、多層防御をさらに一段厚くする。

### C.12 実行環境要件の明文化（Codex R3 Major 指摘2）

- **選択**: `Python >= 3.10` / `PyYAML >= 6.0` を設計書で固定し、起動時にバージョンチェック。
- **理由**: `str | None` 型表記や `Path.is_relative_to` 等、設計書内で前提としている標準機能のバージョン依存を明示しないと、Phase4 で環境差分に起因する不具合を招く。起動時チェックで「早期失敗」させることで、実装時の揺らぎを最小化する。
