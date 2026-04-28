---
name: demo-2-rounding-checker
description: クラウドスタッフィング AI デモ Demo 2「端数処理チェッカー」をターミナルから起動・実行する。打刻と丸めルール（1分/5分/10分/15分など）から請求・給与の差を可視化し、月20日換算で18,000円差まで演出するPython CLIデモ。計算は真理値表ベースのロジック処理（AIの自由判断ではない）。ユーザーが「Demo 2」「端数処理」「丸め」「rounding-checker」「launch-rounding」「月18,000円差」を言及した時に使う。
---

# Demo 2: 端数処理チェッカー

派遣管理の月次締め前に、丸めルールの違いで請求・給与がどう変わるかを可視化するPython CLIデモ。計算は **真理値表ベースのロジック処理** で、AI の自由判断ではない。

## 対象デモ
- **デモ名**: 端数処理チェッカー
- **格納場所**: `02_rounding-checker/`（リポジトリルート `ai-demos/` 直下）
- **エントリーポイント**: `02_rounding-checker/src/main.py`（CLI）

## 起動コマンド（推奨）

リポジトリルート（`ai-demos/`）から:

```bash
./launch-rounding.sh
```

このスクリプトは内部で以下を実行する:
1. `cd 02_rounding-checker`
2. **Step 1**: 1分単位（フェア基準）でシミュレーション
3. **Step 2**: スタッフ有利ルール（出勤floor + 退勤ceil）でシミュレーション
4. **Step 3**: 3ルール一括比較で `--punch 9:03,18:07 --hourly 1800 --break 60` の場合の月18,000円差を表示
5. **Step 4**: explain --demo で「なぜこの結果か」を3行で説明

## 直接実行する場合（Skillを使わない代替）

```bash
cd 02_rounding-checker

# 5ルール一括比較（最も豊富）
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/5min_round.yml \
  --config samples/rules/10min_round.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60

# 「月18,000円差」を強調する3軸比較
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60

# 説明生成
python3 src/main.py explain --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --demo
```

サブコマンド: `simulate` / `compare` / `explain` / `validate`。詳細は `02_rounding-checker/README.md`。

## 利用可能な YAML ルール（5種）

- `samples/rules/strict_1min.yml` — 1分単位（フェア基準）
- `samples/rules/5min_round.yml` — 5分丸め（四捨五入）
- `samples/rules/10min_round.yml` — 10分丸め（四捨五入）
- `samples/rules/employee_friendly.yml` — 15分単位スタッフ有利
- `samples/rules/company_friendly.yml` — 15分単位会社有利

## 停止方法

- ターミナル CLI のため、コマンド完了で自動終了

## 使用ポート

**なし**（CLI、サーバ起動なし）

## 必要な環境変数

**なし**

## 実行前チェック

1. Python 3.10 以上
   ```bash
   python3 --version
   ```
2. リポジトリルート `ai-demos/` にいること
3. PyYAML はあれば使うが、無くても内蔵 mini-parser で動作（README に明記）
   ```bash
   python3 -c "import yaml" 2>&1 | head -1   # 失敗してもOK（fallback あり）
   ```

## 実行後の確認方法

- 比較表に `1分単位（フェア）` `15分丸め（増加方向）` `15分丸め（減少方向）` の3行が表示
- `ルール間 最大差額: 900円（月20日換算: 18,000円）` の行が表示される
- exit code 0

## よくある失敗と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `python3: command not found` | Python 未インストール | `brew install python@3.11` |
| `[ERROR] unit_minutes must be 1/5/10/15/30/60` | 想定外の丸め単位指定 | YAML の `unit_minutes` を許容値に修正 |
| 「期待通りの900円差が出ない」 | 引数欠如 | `--punch 9:03,18:07 --hourly 1800 --break 60` を必ず揃える |
| `--punch must be 'HH:MM,HH:MM'` が CSV path で出る | フラグ間違い | CSV は `--punch-file <path>`、単発打刻は `--punch HH:MM,HH:MM` |

## このSkillが起動された時のClaudeの振る舞い

1. ユーザーがリポジトリルート `ai-demos/` にいるか確認
2. `./launch-rounding.sh` を実行
3. Step 1〜4の実行結果を要約して報告（特に「最大差額: 900円/日（月20日換算: 18,000円）」を強調）
4. ユーザーから「他の打刻でも試したい」と要求があれば `--punch` 値を変えて compare を再実行
5. エラー時は「よくある失敗と対処」を参照しつつ原因を切り分け

## 関連ファイル

- スクリプト: `ai-demos/launch-rounding.sh`
- README: `ai-demos/02_rounding-checker/README.md`
- スラッシュコマンド: `ai-demos/02_rounding-checker/.claude/commands/rounding-{simulate,compare,explain,demo}.md`
- YAMLルール: `ai-demos/02_rounding-checker/samples/rules/*.yml`
