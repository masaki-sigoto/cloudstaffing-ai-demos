#!/usr/bin/env bash
# ============================================================
# 04 運用整備状況 簡易診断アプリ 起動スクリプト
#   - ローカル HTTP サーバ（python3 http.server）を起動
#   - デフォルトポート: 8765（環境変数 PORT で変更可）
#   - ブラウザを自動で開く
#   - Ctrl+C で停止
# ============================================================

set -e

# プロジェクトルート解決（このスクリプトの場所基準）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YESNO_DIR="${SCRIPT_DIR}/04_yesno-diagnosis/src"

# ポート設定（デフォルト 8765、環境変数で上書き可）
PORT="${PORT:-8765}"

# ポート占有チェック
if lsof -i ":${PORT}" >/dev/null 2>&1; then
  echo "❌ ポート ${PORT} はすでに使用中です。"
  echo "   別ポート指定で再実行: PORT=9876 ./launch-yesno.sh"
  exit 1
fi

# ディレクトリ存在確認
if [ ! -f "${YESNO_DIR}/index.html" ]; then
  echo "❌ ${YESNO_DIR}/index.html が見つかりません"
  exit 1
fi

URL="http://localhost:${PORT}/index.html"

echo "============================================================"
echo "🚀 運用整備状況 簡易診断アプリ 起動"
echo "   URL:    ${URL}"
echo "   Serve:  ${YESNO_DIR}"
echo "   Stop:   Ctrl+C"
echo "============================================================"

# ブラウザ自動オープン（macOS）
if command -v open >/dev/null 2>&1; then
  (sleep 1 && open "${URL}") &
fi

# HTTP サーバ起動（python3 標準ライブラリ）
cd "${YESNO_DIR}"
exec python3 -m http.server "${PORT}"
