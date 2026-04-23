---
description: ダミーCSV（timesheet/applications/shifts/clients）を samples/ 配下に生成。10異常パターンを意図的に混入
---

# /generate-samples

セミナー用のダミー勤怠データを再生成する。10異常パターン全てを最低1件ずつ混入する。

## 実行

```bash
cd "/Users/apple/Library/Mobile Documents/com~apple~CloudDocs/管理フォルダ/01_会社別/クロスリンク/06_クラウドスタッフィング/ai-demos/03_attendance-check"
python3 src/main.py generate-samples --month 2026-04 --data-class dummy --count 12 --overwrite
```

## 引数

- `--month YYYY-MM` （必須）: 対象月
- `--data-class dummy` （必須）: ダミー以外は拒否
- `--count N`: スタッフ数（既定12）
- `--seed N`: 乱数シード（既定42、同一seed=同一出力）
- `--overwrite`: 既存ファイルがある場合に上書き

## 生成物

`samples/{YYYYMM}/` 配下：
- `timesheet.csv`: スタッフ打刻ペア（1行=1出退勤）
- `applications.csv`: 休暇／残業申請
- `shifts.csv`: シフト予定
- `clients.csv`: 派遣先マスター（ABC商事・XYZ物流・DEF製造）
