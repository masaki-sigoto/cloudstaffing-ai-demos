#!/usr/bin/env bash
# ============================================================
# 02 端数処理チェッカー デモ起動スクリプト
#   - 3ルール比較で「月18,000円差」を演出
#   - ポート不使用、ターミナルのみで完結
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/02_rounding-checker"

echo "============================================================"
echo "💰 02. 端数処理チェッカー デモ"
echo "   シナリオ: 9:03出勤 / 18:07退勤 / 時給1,800円 / 休憩60分"
echo "============================================================"
echo ""
echo "▼ Step 1: 素の1分単位計算（フェア基準）"
echo "------------------------------------------------------------"
python3 src/main.py simulate --config samples/rules/strict_1min.yml --punch 9:03,18:07 --hourly 1800 --break 60 2>&1 | tail -20

echo ""
echo "============================================================"
echo "▼ Step 2: スタッフ有利ルール（出勤floor + 退勤ceil）"
echo "------------------------------------------------------------"
python3 src/main.py simulate --config samples/rules/employee_friendly.yml --punch 9:03,18:07 --hourly 1800 --break 60 2>&1 | tail -20

echo ""
echo "============================================================"
echo "▼ Step 3: 3ルール一括比較（セミナー映えのメイン）"
echo "------------------------------------------------------------"
python3 src/main.py compare \
  --config samples/rules/strict_1min.yml \
  --config samples/rules/employee_friendly.yml \
  --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --break 60

echo ""
echo "============================================================"
echo "▼ Step 4: explain で「なぜこの結果か」を3行で説明"
echo "------------------------------------------------------------"
python3 src/main.py explain --config samples/rules/company_friendly.yml \
  --punch 9:03,18:07 --hourly 1800 --demo 2>&1 | tail -30

echo ""
echo "============================================================"
echo "✅ デモ完了: 同じ打刻で **1日最大900円 / 月20日換算 18,000円** の差"
echo "============================================================"
