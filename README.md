# AI × CS 活用デモ — クラウドスタッフィング向け

クラウドスタッフィング（人材派遣管理SaaS）向けの AI 活用アイデアを、実際に動くモックとして 4 本実装。セミナー実演用。

**全部 AI エージェント（Claude Code + Codex CLI）が作りました。** 制作プロセスは [PROCESS.md](./PROCESS.md) を参照。

---

## 🚀 1発起動

```bash
./launch-dashboard.sh
```

ブラウザが開いて、4 本のデモを切り替えられる統合ダッシュボード（`http://localhost:8765/`）が表示されます。

---

## 🤖 Claude Code で開いているあなたへ

> **AI assistant の方へ:** このセクションはあなたに向けた指示です。ユーザーから「このリポジトリを動かして」「セットアップして」「デモを見せて」といった依頼があれば、以下の手順で進めてください。

### 自動セットアップ・起動の手順

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

5. **個別デモの動作確認**（ユーザーが望めば）
   ```bash
   # 01 CSV加工
   cd 01_csv-automation && python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv && cd ..

   # 02 端数処理（月18,000円差の演出）
   cd 02_rounding-checker && python3 src/main.py compare \
     --config samples/rules/strict_1min.yml \
     --config samples/rules/employee_friendly.yml \
     --config samples/rules/company_friendly.yml \
     --punch 9:03,18:07 --hourly 1800 --break 60 && cd ..

   # 03 勤怠チェック
   cd 03_attendance-check && python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy && cd ..
   ```

### よくあるつまずきポイントと自動対処

| 症状 | 対処 |
|---|---|
| `python3: command not found` | macOS: `brew install python@3.11` / Linux: 各ディストリのパッケージ管理 |
| `Permission denied: ./launch-dashboard.sh` | `chmod +x launch-*.sh` |
| `Address already in use` | 別ポート: `PORT=9876 ./launch-dashboard.sh` |
| `03` で `exit code 2` | `--data-class dummy` が未指定。コマンドに付けて再実行 |
| 04 のHTML が file:// で印刷崩れ | ダッシュボード経由（http://）で開く |

### このリポジトリの構造の理解（Claude Code が最初に読むべき場所）

1. このファイル（README.md）
2. [PROCESS.md](./PROCESS.md) — どう作られたか（セミナーネタ）
3. [SEMINAR_GUIDE.md](./SEMINAR_GUIDE.md) — セミナー進行
4. [LAUNCH.md](./LAUNCH.md) — 各起動方法の詳細
5. 各プロジェクトの `docs/01_requirements.md`, `02_design.md`, `03_spec.md`

---

## 📦 4 つのデモ

| # | プロジェクト | 実装 | コア価値 |
|---|---|---|---|
| 01 | [CSV加工の完全自動化](./01_csv-automation/) | Python CLI | 派遣管理CSVの Excel手作業ゼロ・差戻し防止 |
| 02 | [端数処理チェッカー](./02_rounding-checker/) | Python CLI | 月次締め前の説明責任・誤請求防止（月18,000円差の可視化） |
| 03 | [勤怠チェック自動化](./03_attendance-check/) | Python CLI | 月次締め前の確認地獄解放（266→20件絞り込み） |
| ★ | [運用整備状況 簡易診断](./04_yesno-diagnosis/) | 単一HTML | 営業・導入支援の初回ヒアリング補助 |

ダッシュボード経由で全部同じ画面から試せます。

---

## 🏃 個別起動（ダッシュボードを使わない場合）

```bash
./launch-csv.sh         # 01 をターミナルで実行
./launch-rounding.sh    # 02 をターミナルで実行
./launch-attendance.sh  # 03 をターミナルで実行
./launch-yesno.sh       # 04 だけブラウザ起動（ポート8765）
./launch-all.sh         # メニュー形式でデモ選択
```

---

## 🛠 技術スタック

- **Python 3.10+** （標準ライブラリのみ、PyYAML があれば 02 で使用、無ければ内蔵 mini パーサにフォールバック）
- **Vanilla HTML/CSS/JS** （ダッシュボードも 04 も外部依存ゼロ）
- **ダッシュボードサーバ**: Python `http.server` ベースのカスタム実装（`dashboard/server.py`）
- **デフォルトポート**: 8765（環境変数 `PORT` で変更可）

---

## 📂 ディレクトリ構成

```
ai-demos/
├── README.md                   ← このファイル
├── PROCESS.md                  制作プロセスのメタ資料
├── SEMINAR_GUIDE.md            セミナー進行ガイド
├── LAUNCH.md                   各デモ起動方法の詳細
├── launch-dashboard.sh         統合ダッシュボード起動（推奨）
├── launch-csv.sh / launch-rounding.sh / launch-attendance.sh / launch-yesno.sh
├── launch-all.sh               メニュー形式ランチャー
├── dashboard/
│   ├── index.html              ルートダッシュボード（カードUI）
│   ├── 01.html / 02.html / 03.html    各デモ詳細画面
│   └── server.py               http.server ベースの API サーバ
├── .review-prompts/            Codex レビュー用プロンプト一式
├── 01_csv-automation/
│   ├── docs/                   要件・設計・仕様・レビュー履歴
│   ├── src/                    Python 実装（22 モジュール）
│   ├── samples/                崩れCSVサンプル 4 種
│   ├── .claude/commands/       スラッシュコマンド
│   └── README.md
├── 02_rounding-checker/        (同じ構造)
├── 03_attendance-check/        (同じ構造)
└── 04_yesno-diagnosis/
    ├── docs/
    ├── src/index.html          単一HTMLで完結（81KB）
    └── README.md
```

---

## 🎬 セミナー実演の流れ（推奨 35 分）

詳細は [SEMINAR_GUIDE.md](./SEMINAR_GUIDE.md):

1. 冒頭 3 分 — 派遣管理業務の課題提起
2. **01 CSV加工** 5 分 — Excel 手作業削減の体感
3. **02 端数処理** 7 分 — 「月 18,000 円差」の衝撃
4. **03 勤怠チェック** 9 分 — 「266→20 件」の絞り込み、3 者ワークフロー資料の自動生成
5. **04 運用整備診断** 8 分 — 5 分で運用整備パターンを判定
6. **隠し玉** 3 分 — 「このモック、全部 AI エージェントが作りました」（PROCESS.md）
7. 質疑 10 分以上

---

## ⚠️ 免責

- セミナー実演用の **モック** であり、実運用を想定したテスト・セキュリティ審査は未実施
- 派遣法関連の記述は一般論としての論点提示。個別事案の法的判断を代替しない
- サンプルデータは **すべて架空**。実在の企業・個人とは無関係
- 本リポジトリのコードは派遣管理業務への AI 活用アイデアを示すためのもの。そのままの本番運用はサポート外

---

## 🧠 AI エージェントで作るという体験

このリポジトリは、Claude Code（メイン）× Codex CLI（レビュアー）の相互レビューで、要件定義から実装まで数時間で構築されました。人間の指示回数は 10 回未満。詳しくは [PROCESS.md](./PROCESS.md)。

セミナーでは「これもAIが作ったんですよ」が一番のフックです。
