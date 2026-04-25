# 端数処理チェッカー (rounding-checker)

> 派遣管理 SaaS「クラウドスタッフィング」のセミナー実演用 MVP。
> 勤怠の**丸めルール**（15 分切上げ／切捨て／1 分単位など）を YAML で明文化し、
> 打刻 CSV と突き合わせて**月次締め前／契約前**にシミュレーション・可視化する CLI ツール。
>
> **計算は真理値表ベースのロジック処理。AI の自由判断ではない**ため、出力金額は誰が再計算しても同じ結果になります。

## プロジェクト概要

派遣元の**請求担当・給与担当**が避けて通れない「端数処理」を、**ロジック計算で透明化**して
請求書・給与明細の金額について「なぜその結果になったのか」を逆算で説明できるようにします。

- **契約登録時**: CS の案件ルール設定を試し打ちして事前レビュー
- **月次締め前**: 誤請求・給与差額支払いを未然に発見
- **派遣先への説明**: 「この金額はこのルールだからこうなる」を 1 画面で共有

**KEY MESSAGE**: *説明コスト削減* — ロジックが透明になるだけで現場の会話がラクになる。

## 同梱ルール（YAML）

| ルール | 内容 |
|---|---|
| `strict_1min.yml` | 1 分単位フェア（端数なし） |
| `employee_friendly.yml` | スタッフ有利の増加方向丸め |
| `company_friendly.yml` | 会社有利の減少方向丸め |
| `5min_round.yml` | 5 分単位丸め |
| `10min_round.yml` | 10 分単位丸め |

## 統合ダッシュボード経由の起動

リポジトリルートで `./launch-dashboard.sh` を起動後、ブラウザで以下にアクセス。

```
http://localhost:8765/dashboard/02.html
```

## クイックスタート

```bash
# 1) 素の打刻（1 分単位フェア）
python3 src/main.py simulate \
  --config samples/rules/strict_1min.yml \
  --punch 9:03,18:07 --hourly 1800

# 2) CSV 一括
python3 src/main.py simulate \
  --config samples/rules/employee_friendly.yml \
  --punch-file samples/punches_202604.csv \
  --hourly 1800

# 3) ルール比較（ルール間の差分を可視化）
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60

# 4) 逆算チェック（短縮デモ）
python3 src/main.py explain \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --demo

# 5) YAML ルール妥当性チェック
python3 src/main.py validate \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --config samples/rules/strict_1min.yml
```

## 動作要件

- **Python 3.10+**
- **PyYAML 6.0+（推奨）**

### PyYAML の扱い

本ツールは YAML 読み込みに PyYAML を使います。インストール方法:

```bash
pip install pyyaml
# or
python3 -m pip install --user pyyaml
# macOS で PEP 668 に阻まれたら
python3 -m pip install --user --break-system-packages pyyaml
```

**PyYAML が入らない環境でもフォールバック実装で動作します**（`src/main.py` に極小
YAML パーサを内蔵）。ただし対応書式は「シンプルな `key: value` と 1 段ネスト」のみで、
サンプル YAML 相当のもの専用です。本番的な YAML 機能（アンカー・リスト・多段ネスト）
が必要なら PyYAML を必ず入れてください。

## 派遣管理における位置付け

| フェーズ | シーン | ツールでできること |
|---|---|---|
| 案件登録 | 派遣先の端数処理希望を CS の案件ルールに落とす前 | `validate` + `simulate` で事前レビュー |
| 月次締め前 | CS 打刻を CSV で抽出し丸め後時間を確認 | `simulate --punch-file` で一括計算 |
| 派遣先説明 | 請求書の金額根拠を聞かれたとき | `explain` 通常モードで 5 ステップ説明 |
| 給与説明 | スタッフから「何でこの時間？」と聞かれたとき | `explain --demo` で 3 ステップ即答 |

CSV には**匿名 ID のみ**（氏名・派遣先社名は含めない）。PII 混入は設計レベルで阻止します。

## デモシナリオ（所要 7 分）

**基準条件**: 打刻 `9:03 / 18:07`・時給 `1,800円`・休憩固定 `60分`。

1. **ステップ 0（30 秒）**: 「9:03 に来て 18:07 に帰った。請求額と給与額、いくらでしょう？」
2. **ステップ 1（1 分）**: `simulate` with `strict_1min.yml` → Gross 9:04 / Net 8:04 / **14,520 円**
3. **ステップ 2（1 分）**: `simulate` with `employee_friendly.yml` → Net 8:15 / **14,850 円**
4. **ステップ 3（2 分）**: `compare` 3 ルール並列 → 最大 900 円差 / 月 20 日で **18,000 円**
5. **ステップ 4（2 分）**: `explain --demo` で逆算チェック。丸め 12 分 +(-)7 分 の内訳を日本語で
6. **ステップ 5（30 秒）**: 「ルールを明文化し、締め前にシミュレーションする。それだけ」

### 期待する「900 円/日違う」インパクト

| ルール | 支払対象時間 | 支払額 | 基準差 |
|---|---|---|---|
| 1 分単位（フェア） | 8:04 | 14,520 円 | ±0 |
| 増加方向（スタッフ有利） | 8:15 | 14,850 円 | **+330** |
| 減少方向（会社有利） | 7:45 | 13,950 円 | **-570** |

employee_friendly と company_friendly の差 = **900 円/日**、月 20 日換算で
**約 18,000 円**のブレ。派遣先 3 社・1 年運用なら**数十万円オーダー**の説明コストが
可視化されます。

## 提供スラッシュコマンド

| コマンド | 用途 |
|---|---|
| `/rounding-simulate` | 1 ルールで打刻を計算 |
| `/rounding-compare` | 複数ルールの支払額差 |
| `/rounding-explain` | 逆算説明（`--demo` 付き） |
| `/rounding-demo` | 一気通貫デモ（simulate → compare → explain） |

## ディレクトリ構成

```
02_rounding-checker/
├── README.md
├── docs/            # 要件・設計・技術仕様
├── src/
│   └── main.py      # 単一ファイル MVP 実装
├── samples/
│   ├── rules/
│   │   ├── strict_1min.yml
│   │   ├── employee_friendly.yml
│   │   ├── company_friendly.yml
│   │   ├── 5min_round.yml
│   │   └── 10min_round.yml
│   └── punches_202604.csv   # 派遣 3 名 × 5 日の匿名打刻
├── .claude/commands/         # スラッシュコマンド定義
└── out/                      # --out 出力先（空）
```

## 制約（MUST 範囲）

- 単発シフト（日跨ぎなし）のみ
- 固定休憩控除（複数回休憩は非対応）
- 法定内外・深夜割増は非対応（`overtime:` ブロックは WARN で読み捨て）
- 労基法の法解釈は扱わない（設定ルール通り計算するだけ）
- AI の自由判断ではなく**真理値表ベースのロジック計算**で処理。最終的な丸め後時間・金額の確認は担当者が行う

## 想定QA（3問）

- **Q. 同じ打刻・同じルールなら毎回同じ金額が出ますか？**
  A. はい。真理値表ベースのロジック処理のため、誰が再計算しても同じ結果になります。AI の自由判断は介在しません。
- **Q. 法定内外・深夜割増には対応しますか？**
  A. 本 MVP は単発シフト・固定休憩のみで、法定内外・深夜割増は非対応です（`overtime:` ブロックは WARN で読み捨て）。労基法の法解釈は扱わず、設定ルール通りに計算するだけです。
- **Q. employee_friendly と company_friendly のどちらが正しいのですか？**
  A. 優劣の話ではなく**ルールの明文化**が目的です。本ツールは派遣先・派遣元・スタッフ間で「どのルールで計算しているか」を可視化し、月次締め前の説明コストを下げます。最終的な金額確認は担当者が行います。
