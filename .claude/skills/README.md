# Demo Skills — 4 つのデモ起動 Skill 一覧

クラウドスタッフィング AI デモ 4 本を、Claude Code から迷わず起動するための Skill 定義集。

**配置場所**: `ai-demos/.claude/skills/`（プロジェクトスコープ）

## Skill 一覧

| No | Skill 名 | 対象デモ | 起動コマンド | 使用ポート | 環境変数 |
|---:|---|---|---|---|---|
| 1 | [demo-1-csv-automation](./demo-1-csv-automation/SKILL.md) | CSV加工の整形支援 | `./launch-csv.sh` | なし | なし |
| 2 | [demo-2-rounding-checker](./demo-2-rounding-checker/SKILL.md) | 端数処理チェッカー | `./launch-rounding.sh` | なし | なし |
| 3 | [demo-3-attendance-check](./demo-3-attendance-check/SKILL.md) | 勤怠チェック自動化 | `./launch-attendance.sh` | なし | なし |
| 4 | [demo-4-yesno-diagnosis](./demo-4-yesno-diagnosis/SKILL.md) | 運用整備状況 簡易診断 | `./launch-yesno.sh` | **8765**（HTTPサーバ） | `PORT`（任意） |

## 統一実行方法

### Claude Code 内から
ユーザーが「Demo 1 を起動して」「CSV加工のデモを実行」「launch-csv」等と言及すると、対応する Skill が自動でマッチして実行される。

### ターミナルから直接
リポジトリルート `ai-demos/` から:

```bash
./launch-csv.sh         # Demo 1
./launch-rounding.sh    # Demo 2
./launch-attendance.sh  # Demo 3
./launch-yesno.sh       # Demo 4（http://localhost:8765/index.html）
```

メニュー形式:

```bash
./launch-all.sh         # 1〜4 を選択して順次起動
```

統合ダッシュボード（4 デモを 1 画面で切り替え）:

```bash
./launch-dashboard.sh   # http://localhost:8765/
```

## 各 Skill 共通の前提

- **動作環境**: macOS / Linux + Python 3.10 以上
- **依存**: 標準ライブラリのみ（02 のみ PyYAML 任意、無くても内蔵 mini-parser で動作）
- **秘密情報**: 不要（API キー・トークン等は使わない）
- **サンプルデータ**: 全てダミー、実在の企業・個人とは無関係
- **リスクスタンス**: AI は確認作業を支援、最終確認・最終判断は担当者が行う

## 完了チェックリスト

| No | デモ名 | Skill 名 | 実行コマンド | 起動確認 | README 記載 | 備考 |
|---:|---|---|---|---|---|---|
| 1 | CSV加工の整形支援 | demo-1-csv-automation | `./launch-csv.sh` | ✅ | ✅ | exit 0、5→2件変換、要確認3件検出 |
| 2 | 端数処理チェッカー | demo-2-rounding-checker | `./launch-rounding.sh` | ✅ | ✅ | exit 0、月18,000円差を表示 |
| 3 | 勤怠チェック自動化 | demo-3-attendance-check | `./launch-attendance.sh` | ✅ | ✅ | exit 0、266→20件・通知3件・チェックリスト2件 |
| 4 | 運用整備状況 簡易診断 | demo-4-yesno-diagnosis | `./launch-yesno.sh` | ✅ | ✅ | HTTP 200、ポート 8765 |

## トラブル時の参照先

各 Skill の `SKILL.md` 内 「よくある失敗と対処」セクションを参照。

主要な落とし穴:
- `python3: command not found` → `brew install python@3.11`
- `Permission denied: ./launch-*.sh` → `chmod +x launch-*.sh`
- Demo 4 の `Address already in use` → `PORT=9876 ./launch-yesno.sh`
- Demo 3 の `exit code 2` → `--data-class dummy` 必須
