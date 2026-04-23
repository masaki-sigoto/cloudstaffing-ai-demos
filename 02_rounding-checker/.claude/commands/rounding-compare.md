---
description: 端数処理チェッカー compare — 2 ルール以上の支払額差をテーブル表示
---

# rounding-compare

複数ルール設定を並べて「同じ打刻でも丸め方式でこれだけ違う」を見せるセミナー映えコマンド。

使い方:

```
/rounding-compare <punch> <hourly>
```

実行する bash コマンド（3 ルール定番セット）:

```bash
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch {{punch}} --hourly {{hourly}} --break 60
```

期待出力: 1分=14,520円 / 増加方向=14,850円 / 減少方向=13,950円 → 最大差額 900円/日。
