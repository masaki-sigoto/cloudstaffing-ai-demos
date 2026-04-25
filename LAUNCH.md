# LAUNCH — 各デモのモックを立ち上げる

各デモの起動方法を1ページにまとめたチートシート。

> **前提 CWD（共通）**: 本ドキュメントのコマンドはすべて `REPO_ROOT`（= `ai-demos/`）から実行します。最初に一度 `cd <REPO_ROOT>` した上で、以下のコマンドをコピペしてください。

---

## 推奨: 統合ダッシュボードで全部いっぺんに

```bash
# REPO_ROOT (= ai-demos/) で実行
./launch-dashboard.sh
# → http://localhost:8765/ がブラウザで開き、4本のデモを切替実行できる
```

`dashboard/server.py`（API 付き Python `http.server`）がブラウザから本物の CLI を実行する。
セミナー本番はこの統合ダッシュボードを推奨。

---

## TL;DR（コピペで個別に動かす）

```bash
# 前提: REPO_ROOT (= ai-demos/) にいる状態。各コマンドは終了時に REPO_ROOT に戻る。

# 01 CSV加工の整形支援 (4秒)
cd 01_csv-automation && python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv && cd ..

# 02 端数処理 (3秒) — 5ルール比較で「月18,000円差」演出
cd 02_rounding-checker && python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/5min_round.yml \
  --config samples/rules/10min_round.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60 && cd ..

# 03 勤怠チェック (1秒) — 全266件 → 要確認20件（高11/中8/低1）
cd 03_attendance-check && python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy && cd ..

# 04 運用整備状況 簡易診断（導入時 組織登録 判断支援）
./launch-yesno.sh
```

---

## プロジェクト別の立ち上げ方

### 01. CSV加工の整形支援（ポート不要 / ターミナル完結）

**前提 CWD**: `REPO_ROOT`（= `ai-demos/`）。下記コマンド冒頭の `cd 01_csv-automation` で対象プロジェクトに移動して実行します。

```bash
cd 01_csv-automation

# 基本: 1ファイル変換
python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv

# セミナー向け: エラー混入サンプルで一気通貫
python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv
cat out/timesheet_202604_haken_c_report.md   # レポート閲覧
python3 src/main.py save-template --input samples/timesheet_202604_haken_a.csv --name haken_a --force
python3 src/main.py convert --input samples/timesheet_202605_haken_a.csv --template haken_a
```

**出力先**: `out/*.csv` / `out/*_report.md` / `out/*_needs_review.csv`  
**サーバ不要 / ポート不要**

### 02. 端数処理チェッカー（ポート不要 / ターミナル完結）

**前提 CWD**: `REPO_ROOT`（= `ai-demos/`）から `cd 02_rounding-checker` で移動した状態。

利用可能な YAML ルール（**5 種**）:

- `strict_1min.yml` — 1 分単位の素計算（ベースライン）
- `5min_round.yml` — 5 分単位 round
- `10min_round.yml` — 10 分単位 round
- `employee_friendly.yml` — スタッフ有利の丸め
- `company_friendly.yml` — 派遣先（会社）有利の丸め

> 比較の使い分け: **標準=5ルール比較**（上記 5 種すべて。網羅的に説明したいとき） / **短縮=3ルール比較**（strict_1min × employee_friendly × company_friendly。「月18,000円差」インパクトに絞りたいとき）。
>
> 計算は **真理値表ベースのロジック処理**。AI の自由判断ではなく、設定したルールを厳密に適用する。

```bash
cd 02_rounding-checker

# セミナー映え: 5 ルール比較で「月18,000円差」を見せる
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/5min_round.yml \
  --config samples/rules/10min_round.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60

# 「月18,000円差」のコア演出は 1分単位 × スタッフ有利 × 派遣先有利 の3軸
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60

# 丸め単位だけを比べたいとき（1min vs 5min vs 10min）
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/5min_round.yml \
  --config samples/rules/10min_round.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60

# explain: 「なぜこの結果か」を3行で
python3 src/main.py explain --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --demo

# CSV 一括処理
python3 src/main.py simulate --config samples/rules/employee_friendly.yml \
  --punch-file samples/punches_202604.csv --hourly 1800
```

**出力先**: 標準出力  
**サーバ不要 / ポート不要**

### 03. 勤怠チェック自動化（ポート不要 / ターミナル完結）

**前提 CWD**: `REPO_ROOT`（= `ai-demos/`）から `cd 03_attendance-check` で移動した状態。

```bash
cd 03_attendance-check

# サンプル再生成（必要時のみ）
python3 src/main.py generate-samples --month 2026-04 --data-class dummy --count 12 --overwrite

# メイン: 勤怠チェック実行
python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy

# 生成された通知ファイル確認
cat out/notifications/U-001_sato.txt
cat out/checklist/by_client_site_202604.txt
```

**出力先**: `out/notifications/*.txt` / `out/checklist/*.txt` / `out/*.json`  
**サーバ不要 / ポート不要**

### 04. 運用整備状況 簡易診断（導入時 組織登録 判断支援）（ブラウザ起動）

**前提 CWD**: 方法 A はどこからでも可。方法 B は `REPO_ROOT`（= `ai-demos/`）で `./launch-yesno.sh`、または `04_yesno-diagnosis/src/` 配下で `python3 -m http.server` 直叩き。

単一HTMLで完結するため、**2通りの起動方法** があります。

#### 方法A: ダブルクリック（一番簡単）

Finder で以下のファイルをダブルクリック（`REPO_ROOT` = `ai-demos/` 配下）:

```
04_yesno-diagnosis/src/index.html
```

または `REPO_ROOT` から:

```bash
open 04_yesno-diagnosis/src/index.html
```

**メリット**: 起動 1 秒、ポート不使用、何もインストール不要  
**デメリット**: `file://` プロトコルで開くため、一部ブラウザで印刷時の挙動が微妙に違う場合あり

#### 方法B: ローカル HTTP サーバ経由（セミナー本番推奨）

`REPO_ROOT`（= `ai-demos/`）から起動スクリプトを使う:

```bash
# REPO_ROOT で実行
./launch-yesno.sh
# → http://localhost:8765/ が自動で開く
```

または手動で:

```bash
cd 04_yesno-diagnosis/src
python3 -m http.server 8765
# ブラウザで http://localhost:8765/index.html にアクセス
```

**メリット**: 印刷挙動が安定、セキュリティ警告が出ない  
**デメリット**: ポート 8765 を使う（停止は Ctrl+C）

**使用ポート**: `8765`（競合しにくいポート）
環境変数で変更可能: `PORT=8888 ./launch-yesno.sh`

---

## Claude Code のスラッシュコマンド経由で立ち上げる

各プロジェクトディレクトリで Claude Code を起動すると、`.claude/commands/` のスラッシュコマンドが使えます。

| プロジェクト | コマンド | 内容 |
|---|---|---|
| 01 | `/csv-convert` | 1ファイル変換 |
| 01 | `/csv-save-template` | テンプレート保存 |
| 01 | `/csv-demo` | 全サンプル一気通貫 |
| 02 | `/rounding-simulate` | シミュレート |
| 02 | `/rounding-compare` | ルール比較（標準=5ルール / 短縮=3ルール）。月18,000円差の演出は短縮3ルール（strict_1min × employee_friendly × company_friendly）で行う |
| 02 | `/rounding-explain` | 説明生成 |
| 02 | `/rounding-demo` | セミナー用一気通貫 |
| 03 | `/attendance-check` | 通常実行 |
| 03 | `/attendance-demo` | セミナー用インパクト出力 |
| 03 | `/generate-samples` | サンプル再生成 |
| 04 | `/yesno-open` | HTMLをブラウザで開く |
| 04 | `/yesno-demo` | デモ手順ガイド表示 |

Claude Code がセッション内で **`/〇〇`** と入力するだけでコマンド実行できます。

---

## ポート利用状況

| プロジェクト | 利用ポート | サーバ |
|---|---|---|
| 01 | — | なし（CLI） |
| 02 | — | なし（CLI） |
| 03 | — | なし（CLI） |
| 04 (方法A) | — | なし（file://） |
| 04 (方法B) | **8765**（デフォルト）/ 環境変数 `PORT` で変更可 | python3 http.server |

避けたメジャーポート: 3000/3001 (Node/React)、4000/4200 (Angular/Phoenix)、5000 (Flask)、5173 (Vite)、5500/5501 (VSCode Live Server)、8000 (Django/http)、8080 (Apache)、8081 (Jenkins)、8888 (Jupyter)、9000 (PHP-FPM/SonarQube) 等。

8765 は memorable で競合しにくい番号として採用。
要点: メジャーな開発ポート **3000 / 5000 / 8000 / 8080** との競合を避けるための選択。

---

## トラブルシュート

### `python3: command not found`
→ Homebrew で `brew install python@3.11`

### 04 方法B で「Address already in use」
→ 別のプロセスがポート 8765 を使用中。別ポート指定:
```bash
PORT=9876 ./launch-yesno.sh
```

### 01 で「samples/ 配下以外は読めない」エラー
→ 仕様通り、`samples/` 内のCSVのみ読み込み可能。デモ外のファイルを使いたいときは一度 `samples/` にコピー。

### 03 で `exit code 2`
→ `--data-class` の指定漏れ。`--data-class dummy` を付けて再実行。

### `/rounding-compare` で「期待通りの 900円差」が出ない
→ `--punch 9:03,18:07` と `--hourly 1800 --break 60` を必ず揃える。仕様書の基準シナリオ条件。
