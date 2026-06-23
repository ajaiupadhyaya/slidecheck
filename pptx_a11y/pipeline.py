import os

from pptx_a11y.checks import load_all as load_checks
from pptx_a11y.fixers import load_all as load_fixers
from pptx_a11y.loader import LoadError, load_presentation
from pptx_a11y.models import FileResult
from pptx_a11y.report import html_report, json_report

# check_id <-> fixer_id pairs whose changes mean a finding was auto-fixed
_FIX_MAP = {"alt_text": "alt_text", "slide_title": "slide_title", "metadata": "metadata"}


def unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    n = 1
    while os.path.exists(f"{base}_{n}{ext}"):
        n += 1
    return f"{base}_{n}{ext}"


def _mark_fixed(findings, changes):
    change_keys = {(c.fixer_id, c.slide_index, c.shape_ref) for c in changes}
    for f in findings:
        fixer = _FIX_MAP.get(f.check_id)
        if fixer and (fixer, f.slide_index, f.shape_ref) in change_keys:
            f.auto_fixed = True


def process_file(path: str, describer, out_dir: str | None = None) -> FileResult:
    out_dir = out_dir or os.path.dirname(os.path.abspath(path))
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        prs = load_presentation(path)
    except LoadError as exc:
        return FileResult(source_path=path, error=str(exc))

    findings = []
    for check in load_checks():
        findings.extend(check(prs))

    changes = []
    for fixer in load_fixers():
        changes.extend(fixer(prs, describer))

    _mark_fixed(findings, changes)

    out_path = unique_path(os.path.join(out_dir, f"{stem}_accessible.pptx"))
    prs.save(out_path)

    result = FileResult(source_path=path, output_path=out_path, findings=findings, changes=changes)

    with open(os.path.join(out_dir, f"{stem}_a11y_report.html"), "w", encoding="utf-8") as fh:
        fh.write(html_report.render(result))
    with open(os.path.join(out_dir, f"{stem}_a11y_report.json"), "w", encoding="utf-8") as fh:
        fh.write(json_report.render(result))
    return result
