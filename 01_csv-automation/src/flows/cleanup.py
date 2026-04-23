"""CleanupFlow (spec §5.23b, MAY). MVP simplified."""
from __future__ import annotations
from argparse import Namespace
from pathlib import Path


class CleanupFlow:
    def run(self, args: Namespace) -> int:
        dry = bool(getattr(args, "dry_run", False))
        targets: list[Path] = []
        out_dir = Path("out")
        if out_dir.is_dir():
            for p in out_dir.iterdir():
                if p.is_file():
                    targets.append(p)
        samples_dir = Path("samples")
        if samples_dir.is_dir():
            for p in samples_dir.iterdir():
                if p.is_file() and p.name.startswith("tmp_"):
                    targets.append(p)

        if dry:
            print("[dry-run] 削除対象:")
            for t in targets:
                print(f"  - {t}")
            print(f"合計: {len(targets)} 件")
            return 0

        removed = 0
        for t in targets:
            try:
                t.unlink()
                removed += 1
            except OSError as e:
                print(f"[WARN] 削除失敗: {t} ({e})")
        print(f"[OK] 削除済み: {removed} / {len(targets)} 件")
        return 0
