---
description: 端数処理チェッカー simulate — 打刻CSV + YAMLルールで丸め後時間を可視化
---

# rounding-simulate

指定ルールで打刻データをシミュレートします。

使い方:

```
/rounding-simulate <rule_file> <punch_csv_or_hhmm> [hourly]
```

引数:
- `{{rule}}`: YAML ルールファイル（例: `samples/rules/employee_friendly.yml`）
- `{{csv}}`: 打刻CSV（`samples/punches_202604.csv`）または `9:03,18:07` 形式の単発打刻

実行する bash コマンド:

```bash
# CSV の場合
python3 src/main.py simulate --config {{rule}} --punch-file {{csv}} --hourly 1800

# 単発打刻の場合
python3 src/main.py simulate --config {{rule}} --punch {{csv}} --hourly 1800
```
