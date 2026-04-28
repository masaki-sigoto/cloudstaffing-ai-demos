---
name: demo-3-attendance-check
description: クラウドスタッフィング AI デモ Demo 3「勤怠チェック自動化」をターミナルから起動・実行する。月次締め前にスタッフ打刻・申請・シフト・派遣先承認を突合し、要確認候補を抽出するPython CLIデモ。10異常パターン（A-01〜A-10）を検知し、3者ワークフロー（スタッフ/派遣元/派遣先承認者）の差戻し起票資料を自動生成する。最終確認は担当者が行う前提。ユーザーが「Demo 3」「勤怠チェック」「異常検知」「266→20件」「attendance-check」「launch-attendance」を言及した時に使う。
---

# Demo 3: 勤怠チェック自動化

派遣管理 SaaS 上のスタッフ打刻・申請・シフト・派遣先承認データを突合し、月次締め前に「要確認候補」だけを抽出するPython CLIデモ。AI が候補を抽出 → 担当者が最終確認、というワークフロー前提。3 者ワークフローの差戻し起票情報まで整形して出力する。

## 対象デモ
- **デモ名**: 勤怠チェック自動化
- **格納場所**: `03_attendance-check/`（リポジトリルート `ai-demos/` 直下）
- **エントリーポイント**: `03_attendance-check/src/main.py`（CLI）

## 起動コマンド（推奨）

リポジトリルート（`ai-demos/`）から:

```bash
./launch-attendance.sh
```

このスクリプトは内部で以下を実行する:
1. `cd 03_attendance-check`
2. `samples/202604/timesheet.csv` 等のサンプル不在時は `python3 src/main.py generate-samples` で再生成
3. Before表示（行数表示で「266 件を全件目視で…」を演出）
4. `python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy` を実行
5. 担当者別通知ファイル（`out/notifications/U-001_sato.txt` 等）の抜粋を表示
6. 派遣先事業所別チェックリスト（`out/checklist/by_client_site_202604.txt`）の抜粋を表示

## 直接実行する場合（Skillを使わない代替）

```bash
cd 03_attendance-check

# サンプル再生成（10異常パターン混入）
python3 src/main.py generate-samples --month 2026-04 --data-class dummy --count 12 --overwrite

# メイン実行
python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy

# 結果確認
cat out/notifications/U-001_sato.txt
cat out/checklist/by_client_site_202604.txt
```

サブコマンド: `check` / `generate-samples`。詳細は `03_attendance-check/README.md`。

## 10異常パターン

| ID | 内容 | 重要度 |
|---|---|---|
| A-01 | 退勤打刻漏れ（出勤のみ） | 高 |
| A-02 | 出勤打刻漏れ（退勤のみ） | 高 |
| A-03 | 休憩未入力 | 中 |
| A-04 | 連続24時間以上の勤務 | 高 |
| A-05 | 1日複数回の出退勤 | 低 |
| A-06 | 申請×実績不整合 | 高 |
| A-07 | 派遣先承認待ち滞留（3営業日以上） | 中 |
| A-08 | 深夜打刻（シフト外） | 中 |
| A-09 | シフトとの大幅乖離（±60分超） | 中 |
| A-10 | 重複打刻（5分以内） | 高 |

## 停止方法

- ターミナル CLI のため、コマンド完了で自動終了

## 使用ポート

**なし**（CLI、サーバ起動なし）

## 必要な環境変数

**なし**。ただし以下のフラグでデータ種別を明示する仕様（実データ防波堤）:
- `--data-class dummy`: ダミーデータ用（必須、未指定時 exit 2）
- `--data-class real`: 実データ用（同時に `--allow-real-data` 必須）
- `--no-mask-names` 指定時は `--confirm-unmask-real` も必要

## 実行前チェック

1. Python 3.10 以上
   ```bash
   python3 --version
   ```
2. リポジトリルート `ai-demos/` にいること
3. `03_attendance-check/samples/202604/` にダミーデータがあること（無ければスクリプトが自動生成）

## 実行後の確認方法

- 標準出力に `全 266 件 → 要確認 20 件 [高] 11 件 / [中] 8 件 / [低] 1 件` が表示
- `03_attendance-check/out/notifications/U-001_sato.txt` 等が生成
- `03_attendance-check/out/checklist/by_coordinator_202604.txt` と `by_client_site_202604.txt` が生成
- `03_attendance-check/out/result_202604.json` と `run_summary_202604.json` が生成
- exit code 0

## よくある失敗と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `python3: command not found` | Python 未インストール | `brew install python@3.11` |
| `exit code 2` | `--data-class` 未指定 | コマンドに `--data-class dummy` を追加 |
| `samples/202604/timesheet.csv が見つかりません` | サンプル未生成 | `python3 src/main.py generate-samples --month 2026-04 --data-class dummy --count 12 --overwrite` |
| 件数が 266 と違う | seed 違いまたは別月 | seed 42 / month 2026-04 を確認 |

## このSkillが起動された時のClaudeの振る舞い

1. ユーザーがリポジトリルート `ai-demos/` にいるか確認
2. `./launch-attendance.sh` を実行
3. 「全 266 件 → 要確認 20 件（高 11 / 中 8 / 低 1）」を強調しつつサマリ報告
4. 通知ファイル・チェックリストの存在を確認して件数とパスを報告
5. 「最終確認は担当者が行う」前提を必ず添える（リスク表現ガイド遵守）
6. エラー時は「よくある失敗と対処」を参照しつつ原因切り分け

## 関連ファイル

- スクリプト: `ai-demos/launch-attendance.sh`
- README: `ai-demos/03_attendance-check/README.md`
- スラッシュコマンド: `ai-demos/03_attendance-check/.claude/commands/{attendance-check,attendance-demo,generate-samples}.md`
- サンプル: `ai-demos/03_attendance-check/samples/202604/{timesheet,applications,shifts,clients}.csv`
- 出力先: `ai-demos/03_attendance-check/out/{notifications,checklist}/`, `result_*.json`, `run_summary_*.json`
