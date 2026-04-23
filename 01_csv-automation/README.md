# CSV加工の完全自動化 — 派遣管理CSV標準化ツール

クラウドスタッフィング AIデモ No.01。派遣元企業から毎月提出される崩れた勤怠CSV（ヘッダー揺れ／令和表記／全角半角混在／BOM＋Shift_JIS）を、1コマンドで標準スキーマに揃えるPython CLI。

**注意**: 本CLIはセミナーデモ用モックです。実運用グレードのバリデーション・監査ログ・権限制御は実装されていません。**実勤怠データを投入しないこと**。

---

## クイックスタート（3行）

```bash
cd 01_csv-automation
python3 src/main.py convert --input samples/timesheet_202604_haken_a.csv
# → out/timesheet_202604_haken_a.csv と out/*_report.md が生成される
```

Python 3.11.9 を推奨（3.10+ で動作）。外部依存なし（標準ライブラリのみ）。

---

## サンプルCSVの紹介

| ファイル | パターン | 見せどころ |
|---|---|---|
| `samples/timesheet_202604_haken_a.csv` | 列順逆転＋ヘッダー揺れ＋令和表記＋全角￥ | Before/Afterの劇的コントラスト（5行すべて自動変換成功） |
| `samples/timesheet_202604_haken_b.csv` | BOM＋全角数字＋全角コロン＋「1時間」表記 | 文字コード判定・記号正規化の網羅性 |
| `samples/timesheet_202604_haken_c.csv` | エラー混入（13月／氏名空／end<start／abc円） | 要確認セル4件を自動ハイライト |
| `samples/timesheet_202605_haken_a.csv` | 翌月分（パターンA同形式） | テンプレート再利用の一発変換デモ |

---

## デモシナリオ（セミナー実演の流れ、約4〜7分）

### 所要時間 約4分

1. **導入（30秒）** — `samples/timesheet_202604_haken_a.csv` を開く。ヘッダーが「時給 / 終業 / 始業 / 勤務日 / 氏名 / 社員コード / 休憩（分）」でバラバラ、値には「￥1,500」「令和8年4月23日」「全角スペース入り氏名」が混在していることを見せる。
2. **Beforeショック（30秒）** — 「毎月、月初月末の締めタイミングで、派遣先担当者が手でExcelで直してます」と業務の悲惨さを強調。
3. **コマンド実行（20秒）** — `/csv-convert samples/timesheet_202604_haken_a.csv` をClaude Codeから起動（または直接 `python3 src/main.py convert --input samples/timesheet_202604_haken_a.csv`）。
4. **After披露（60秒）** — `out/timesheet_202604_haken_a.csv` を開く。ヘッダーが標準スキーマ（`employee_id, name, work_date, start_time, end_time, break_minutes, hourly_wage`）に揃い、日付が `2026-04-23`、時給が `1500` に正規化されていることを見せる。
5. **エラーハイライト（30秒）** — `/csv-convert samples/timesheet_202604_haken_c.csv` を実行。`out/timesheet_202604_haken_c_report.md` を開いて、「3行目の勤務日は『令和8年13月5日』で不正」のような要確認一覧を見せる。
6. **テンプレート保存（20秒）** — `/csv-save-template samples/timesheet_202604_haken_a.csv haken_a` で `templates/haken_a.json` を生成。
7. **翌月の再利用（30秒）** — `/csv-convert-with-template samples/timesheet_202605_haken_a.csv haken_a`。数秒で3行全て揃う。
8. **締め（20秒）** — 「主要な派遣元パターンに即応、残りはテンプレートで資産化」と着地。

---

## 実行結果サンプル（抜粋）

```
$ python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv

=== Before (masked, first 3 rows) ===
社員コード,氏名,勤務日,始業,終業,休憩,時給
EMP001,山田太郎,2026-04-23,09:00,18:00,60,1500
EMP002,佐藤花子,令和8年13月5日,10:00,19:00,60,1600
EMP003,,2026-04-23,09:00,08:00,60,1500

=== After (masked, first 3 rows) ===
employee_id,name,work_date,start_time,end_time,break_minutes,hourly_wage
EMP001,山***,2026-04-23,09:00,18:00,60,****
EMP005,高***,2026-04-24,09:00,18:00,60,****

=== Summary ===
input=5 output=2 dropped=3 review=3 (policy=drop)
関係式: input = output + dropped → 5 = 2 + 3 ✓
[OK] 出力: out/timesheet_202604_haken_c.csv
[OK] レポート: out/timesheet_202604_haken_c_report.md
```

レポート（`out/timesheet_202604_haken_c_report.md`）抜粋:

```markdown
## 要確認セル一覧
| 行 | 列 | 元の値 | 推定理由 |
|---|---|---|---|
| 3 | work_date | 令和8年13月5日 | 月が不正（13月は存在しない） |
| 4 | name | (空) | 必須項目が空欄 |
| 4 | end_time | 08:00 | 終業が始業より前（日またぎは自動補正せず要確認） |
| 5 | hourly_wage | abc円 | 数値に変換できない |
```

---

## 主なCLI

```bash
# 単発変換（既定ポリシー: drop = 要確認行を除外）
python3 src/main.py convert --input samples/timesheet_202604_haken_a.csv

# keep: 全行出力、要確認行は原値のまま＋末尾に __needs_review 列
python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv --error-policy keep

# fail: 要確認が1件でもあれば整形済CSV未出力・非ゼロ終了
python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv --error-policy fail

# ドライラン
python3 src/main.py convert --input samples/timesheet_202604_haken_a.csv --dry-run

# テンプレート保存 → 翌月適用
python3 src/main.py save-template --input samples/timesheet_202604_haken_a.csv --name haken_a --force
python3 src/main.py convert --input samples/timesheet_202605_haken_a.csv --template haken_a

# ディレクトリ一括
python3 src/main.py convert --input-dir samples/

# クリーンアップ（out/ と samples/tmp_* を削除）
python3 src/main.py cleanup --dry-run
python3 src/main.py cleanup
```

---

## スラッシュコマンド（Claude Code）

`.claude/commands/` 配下に以下を配置済み。

| コマンド | 役割 |
|---|---|
| `/csv-convert <input>` | 崩れCSVを標準スキーマに変換 |
| `/csv-save-template <input> <name>` | ヘッダーマッピングをテンプレート保存 |
| `/csv-convert-with-template <input> <name>` | テンプレート適用で一発変換 |
| `/csv-demo` | 全サンプルを順番に変換するセミナー一括実行 |

---

## ディレクトリ構成

```
01_csv-automation/
├── docs/                   # 要件定義・設計・仕様
├── src/
│   ├── main.py             # CLIDispatcher（エントリポイント）
│   ├── schema/canonical.py # 標準スキーマ定数
│   ├── flows/              # ConvertFlow / SaveTemplateFlow / CleanupFlow
│   ├── io/                 # EncodingDetector / TimesheetLoader / Writer
│   ├── mapping/            # HeaderInferencer + 同義語辞書 + 類似度
│   ├── normalize/          # date/time/number/text パーサ + Normalizer
│   ├── quality/            # ReviewCollector / ErrorPolicyApplier / Counters
│   ├── report/             # BillingReportGenerator（md / csv）
│   ├── template/           # TemplateStore（JSON読み書き）
│   ├── security/           # PIIMasker（氏名・時給マスク）
│   └── errors.py           # 例外階層
├── samples/                # 崩れCSVサンプル（パターンA/B/C＋翌月分）
├── templates/              # 保存済テンプレート（実行時生成）
├── out/                    # 整形済CSV・レポート（Git管理外想定）
├── .claude/commands/       # Claude Code スラッシュコマンド
└── README.md
```

---

## 標準スキーマ（canonical schema）

| 列 | 必須 | 備考 |
|---|---|---|
| `employee_id` | 必須 | 空欄は要確認 |
| `name` | 必須 | 空欄は要確認 |
| `work_date` | 必須 | `YYYY-MM-DD` に正規化 |
| `start_time` | 必須 | `HH:MM` |
| `end_time` | 必須 | `HH:MM`、`end < start` は要確認 |
| `break_minutes` | 任意 | 空欄は `0` に補完 |
| `hourly_wage` | 必須 | 整数。`￥`, `円`, `,` を剥がす |

## 片付け（デモ後）

```bash
python3 src/main.py cleanup        # out/ と samples/tmp_* を削除
# or
rm -rf out/* && touch out/.gitkeep
```
