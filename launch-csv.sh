#!/usr/bin/env bash
# ============================================================
# 01 CSV加工の完全自動化 デモ起動スクリプト
#   - エラー混入サンプル(haken_c) を変換 → レポート表示
#   - ポート不使用、ターミナルのみで完結
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/01_csv-automation"

echo "============================================================"
echo "📋 01. CSV加工の完全自動化 デモ"
echo "   対象: samples/timesheet_202604_haken_c.csv (エラー混入)"
echo "============================================================"
echo ""
echo "▼ Before: 崩れた元CSV（派遣元から届いた状態）"
echo "------------------------------------------------------------"
cat samples/timesheet_202604_haken_c.csv
echo ""
echo "============================================================"
echo "▼ 変換実行: python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv"
echo "============================================================"
python3 src/main.py convert --input samples/timesheet_202604_haken_c.csv

echo ""
echo "============================================================"
echo "▼ After: 変換後の標準形式CSV (out/timesheet_202604_haken_c.csv)"
echo "------------------------------------------------------------"
cat out/timesheet_202604_haken_c.csv

echo ""
echo "============================================================"
echo "▼ エラー行レポート (抜粋)"
echo "------------------------------------------------------------"
head -60 out/timesheet_202604_haken_c_report.md

echo ""
echo "============================================================"
echo "✅ デモ完了"
echo "   - 変換後CSV: $(pwd)/out/timesheet_202604_haken_c.csv"
echo "   - レポート:   $(pwd)/out/timesheet_202604_haken_c_report.md"
echo "   - 要確認CSV: $(pwd)/out/timesheet_202604_haken_c_needs_review.csv"
echo "============================================================"
