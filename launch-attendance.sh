#!/usr/bin/env bash
# ============================================================
# 03 勤怠チェック自動化 デモ起動スクリプト
#   - 266件 → 要確認20件 の絞り込みインパクト
#   - 担当者別通知・派遣先事業所別チェックリスト生成
#   - ポート不使用、ターミナルのみで完結
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/03_attendance-check"

echo "============================================================"
echo "📊 03. 勤怠チェック自動化 デモ"
echo "   対象: 2026-04 月次締め前 (as-of 2026-04-28)"
echo "   スタッフ12名 × 1ヶ月分 (266件) の打刻データ"
echo "============================================================"
echo ""

# サンプルがなければ生成
if [ ! -f samples/202604/timesheet.csv ]; then
  echo "▼ サンプル未生成のため generate-samples を実行"
  python3 src/main.py generate-samples --month 2026-04 --data-class dummy --count 12 --overwrite
  echo ""
fi

echo "▼ Before: 「従来はこの266件を全件目視でチェックしていた…」"
echo "------------------------------------------------------------"
echo "  打刻データ件数: $(wc -l < samples/202604/timesheet.csv) 行 (ヘッダー含む)"
echo "  申請データ件数: $(wc -l < samples/202604/applications.csv) 行"
echo "  シフトデータ:   $(wc -l < samples/202604/shifts.csv) 行"
echo ""

echo "============================================================"
echo "▼ 実行: python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy"
echo "============================================================"
python3 src/main.py check --month 2026-04 --as-of-date 2026-04-28 --data-class dummy

echo ""
echo "============================================================"
echo "▼ 生成されたコーディネーター別通知（抜粋: U-001 佐藤さん宛）"
echo "------------------------------------------------------------"
if [ -f out/notifications/U-001_sato.txt ]; then
  head -30 out/notifications/U-001_sato.txt
else
  ls out/notifications/ 2>/dev/null | head -5
fi

echo ""
echo "============================================================"
echo "▼ 派遣先事業所別チェックリスト（抜粋）"
echo "------------------------------------------------------------"
if [ -f out/checklist/by_client_site_202604.txt ]; then
  head -30 out/checklist/by_client_site_202604.txt
fi

echo ""
echo "============================================================"
echo "✅ デモ完了: 全266件 → AIが拾った要確認 20件 に絞り込み"
echo "   - 通知:       $(pwd)/out/notifications/ (3ファイル)"
echo "   - チェックリスト: $(pwd)/out/checklist/ (2ファイル)"
echo "   - JSON結果:    $(pwd)/out/result_202604.json"
echo "   - 実行サマリ:   $(pwd)/out/run_summary_202604.json"
echo "============================================================"
