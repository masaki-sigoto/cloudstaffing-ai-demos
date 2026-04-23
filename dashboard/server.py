#!/usr/bin/env python3
"""
AI × CS 活用デモ 統合ダッシュボード サーバ

http.server ベースのシンプルな API + 静的ファイル配信。
POST /api/demo/{01|02|03}/run で各 CLI を subprocess 実行、結果を JSON 返却。
GET /api/demo/{01|02|03}/file?path=... で生成ファイルのテキスト返却。
他は普通の静的ファイル配信。

使用方法:
    python3 dashboard/server.py [port]
    または
    ./launch-dashboard.sh
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# プロジェクトルート = このファイルの親の親 (ai-demos/)
REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_01 = REPO_ROOT / "01_csv-automation"
PROJECT_02 = REPO_ROOT / "02_rounding-checker"
PROJECT_03 = REPO_ROOT / "03_attendance-check"


# ============================================================
# デモ実行ハンドラ: 各デモごとに subprocess でCLIを呼び出す
# ============================================================


def run_demo_01(payload: dict) -> dict:
    """01 CSV加工: convert サブコマンドを実行"""
    sample = payload.get("sample", "timesheet_202604_haken_c.csv")
    sample_path = f"samples/{sample}"
    cmd = ["python3", "src/main.py", "convert", "--input", sample_path]

    proc = subprocess.run(
        cmd, cwd=PROJECT_01, capture_output=True, text=True, timeout=60
    )

    # Before CSV を読む
    before_csv = (PROJECT_01 / sample_path).read_text(encoding="utf-8", errors="replace")

    # After CSV, レポート, sidecar を読む（存在すれば）
    basename = sample.rsplit(".", 1)[0]
    after_path = PROJECT_01 / "out" / f"{basename}.csv"
    report_path = PROJECT_01 / "out" / f"{basename}_report.md"
    sidecar_path = PROJECT_01 / "out" / f"{basename}_needs_review.csv"

    after_csv = after_path.read_text(encoding="utf-8") if after_path.exists() else ""
    report_md = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    sidecar_csv = sidecar_path.read_text(encoding="utf-8") if sidecar_path.exists() else ""

    return {
        "cmd": " ".join(cmd),
        "cwd": str(PROJECT_01),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
        "sample": sample,
        "before_csv": before_csv,
        "after_csv": after_csv,
        "report_md": report_md,
        "sidecar_csv": sidecar_csv,
    }


def run_demo_01_save_template(payload: dict) -> dict:
    sample = payload.get("sample", "timesheet_202604_haken_a.csv")
    name = payload.get("name", "haken_a")
    cmd = [
        "python3", "src/main.py", "save-template",
        "--input", f"samples/{sample}",
        "--name", name,
        "--force",
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_01, capture_output=True, text=True, timeout=60)
    return {
        "cmd": " ".join(cmd),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
    }


def run_demo_02(payload: dict) -> dict:
    """02 端数処理: compare で3ルール比較（セミナー演出の核）"""
    hourly = str(payload.get("hourly", 1800))
    break_min = str(payload.get("break", 60))
    punch = payload.get("punch", "9:03,18:07")
    cmd = [
        "python3", "src/main.py", "compare",
        "--config", "samples/rules/strict_1min.yml",
        "--config", "samples/rules/employee_friendly.yml",
        "--config", "samples/rules/company_friendly.yml",
        "--punch", punch,
        "--hourly", hourly,
        "--break", break_min,
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_02, capture_output=True, text=True, timeout=60)
    return {
        "cmd": " ".join(cmd),
        "cwd": str(PROJECT_02),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
        "punch": punch,
        "hourly": int(hourly),
        "break_min": int(break_min),
    }


def run_demo_02_explain(payload: dict) -> dict:
    rule = payload.get("rule", "samples/rules/company_friendly.yml")
    punch = payload.get("punch", "9:03,18:07")
    hourly = str(payload.get("hourly", 1800))
    cmd = [
        "python3", "src/main.py", "explain",
        "--config", rule,
        "--punch", punch,
        "--hourly", hourly,
        "--demo",
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_02, capture_output=True, text=True, timeout=60)
    return {
        "cmd": " ".join(cmd),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
    }


def run_demo_03(payload: dict) -> dict:
    """03 勤怠チェック: check を実行、生成ファイルも読み込む"""
    month = payload.get("month", "2026-04")
    as_of = payload.get("as_of_date", "2026-04-28")
    cmd = [
        "python3", "src/main.py", "check",
        "--month", month,
        "--as-of-date", as_of,
        "--data-class", "dummy",
        "--no-color",  # HTMLに埋め込むのでANSIなしが望ましい
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_03, capture_output=True, text=True, timeout=60)

    out_dir = PROJECT_03 / "out"
    yyyymm = month.replace("-", "")

    # 結果 JSON 読み込み
    result_json_path = out_dir / f"result_{yyyymm}.json"
    summary_json_path = out_dir / f"run_summary_{yyyymm}.json"
    result = json.loads(result_json_path.read_text(encoding="utf-8")) if result_json_path.exists() else None
    summary = json.loads(summary_json_path.read_text(encoding="utf-8")) if summary_json_path.exists() else None

    # 通知ファイル一覧
    notifications_dir = out_dir / "notifications"
    notifications = []
    if notifications_dir.exists():
        for f in sorted(notifications_dir.glob("*.txt")):
            notifications.append({"name": f.name, "content": f.read_text(encoding="utf-8")})

    # チェックリスト
    checklist_dir = out_dir / "checklist"
    checklists = []
    if checklist_dir.exists():
        for f in sorted(checklist_dir.glob("*.txt")):
            checklists.append({"name": f.name, "content": f.read_text(encoding="utf-8")})

    return {
        "cmd": " ".join(cmd),
        "cwd": str(PROJECT_03),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
        "month": month,
        "as_of_date": as_of,
        "result": result,
        "summary": summary,
        "notifications": notifications,
        "checklists": checklists,
    }


def run_demo_03_generate(payload: dict) -> dict:
    """03 のサンプル再生成"""
    month = payload.get("month", "2026-04")
    count = str(payload.get("count", 12))
    cmd = [
        "python3", "src/main.py", "generate-samples",
        "--month", month,
        "--data-class", "dummy",
        "--count", count,
        "--overwrite",
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_03, capture_output=True, text=True, timeout=60)
    return {
        "cmd": " ".join(cmd),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
    }


# ============================================================
# ルーティング
# ============================================================


DEMO_ACTIONS = {
    ("01", "run"): run_demo_01,
    ("01", "save_template"): run_demo_01_save_template,
    ("02", "run"): run_demo_02,
    ("02", "explain"): run_demo_02_explain,
    ("03", "run"): run_demo_03,
    ("03", "generate"): run_demo_03_generate,
}

SAMPLES_01 = [
    "timesheet_202604_haken_a.csv",
    "timesheet_202604_haken_b.csv",
    "timesheet_202604_haken_c.csv",
    "timesheet_202605_haken_a.csv",
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # ログを抑えめに
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str, content_type="text/plain; charset=utf-8"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, status: int, data: bytes, content_type="application/octet-stream"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # メタ API
        if path == "/api/meta":
            return self._send_json(200, {
                "name": "AI × CS 活用デモ 統合ダッシュボード",
                "demos": ["01", "02", "03", "04"],
                "samples_01": SAMPLES_01,
            })

        # 静的ファイル配信
        self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.strip("/").split("/")

        if len(path) >= 4 and path[0] == "api" and path[1] == "demo":
            demo_id = path[2]
            action = path[3]
            key = (demo_id, action)
            if key not in DEMO_ACTIONS:
                return self._send_json(404, {"error": f"unknown action: {demo_id}/{action}"})

            # body 読み込み
            length = int(self.headers.get("Content-Length", "0"))
            body_bytes = self.rfile.read(length) if length > 0 else b""
            try:
                payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
            except json.JSONDecodeError:
                return self._send_json(400, {"error": "invalid JSON body"})

            try:
                result = DEMO_ACTIONS[key](payload)
                return self._send_json(200, result)
            except subprocess.TimeoutExpired:
                return self._send_json(504, {"error": "demo execution timeout"})
            except Exception as e:
                return self._send_json(500, {"error": str(e), "type": type(e).__name__})

        self._send_json(404, {"error": "not found"})

    # ------------------------------------------------------------
    # 静的ファイル配信
    # ------------------------------------------------------------

    def _serve_static(self, path: str):
        # ルートなら dashboard/index.html
        if path in ("/", ""):
            path = "/dashboard/index.html"
        elif path == "/dashboard" or path == "/dashboard/":
            path = "/dashboard/index.html"

        # パスの正規化とリポジトリ外アクセスのガード
        rel = path.lstrip("/")
        target = (REPO_ROOT / rel).resolve()

        try:
            target.relative_to(REPO_ROOT)
        except ValueError:
            return self._send_json(403, {"error": "forbidden"})

        if not target.exists() or not target.is_file():
            return self._send_json(404, {"error": f"not found: {path}"})

        # Content-Type 判定
        ext = target.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
            ".csv": "text/csv; charset=utf-8",
            ".txt": "text/plain; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")

        # テキストは UTF-8 デコード前提で返却
        if ctype.startswith("text/") or ctype.startswith("application/json") or ctype.startswith("application/javascript"):
            try:
                text = target.read_text(encoding="utf-8")
                return self._send_text(200, text, ctype)
            except UnicodeDecodeError:
                pass

        self._send_bytes(200, target.read_bytes(), ctype)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    host = os.environ.get("HOST", "127.0.0.1")

    server = ThreadingHTTPServer((host, port), Handler)
    print("=" * 60)
    print("🚀 AI × CS 活用デモ 統合ダッシュボード")
    print(f"   URL:    http://{host}:{port}/")
    print(f"   Root:   {REPO_ROOT}")
    print(f"   Stop:   Ctrl+C")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止中...")
        server.shutdown()


if __name__ == "__main__":
    main()
