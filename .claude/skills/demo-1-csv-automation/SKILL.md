---
name: demo-1-csv-automation
description: クラウドスタッフィング AI デモ Demo 1「CSV加工の整形支援」をターミナルから起動・実行する。派遣元から届く崩れたCSV（列順・ヘッダー・日付形式・文字コードがバラバラ）を1コマンドで標準形式に整形するPython CLIデモ。ユーザーが「Demo 1」「CSV加工」「CSV整形」「派遣管理 CSV」「csv-automation」「launch-csv」を言及した時に使う。
---

# Demo 1: CSV加工の整形支援

派遣元から届く崩れた勤怠CSVを1コマンドで標準7列スキーマに整形するPython CLIデモ。整形は自動、要確認行のハイライトと最終確認は担当者が行う前提。

## 対象デモ
- **デモ名**: CSV加工の整形支援
- **格納場所**: `01_csv-automation/`（リポジトリルート `ai-demos/` 直下）
- **エントリーポイント**: `01_csv-automation/src/main.py`（CLI）

## 起動コマンド（推奨）

リポジトリルート（`ai-demos/`）から:

```bash
./launch-csv.sh
```

このスクリプトは内部で以下を実行する:
- `cd 01_csv-automation`
- `python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv` （エラー混入サンプルで Before/After をターミナルに表示）
- レポート(`out/*_report.md`)とサイドカーCSV(`out/*_needs_review.csv`)も生成して内容を表示

## 直接実行する場合（Skillを使わない代替）

```bash
cd 01_csv-automation
python3 src/main.py convert --input samples/timesheet_202604_haken_a.csv  # 列順逆転・CP932・令和・全角
python3 src/main.py convert --input samples/timesheet_202604_haken_b.csv  # BOM・全角・時間単位混在
python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv  # エラー混入（13月・未入力・abc円）
python3 src/main.py convert --input samples/timesheet_202605_haken_a.csv  # 翌月分（テンプレ適用デモ用）
```

サブコマンド: `convert` / `save-template` / `cleanup`。詳細は `01_csv-automation/README.md`。

## 停止方法

- ターミナル CLI のため、コマンド完了で自動終了（Ctrl+C は通常不要）
- 長時間処理は今のところなし（1ファイル数秒以内）

## 使用ポート

**なし**（純粋な CLI、サーバ起動なし）

## 必要な環境変数

**なし**（API キー・トークン等の秘密情報も不要）

## 実行前チェック

1. Python 3.10 以上（推奨 3.11.9）
   ```bash
   python3 --version
   ```
2. リポジトリルート `ai-demos/` にいること
   ```bash
   pwd
   ls launch-csv.sh   # あれば OK
   ```
3. スクリプトに実行権限
   ```bash
   ls -la launch-csv.sh   # `-rwxr-xr-x` を確認
   # なければ chmod +x launch-csv.sh
   ```

## 実行後の確認方法

- 標準出力に `=== After ===` セクションが表示される
- `01_csv-automation/out/timesheet_202604_haken_c.csv` が生成される
- `01_csv-automation/out/timesheet_202604_haken_c_report.md` がエラー検出レポートとして生成される
- 件数照合行 `関係式: input = output + dropped → 5 = 2 + 3 ✓` が表示される

## よくある失敗と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `python3: command not found` | Python 未インストール | `brew install python@3.11` |
| `Permission denied: ./launch-csv.sh` | 実行権限なし | `chmod +x launch-csv.sh` |
| `samples/timesheet_*.csv が見つかりません` | カレントディレクトリ違い | `cd ai-demos && ls 01_csv-automation/samples/` |
| `[ERROR] 入力 CSV が samples/ 配下にありません` | 仕様: samples/ 配下のみ受理 | `samples/` にコピーしてから `--input samples/<file>` |

## このSkillが起動された時のClaudeの振る舞い

1. ユーザーがリポジトリルート `ai-demos/` にいるか確認（`pwd` 実行）
2. `./launch-csv.sh` を実行
3. 実行結果のサマリ（input/output/dropped/review 件数、生成ファイルパス）をユーザーに報告
4. エラー時は「よくある失敗と対処」を参照しつつ原因を切り分けて報告
5. 次に試すべき他サンプル（haken_a/b/c/202605_a）の比較も提案できる

## 関連ファイル

- スクリプト: `ai-demos/launch-csv.sh`
- README: `ai-demos/01_csv-automation/README.md`
- スラッシュコマンド: `ai-demos/01_csv-automation/.claude/commands/csv-{convert,save-template,convert-with-template,demo}.md`
- サンプル: `ai-demos/01_csv-automation/samples/timesheet_202604_haken_{a,b,c}.csv`, `timesheet_202605_haken_a.csv`
