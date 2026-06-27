import argparse
import os
import sys

from pptx_a11y.alt_text_ai import NullDescriber
from pptx_a11y.analyze import run_checks
from pptx_a11y.loader import LoadError, load_presentation
from pptx_a11y.pipeline import process_file
from pptx_a11y.report import batch_index
from pptx_a11y.settings import get_describer, load_settings

# ANSI colours, only emitted to an interactive terminal (and never when the
# NO_COLOR convention is set) so piped/CI output stays clean.
_COLORS = {"error": "\033[31m", "warning": "\033[33m", "info": "\033[34m"}
_RESET = "\033[0m"


def _color(text: str, key: str) -> str:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return text
    return f"{_COLORS.get(key, '')}{text}{_RESET}"


def _pptx_in(folder: str) -> list[str]:
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".pptx"):
            continue
        if name.startswith("~$") or name.endswith("_accessible.pptx"):
            continue
        out.append(os.path.join(folder, name))
    return out


def _open_errors(findings) -> int:
    return sum(1 for f in findings if not f.auto_fixed and f.severity.value == "error")


def _summary_line(name: str, findings, fixed: int, suffix: str = "") -> str:
    counts = {}
    for f in findings:
        counts[f.severity.value] = counts.get(f.severity.value, 0) + 1
    return (
        f"{name}: "
        f"{_color(str(counts.get('error', 0)) + ' errors', 'error')}, "
        f"{_color(str(counts.get('warning', 0)) + ' warnings', 'warning')}, "
        f"{fixed} auto-fixed{suffix}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slidecheck", description="Check & fix PPTX accessibility.")
    parser.add_argument("path", help="A .pptx file or a folder of them.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Audit only: print findings and write no files (no fixed deck, no reports).",
    )
    parser.add_argument(
        "--no-ai", action="store_true",
        help="Skip Claude entirely (no AI alt text / suggestions) for a fast, offline scan.",
    )
    args = parser.parse_args(argv)

    target = args.path
    is_folder = os.path.isdir(target)
    if is_folder:
        files = _pptx_in(target)
    elif os.path.isfile(target) and target.lower().endswith(".pptx"):
        files = [target]
    else:
        print(f"Not a .pptx file or folder: {target}", file=sys.stderr)
        return 2

    describer = NullDescriber() if args.no_ai else get_describer(load_settings())

    results = []
    open_error_total = 0
    had_load_failure = False
    for path in files:
        name = os.path.basename(path)

        if args.dry_run:
            try:
                prs = load_presentation(path)
            except LoadError as exc:
                print(f"{name}: ERROR — {exc}", file=sys.stderr)
                had_load_failure = True
                continue
            findings = run_checks(prs)
            open_error_total += _open_errors(findings)
            print(_summary_line(name, findings, 0, "  (dry run — nothing written)"))
            continue

        result = process_file(path, describer)
        results.append(result)
        if result.error:
            print(f"{name}: ERROR — {result.error}", file=sys.stderr)
            had_load_failure = True
            continue
        open_error_total += _open_errors(result.findings)
        fixed = sum(1 for f in result.findings if f.auto_fixed)
        report = os.path.splitext(path)[0] + "_a11y_report.html"
        print(_summary_line(name, result.findings, fixed, f" -> {os.path.basename(result.output_path)}"))
        print(f"  report: {os.path.abspath(report)}")

    if is_folder and results and not args.dry_run:
        index = batch_index.write_index(results, target)
        print(f"Batch summary: {os.path.abspath(index)}")

    # Exit codes (so CI can act on the result):
    #   2 — a deck could not be opened/processed (hard failure)
    #   1 — ran fine, but a deck still has an open Error finding (needs work)
    #   0 — ran fine, all good
    if had_load_failure:
        return 2
    return 1 if open_error_total else 0
