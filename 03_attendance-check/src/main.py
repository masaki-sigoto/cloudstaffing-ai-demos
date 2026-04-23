"""CLI エントリ。"""

from __future__ import annotations

import logging
import sys
from typing import Optional

# パッケージ実行と単体実行の両立
try:
    from .cli import build_parser, run_check, run_generate_samples, validate_data_class_guard
    from .errors import DemoError
except ImportError:  # python src/main.py で直接実行されるケース
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.cli import build_parser, run_check, run_generate_samples, validate_data_class_guard  # type: ignore
    from src.errors import DemoError  # type: ignore


def main(argv: Optional[list] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_data_class_guard(args)
        if args.subcommand == "check":
            return run_check(args)
        elif args.subcommand == "generate-samples":
            return run_generate_samples(args)
        else:
            parser.print_help()
            return 2
    except DemoError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return e.exit_code
    except Exception as e:  # 想定外
        print(f"[FATAL] 予期しないエラー: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
