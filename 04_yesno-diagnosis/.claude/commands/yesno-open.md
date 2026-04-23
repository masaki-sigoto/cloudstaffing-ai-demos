---
description: 運用整備ナビゲーター（YES/NO 簡易診断アプリ）をブラウザで開く
---

# yesno-open

`04_yesno-diagnosis/src/index.html` をデフォルトブラウザで開きます。
単一HTMLファイルのため、`file://` プロトコルで直接起動します。

## 実行手順

以下のコマンドを Bash で実行してください。

```bash
open "/Users/apple/Library/Mobile Documents/com~apple~CloudDocs/管理フォルダ/01_会社別/クロスリンク/06_クラウドスタッフィング/ai-demos/04_yesno-diagnosis/src/index.html"
```

## 確認ポイント

- 免責バー（「本ツールは診断補助であり、法令判定ではありません」）が画面最上部に常時表示される
- スプラッシュで「保存しない（一時利用）」が初期選択されている
- 「ショート版で開始」ボタンが最も目立つCTA
- オフライン（ネット切断）でも動作する

## トラブルシュート

- ブラウザで開けない場合は、Finder から直接 `src/index.html` をダブルクリック
- `localStorage` が使えない環境（プライベートブラウジング等）では黄バナーが表示され、セッション中のみ回答保持となる
