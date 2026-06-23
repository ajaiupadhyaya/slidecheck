import argparse
import os
import sys

from pptx_a11y.pipeline import process_file
from pptx_a11y.settings import get_describer, load_settings


def _pptx_in(folder: str) -> list[str]:
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".pptx"):
            continue
        if name.startswith("~$") or name.endswith("_accessible.pptx"):
            continue
        out.append(os.path.join(folder, name))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slidecheck", description="Check & fix PPTX accessibility.")
    parser.add_argument("path", help="A .pptx file or a folder of them.")
    args = parser.parse_args(argv)

    target = args.path
    if os.path.isdir(target):
        files = _pptx_in(target)
    elif os.path.isfile(target) and target.lower().endswith(".pptx"):
        files = [target]
    else:
        print(f"Not a .pptx file or folder: {target}", file=sys.stderr)
        return 2

    describer = get_describer(load_settings())
    for path in files:
        result = process_file(path, describer)
        if result.error:
            print(f"{os.path.basename(path)}: ERROR — {result.error}")
            continue
        s = {}
        for f in result.findings:
            s[f.severity.value] = s.get(f.severity.value, 0) + 1
        fixed = sum(1 for f in result.findings if f.auto_fixed)
        print(
            f"{os.path.basename(path)}: "
            f"{s.get('error', 0)} errors, {s.get('warning', 0)} warnings, "
            f"{fixed} auto-fixed -> {os.path.basename(result.output_path)}"
        )
    return 0
