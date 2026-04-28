---
name: demo-4-yesno-diagnosis
description: クラウドスタッフィング AI デモ Demo 4「運用整備状況 簡易診断（導入時 組織登録 判断支援）」をブラウザで起動・実行する。YES/NO 質問に答えると派遣管理運用パターン A〜E を判定する単一HTMLデモ。最終的な組織登録は担当者が確認のうえ決定する前提。ローカル HTTP サーバ（デフォルトポート 8765）で起動する。ユーザーが「Demo 4」「YES/NO診断」「運用整備診断」「組織登録判断」「yesno-diagnosis」「launch-yesno」を言及した時に使う。
---

# Demo 4: 運用整備状況 簡易診断（導入時 組織登録 判断支援）

クラウドスタッフィング導入時の組織登録設計を、YES/NO 質問で判断支援する単一HTMLデモ。**ショート版7問固定／フル版 最大15問（分岐により実際の出題は11〜13問）**。結果は推奨パターン提示（A: 基本整備型 / B: 複数拠点対応型 / C: 将来拡張対応型 / D: 多事業所分散型 / E: 法対応要整備型）。**最終的な組織登録は担当者が確認のうえ決定**する前提。

## 対象デモ
- **デモ名**: 運用整備状況 簡易診断（導入時 組織登録 判断支援）
- **格納場所**: `04_yesno-diagnosis/`（リポジトリルート `ai-demos/` 直下）
- **エントリーポイント**: `04_yesno-diagnosis/src/index.html`（単一HTML、約81KB、外部依存ゼロ、オフライン動作）

## 起動コマンド（推奨）

リポジトリルート（`ai-demos/`）から:

```bash
./launch-yesno.sh
```

このスクリプトは内部で以下を実行する:
1. ポート 8765 の占有チェック（占有時はエラー終了、別ポート指定を案内）
2. `python3 -m http.server 8765` を `04_yesno-diagnosis/src/` から起動
3. macOS では `open http://localhost:8765/index.html` でブラウザ自動起動
4. Ctrl+C で停止

## 直接実行する場合（Skillを使わない代替）

### 方法 A: ダブルクリック（最も簡単）
```bash
open ai-demos/04_yesno-diagnosis/src/index.html
```
`file://` プロトコルで開く。ポート不使用、何もインストール不要。

### 方法 B: ローカル HTTP サーバ（セミナー本番推奨）
```bash
cd ai-demos/04_yesno-diagnosis/src
python3 -m http.server 8765
# ブラウザで http://localhost:8765/index.html
```

## 停止方法

- **方法 A**: ブラウザのタブを閉じるだけ
- **方法 B / launch-yesno.sh**: `Ctrl+C` でサーバ停止
  - バックグラウンド起動した場合: `lsof -ti :8765 | xargs kill`

## 使用ポート

**8765**（HTTP サーバ経由のときのみ）。`file://` で直接開く場合はポート不使用。

メジャー開発ポート（3000/5000/8000/8080 等）と競合しないよう選定。

## 必要な環境変数

- `PORT` （任意、デフォルト 8765）: 別ポートで起動したい場合のみ
  ```bash
  PORT=9876 ./launch-yesno.sh
  ```
- 秘密情報（API キー等）は **不要**

## 実行前チェック

1. Python 3.10 以上（HTTP サーバ用、`python3 -m http.server` を内部で使う）
   ```bash
   python3 --version
   ```
2. リポジトリルート `ai-demos/` にいること
3. ポート 8765 が空いていること
   ```bash
   lsof -i :8765   # 何も出なければOK
   ```
4. 単一HTMLが存在すること
   ```bash
   ls -la 04_yesno-diagnosis/src/index.html   # 約 81KB
   ```

## 実行後の確認方法

- ターミナルに `Serving HTTP on 0.0.0.0 port 8765` が表示
- ブラウザで `http://localhost:8765/index.html` にアクセス
- スプラッシュ画面に「運用整備ナビゲーター」「CLOUD STAFFING / 導入時 組織登録 判断支援」のブランドバッジ
- ショート版（7問）/ フル版（最大15問）の選択肢が表示される
- 質問に YES/NO で回答すると、結果画面でパターン A〜E のいずれかが提示される

## よくある失敗と対処

| 症状 | 原因 | 対処 |
|---|---|---|
| `python3: command not found` | Python 未インストール | `brew install python@3.11` |
| `Address already in use` | ポート 8765 が使用中 | `PORT=9876 ./launch-yesno.sh` で別ポート、または `lsof -ti :8765 \| xargs kill` |
| ブラウザが自動で開かない | macOS 以外、または `open` コマンド失敗 | 手動で `http://localhost:8765/index.html` にアクセス |
| 印刷時に表示が崩れる | `file://` 経由特有の挙動 | 方法 B（HTTP サーバ）で開き直す |
| ファイル直接アクセスでも CSS/JS が動かない | きわめて古いブラウザ | Chrome 120+/Edge 120+/Safari 17+/Firefox 120+ を使用 |

## このSkillが起動された時のClaudeの振る舞い

1. ユーザーがリポジトリルート `ai-demos/` にいるか確認
2. ポート 8765 の占有確認（占有時は別ポート提案）
3. `./launch-yesno.sh` を実行（バックグラウンド起動も検討、永続デモ用なら `nohup` 推奨）
4. ブラウザに表示される URL（`http://localhost:8765/index.html`）をユーザーに案内
5. ユーザーが画面を見る前に「ショート版/フル版どちらを試したいか」「セミナーシナリオ動線を見たいか」を確認
6. セミナーシナリオ動線: Q2=Y → Q3=Y → Q5=Y → Q12=Y → Q13=労使協定 → Q6=N → Q15=Y で **パターンC（将来拡張対応型）** に着地
7. 停止指示を受けたら `lsof -ti :8765 | xargs kill` で停止

## 関連ファイル

- スクリプト: `ai-demos/launch-yesno.sh`
- README: `ai-demos/04_yesno-diagnosis/README.md`
- スラッシュコマンド: `ai-demos/04_yesno-diagnosis/.claude/commands/{yesno-open,yesno-demo}.md`
- HTMLファイル: `ai-demos/04_yesno-diagnosis/src/index.html`（単一ファイル完結）
