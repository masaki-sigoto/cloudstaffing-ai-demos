---
description: 月次締め前の勤怠チェックを実行（10異常パターンを検知、要確認レコードを絞り込み）
---

# /attendance-check

派遣管理SaaSの月次締め前に、スタッフ打刻・申請・シフトを突合し、A-01〜A-10の10パターンを検知する。

## 実行

引数：`$ARGUMENTS`（例: `--month 2026-04 --as-of-date 2026-04-28 --data-class dummy`）

以下を順に実行してください：

1. プロジェクトディレクトリへ移動
   ```bash
   cd "/Users/apple/Library/Mobile Documents/com~apple~CloudDocs/管理フォルダ/01_会社別/クロスリンク/06_クラウドスタッフィング/ai-demos/03_attendance-check"
   ```
2. `samples/202604/` が無ければ `python3 src/main.py generate-samples --month 2026-04 --data-class dummy --count 12 --overwrite` で生成
3. `python3 src/main.py check $ARGUMENTS` を実行
4. 実行結果（サマリ・通知ファイルパス・処理時間）を要約して提示

## 既定推奨コマンド

引数未指定時は：
```
python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy
```

## 出力先

- `out/notifications/U-xxx_slug.txt`: 派遣元コーディネーター別通知
- `out/checklist/by_coordinator_YYYYMM.txt`: コーディネーター別チェックリスト
- `out/checklist/by_client_site_YYYYMM.txt`: 派遣先事業所別チェックリスト
- `out/result_YYYYMM.json`: 全Finding JSON
- `out/run_summary_YYYYMM.json`: 実行サマリJSON
- `out/skipped_records.csv`: 読込スキップ監査
