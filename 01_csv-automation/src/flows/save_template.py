"""SaveTemplateFlow (spec §5.23). MVP: non-interactive auto-adopt only."""
from __future__ import annotations
import sys
from argparse import Namespace
from pathlib import Path

from ..errors import DemoError
from ..io.loader import TimesheetLoader
from ..mapping.inferencer import HeaderInferencer
from ..template.store import TemplateStore


class SaveTemplateFlow:
    def __init__(self) -> None:
        self.loader = TimesheetLoader()
        self.inferencer = HeaderInferencer()
        self.store = TemplateStore()

    def run(self, args: Namespace) -> int:
        try:
            return self._run(args)
        except DemoError as e:
            print(f"[ERROR] {type(e).__name__}: {e.message}", file=sys.stderr)
            if e.hint:
                print(f"        hint: {e.hint}", file=sys.stderr)
            return 1

    def _run(self, args: Namespace) -> int:
        input_path = Path(args.input)
        loaded = self.loader.load(input_path)
        mapping = self.inferencer.infer(loaded.headers)
        # Interactive is spec-suggested; MVP auto-adopts silently with a note.
        if getattr(args, "interactive", False):
            print("[INFO] --interactive は MVP では簡易対応（自動採用のみ）。確定マッピング:")
            for canonical, src in mapping.source_headers.items():
                conf = mapping.confidence.get(canonical, 0.0)
                print(f"  - {canonical} ← {src} ({conf:.2f})")

        path = self.store.save(
            name=args.name,
            mapping=mapping,
            encoding=loaded.encoding,
            dialect=loaded.dialect,
            source_hint=input_path.name,
            force=bool(getattr(args, "force", False)),
        )
        print(f"[OK] テンプレート保存: {path}")
        for canonical, src in mapping.source_headers.items():
            conf = mapping.confidence.get(canonical, 0.0)
            nr = canonical in mapping.needs_review_columns
            flag = " (要確認)" if nr else ""
            print(f"  - {canonical} ← {src} (conf={conf:.2f}){flag}")
        return 0
