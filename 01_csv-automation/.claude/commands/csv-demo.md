---
description: 全サンプルCSVを一気に変換してセミナーデモを再現
---

以下を順番に実行し、それぞれの変換結果・件数サマリ・エラー検出を簡潔に伝えてください:

1. `python3 src/main.py convert --input samples/timesheet_202604_haken_a.csv`
2. `python3 src/main.py convert --input samples/timesheet_202604_haken_b.csv`
3. `python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv`
4. `python3 src/main.py save-template --input samples/timesheet_202604_haken_a.csv --name haken_a --force`
5. `python3 src/main.py convert --input samples/timesheet_202605_haken_a.csv --template haken_a`

各ステップで「Before の崩れ」「After の揃い」「検出できた要確認セル」を 1-2 行にまとめるとセミナー映えします。
