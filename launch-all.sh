#!/usr/bin/env bash
# ============================================================
# 全4デモ 一括起動メニュー
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

menu() {
  clear
  cat <<'EOF'
============================================================
  AI × CS 活用デモ 起動メニュー
============================================================

  [1] 01 CSV加工の完全自動化      (ターミナル表示)
  [2] 02 端数処理チェッカー         (ターミナル表示)
  [3] 03 勤怠チェック自動化         (ターミナル表示)
  [4] 04 運用整備状況 簡易診断      (ブラウザ起動, port 8765)
  [a] 01 → 02 → 03 を連続実行
  [q] 終了

============================================================
EOF
  printf "選択 > "
}

run_csv()        { "${SCRIPT_DIR}/launch-csv.sh"; }
run_rounding()   { "${SCRIPT_DIR}/launch-rounding.sh"; }
run_attendance() { "${SCRIPT_DIR}/launch-attendance.sh"; }
run_yesno()      { "${SCRIPT_DIR}/launch-yesno.sh"; }

run_all_terminal() {
  run_csv
  echo ""
  read -p "Enter キーで次のデモ (02 端数処理) へ…"
  run_rounding
  echo ""
  read -p "Enter キーで次のデモ (03 勤怠チェック) へ…"
  run_attendance
  echo ""
  echo "全デモ完了。04 はブラウザ起動なので [4] で個別に起動してください。"
}

while true; do
  menu
  read -r choice
  case "$choice" in
    1) run_csv; read -p "Enter で戻る…" ;;
    2) run_rounding; read -p "Enter で戻る…" ;;
    3) run_attendance; read -p "Enter で戻る…" ;;
    4) run_yesno ;;
    a|A) run_all_terminal; read -p "Enter で戻る…" ;;
    q|Q) echo "終了"; exit 0 ;;
    *) echo "無効な選択"; sleep 1 ;;
  esac
done
