---
description: 端数処理チェッカー 7 分デモを一気通貫で実行
---

# rounding-demo

セミナー本番想定のフル実演。simulate → compare → explain の 3 ステップを順に実行します。

実行する bash コマンド:

```bash
echo "=== [ステップ1] 素の打刻（1 分単位フェア） ===" && \
python3 src/main.py simulate --config samples/rules/strict_1min.yml --punch 9:03,18:07 --hourly 1800 && \
echo "" && \
echo "=== [ステップ2] スタッフ有利（増加方向） ===" && \
python3 src/main.py simulate --config samples/rules/employee_friendly.yml --punch 9:03,18:07 --hourly 1800 && \
echo "" && \
echo "=== [ステップ3] ルール比較で衝撃演出 ===" && \
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60 && \
echo "" && \
echo "=== [ステップ4] 逆算チェック（なぜこの結果か） ===" && \
python3 src/main.py explain --config samples/rules/company_friendly.yml --punch 9:03,18:07 --hourly 1800 --demo
```

トークの流れは `README.md` のデモシナリオ節を参照。
