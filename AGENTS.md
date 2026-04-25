# AGENTS — AI アシスタント向けオペレーション手順

> このファイルは Claude Code などの AI アシスタント専用の運用手順書です。**NotebookLM 投入対象外**（投入対象は `README.md` / `PROCESS.md` / `SEMINAR_GUIDE.md` / `LAUNCH.md` / `NOTEBOOKLM_KNOWLEDGE.md` の 5 本固定。詳細は [README.md の「AI アシスタント向け運用手順」](./README.md) 参照）。リポジトリを開いた AI がセットアップ・起動を行うときだけ参照してください。

## リスク表現ガイド（厳守）

本デモを説明する際は以下を遵守してください。

- 採用する表現: 「AI が確認作業を支援」「不一致の可能性がある箇所を抽出」「最終確認は担当者が行う」「正確性が必要な部分はロジックで処理」
- 避ける表現: 過度な自動化表現（AI 単独での確定、担当者の確認不要を示唆する文言）
- **明示的 NG 表現**: 「ミスゼロ」「100%」「完全自動」「AI が判定／確定」「人の確認は不要」「自動で確定」（断定的な精度・完全性主張は使用しない）

## 自動セットアップ・起動の手順

前提 CWD: `REPO_ROOT`（= `ai-demos/`）。本書のコマンドはすべて `REPO_ROOT` 起点で記述します。

1. **前提チェック**
   ```bash
   python3 --version   # 3.10 以上か確認
   which python3
   ```
   - `python3` が見つからない → ユーザーに `brew install python@3.11` の実行を依頼
   - 3.10 未満 → 同上

2. **実行権限付与**（初回のみ）
   ```bash
   chmod +x launch-*.sh dashboard/server.py 2>/dev/null || true
   ```

3. **ポート競合チェック**
   ```bash
   lsof -i :8765 | head -1
   ```
   - 何か出たら `PORT=9876 ./launch-dashboard.sh` のような別ポート指定を提案

4. **ダッシュボード起動**
   ```bash
   ./launch-dashboard.sh
   ```
   - 自動でブラウザが開き、`http://localhost:8765/` が表示される
   - 出ない場合はユーザーに URL を案内して手動で開いてもらう

5. **個別デモの動作確認**（ユーザーが望めば。前提 CWD: `REPO_ROOT` = `ai-demos/`）
   ```bash
   # 01 CSV加工の整形支援
   cd 01_csv-automation && python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv && cd ..

   # 02 端数処理（月18,000円差の演出。標準=5ルール比較）
   cd 02_rounding-checker && python3 src/main.py compare \
     --config samples/rules/strict_1min.yml \
     --config samples/rules/5min_round.yml \
     --config samples/rules/10min_round.yml \
     --config samples/rules/employee_friendly.yml \
     --config samples/rules/company_friendly.yml \
     --punch 9:03,18:07 --hourly 1800 --break 60 && cd ..

   # 03 勤怠チェック
   cd 03_attendance-check && python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy && cd ..
   ```

## よくあるつまずきポイントと自動対処

| 症状 | 対処 |
|---|---|
| `python3: command not found` | macOS: `brew install python@3.11` / Linux: 各ディストリのパッケージ管理 |
| `Permission denied: ./launch-dashboard.sh` | `chmod +x launch-*.sh` |
| `Address already in use` | 別ポート: `PORT=9876 ./launch-dashboard.sh` |
| `03` で `exit code 2` | `--data-class dummy` が未指定。コマンドに付けて再実行 |
| 04 のHTML が file:// で印刷崩れ | ダッシュボード経由（http://）で開く |

## このリポジトリの構造の理解

1. [README.md](./README.md) — 4本のデモ概要と説明資料
2. [PROCESS.md](./PROCESS.md) — どう作られたか（セミナーネタ）
3. [SEMINAR_GUIDE.md](./SEMINAR_GUIDE.md) — セミナー進行
4. [LAUNCH.md](./LAUNCH.md) — 各起動方法の詳細
5. 各プロジェクトの `docs/01_requirements.md`, `02_design.md`, `03_spec.md`
