"""CLI Dispatcher (spec §5.25)."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

# Allow running as `python src/main.py ...`: ensure project root on sys.path
# so that `import src.flows...` works the same way as `python -m src.main`.
if __package__ in (None, ""):
    _this_dir = Path(__file__).resolve().parent
    _project_root = _this_dir.parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-automation",
        description="派遣管理CSV標準化ツール（勤怠CSV自動整形デモ）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # convert
    pc = sub.add_parser("convert", help="崩れCSVを標準スキーマに変換")
    pc.add_argument("--input", type=str, help="入力CSVファイル")
    pc.add_argument("--input-dir", type=str, help="入力ディレクトリ（*.csv一括）")
    pc.add_argument("--output", type=str, help="出力ファイルパス")
    pc.add_argument("--output-dir", type=str, help="出力ディレクトリ（バッチ時）")
    pc.add_argument("--template", type=str, help="適用テンプレート名")
    pc.add_argument(
        "--error-policy", choices=["drop", "keep", "fail"], default="drop",
        help="要確認行の扱い（既定: drop）",
    )
    pc.add_argument(
        "--report-format", choices=["md", "csv"], default="md",
        help="レポート形式（既定: md）",
    )
    pc.add_argument("--dry-run", action="store_true", help="書き出しを行わずサマリのみ表示")
    pc.add_argument("--fail-fast", action="store_true", help="バッチで1件失敗したら即停止")
    pc.add_argument("--verbose", action="store_true", help="詳細ログ")

    # save-template
    ps = sub.add_parser("save-template", help="ヘッダーマッピングをテンプレートとして保存")
    ps.add_argument("--input", type=str, required=True, help="推論対象CSV")
    ps.add_argument("--name", type=str, required=True, help="テンプレート名（snake_case）")
    ps.add_argument("--interactive", action="store_true", help="対話式確認（MVPでは簡易表示）")
    ps.add_argument("--force", action="store_true", help="既存テンプレートを上書き")

    # cleanup
    pclean = sub.add_parser("cleanup", help="out/ と samples/tmp_* を削除")
    pclean.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "convert":
        if not args.input and not args.input_dir:
            print("[ERROR] --input または --input-dir のいずれかが必要です", file=sys.stderr)
            return 1
        if args.input and args.input_dir:
            print("[ERROR] --input と --input-dir は同時指定できません", file=sys.stderr)
            return 1
        from src.flows.convert import ConvertFlow
        return ConvertFlow().run(args)

    if args.command == "save-template":
        from src.flows.save_template import SaveTemplateFlow
        return SaveTemplateFlow().run(args)

    if args.command == "cleanup":
        from src.flows.cleanup import CleanupFlow
        return CleanupFlow().run(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
