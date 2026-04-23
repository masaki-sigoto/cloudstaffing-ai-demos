#!/usr/bin/env bash
# ============================================================
# AI × CS 活用デモ 統合ダッシュボード 起動スクリプト
#   - Python http.server ベース（カスタムハンドラ）
#   - デフォルトポート: 8765（環境変数 PORT で変更可）
#   - /api/demo/{01|02|03}/run で実CLIを subprocess 実行
#   - ブラウザ自動起動
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER="${SCRIPT_DIR}/dashboard/server.py"

PORT="${PORT:-8765}"

# 前提チェック
if [ ! -f "${SERVER}" ]; then
  echo "❌ ${SERVER} が見つかりません"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 が必要です（3.10 以上）"
  exit 1
fi

# ポート占有チェック
if lsof -i ":${PORT}" >/dev/null 2>&1; then
  echo "❌ ポート ${PORT} はすでに使用中です。"
  echo "   別ポート指定で再実行: PORT=9876 ./launch-dashboard.sh"
  exit 1
fi

URL="http://localhost:${PORT}/"

echo "============================================================"
echo "🚀 AI × CS 活用デモ 統合ダッシュボード"
echo "   URL:     ${URL}"
echo "   Root:    ${SCRIPT_DIR}"
echo "   API:     POST /api/demo/{01|02|03}/{run|...}"
echo "   Stop:    Ctrl+C"
echo "============================================================"

# ブラウザ自動オープン（macOS）
if command -v open >/dev/null 2>&1; then
  (sleep 1.5 && open "${URL}") &
fi

# サーバ起動
exec python3 "${SERVER}" "${PORT}"
