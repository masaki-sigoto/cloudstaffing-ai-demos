---
description: 端数処理チェッカー explain — 「なぜこの結果か」を逆算で日本語説明
---

# rounding-explain

セミナー短縮 3 ステップモード（`--demo`）で、丸め・控除・最終値を表示します。

使い方:

```
/rounding-explain <punch> <rule_file>
```

実行する bash コマンド:

```bash
python3 src/main.py explain \
  --config {{rule}} \
  --punch {{punch}} \
  --hourly 1800 \
  --demo
```

通常モード（5 ステップ詳細）を使う場合は `--demo` を外してください。
