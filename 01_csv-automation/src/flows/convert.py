"""ConvertFlow (spec §5.22). MVP: single file convert pipeline."""
from __future__ import annotations
import sys
from argparse import Namespace
from pathlib import Path

from ..errors import DemoError
from ..io.loader import TimesheetLoader
from ..io.writer import TimesheetWriter
from ..mapping.inferencer import HeaderInferencer
from ..normalize.timesheet import TimesheetNormalizer
from ..quality.counters import RowCountValidator
from ..quality.policy import ErrorPolicy, ErrorPolicyApplier
from ..quality.review import ReviewCollector
from ..report.generator import BillingReportGenerator
from ..schema.canonical import CANONICAL_COLUMNS
from ..security.mask import mask_row
from ..template.store import TemplateStore


def _resolve_paths(input_path: Path, output: Path | None, output_dir: Path | None) -> tuple[Path, Path, Path]:
    base = input_path.stem
    if output is not None:
        out = output
        report_dir = out.parent
    else:
        out_dir = output_dir or Path("out")
        out = out_dir / f"{base}.csv"
        report_dir = out_dir
    report = report_dir / f"{base}_report.md"
    sidecar = report_dir / f"{base}_needs_review.csv"
    return out, report, sidecar


def _policy(name: str) -> ErrorPolicy:
    return ErrorPolicy(name)


def _print_preview(loaded, outcome, policy, input_path: Path, output_path: Path):
    c = outcome.counters
    pol = policy.value
    print()
    print("=== Before (masked, first 3 rows) ===")
    print(",".join(loaded.headers))
    for raw in loaded.rows[:3]:
        print(",".join(raw))
    print()
    print("=== After (masked, first 3 rows) ===")
    print(",".join(CANONICAL_COLUMNS))
    for r in outcome.output_rows[:3]:
        masked = mask_row(r.values)
        print(",".join(masked.get(c, "") for c in CANONICAL_COLUMNS))
    print()
    print("=== Summary ===")
    print(
        f"input={c.input_rows} output={c.output_rows} dropped={c.dropped_rows} "
        f"review={c.review_rows} (policy={pol})"
    )
    if pol == "drop":
        ok = c.input_rows == c.output_rows + c.dropped_rows
        print(
            f"関係式: input = output + dropped → "
            f"{c.input_rows} = {c.output_rows} + {c.dropped_rows} {'✓' if ok else '✗'}"
        )


class ConvertFlow:
    def __init__(self) -> None:
        self.loader = TimesheetLoader()
        self.inferencer = HeaderInferencer()
        self.normalizer = TimesheetNormalizer()
        self.collector = ReviewCollector()
        self.applier = ErrorPolicyApplier()
        self.validator = RowCountValidator()
        self.writer = TimesheetWriter()
        self.reporter = BillingReportGenerator()
        self.template_store = TemplateStore()

    def run(self, args: Namespace) -> int:
        try:
            return self._run(args)
        except DemoError as e:
            print(f"[ERROR] {type(e).__name__}: {e.message}", file=sys.stderr)
            if e.hint:
                print(f"        hint: {e.hint}", file=sys.stderr)
            return 1

    def _run(self, args: Namespace) -> int:
        # Batch mode
        if getattr(args, "input_dir", None):
            return self._run_batch(args)

        input_path = Path(args.input)
        policy = _policy(args.error_policy)
        dry_run = bool(getattr(args, "dry_run", False))

        loaded = self.loader.load(input_path)

        template = None
        if getattr(args, "template", None):
            template = self.template_store.load(args.template)

        mapping = self.inferencer.infer(loaded.headers, template=template)
        result = self.normalizer.normalize(loaded, mapping)
        ledger = self.collector.collect(result)
        outcome = self.applier.apply(result, ledger, policy)

        # Validate counters BEFORE writing (fail-fast)
        if not outcome.halted:
            self.validator.validate(outcome.counters, policy)

        output_path, report_path, sidecar_path = _resolve_paths(
            input_path,
            Path(args.output) if getattr(args, "output", None) else None,
            Path(args.output_dir) if getattr(args, "output_dir", None) else None,
        )

        if dry_run:
            _print_preview(loaded, outcome, policy, input_path, output_path)
            print("[dry-run] ファイル書き出しはスキップされました")
            return 1 if outcome.halted else 0

        # Fail policy with review>0: do NOT write CSV, still write report
        if outcome.halted:
            self.reporter.generate(
                input_path=input_path,
                output_path=output_path,
                loaded=loaded,
                mapping=mapping,
                outcome=outcome,
                policy=policy,
                report_path=report_path,
                format=getattr(args, "report_format", "md"),
            )
            _print_preview(loaded, outcome, policy, input_path, output_path)
            print(
                f"[FAIL] fail ポリシーで要確認行あり（review={outcome.counters.review_rows}）。"
                f"整形済CSV未出力、レポートのみ生成しました: {report_path}",
                file=sys.stderr,
            )
            return 1

        self.writer.write(outcome.output_rows, output_path, policy)
        if policy == ErrorPolicy.KEEP:
            self.writer.write_sidecar(outcome.output_rows, sidecar_path)

        self.reporter.generate(
            input_path=input_path,
            output_path=output_path,
            loaded=loaded,
            mapping=mapping,
            outcome=outcome,
            policy=policy,
            report_path=report_path,
            format=getattr(args, "report_format", "md"),
        )

        _print_preview(loaded, outcome, policy, input_path, output_path)
        print(f"[OK] 出力: {output_path}")
        print(f"[OK] レポート: {report_path}")
        return 0

    def _run_batch(self, args: Namespace) -> int:
        input_dir = Path(args.input_dir)
        if not input_dir.is_dir():
            print(f"[ERROR] 入力ディレクトリが存在しません: {input_dir}", file=sys.stderr)
            return 1
        files = sorted(
            p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".csv"
        )
        if not files:
            print(f"[WARN] CSVファイルが見つかりません: {input_dir}", file=sys.stderr)
            return 0

        total = len(files)
        failures = 0
        fail_fast = bool(getattr(args, "fail_fast", False))
        for i, f in enumerate(files, 1):
            print(f"[{i}/{total}] {f}")
            per_args = Namespace(**vars(args))
            per_args.input = str(f)
            per_args.input_dir = None
            rc = self._run(per_args)
            if rc != 0:
                failures += 1
                if fail_fast:
                    return 1
        if failures == 0:
            return 0
        return 2
