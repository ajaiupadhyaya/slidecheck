"""Batch summary: one self-contained index.html linking every file's report.

Written next to the decks when a folder (or several files) is processed, so a
reviewer gets a single overview instead of opening each report by hand.
"""
import os
from html import escape
from urllib.parse import quote

from pptx_a11y.models import FileResult
from pptx_a11y.report import summary_counts

_CSS = """
body{font-family:system-ui,Arial,sans-serif;margin:2rem;color:#1a1a1a}
h1{font-size:1.4rem}
table{border-collapse:collapse;width:100%;margin-top:1rem}
th,td{text-align:left;padding:.5rem .7rem;border-bottom:1px solid #e0e0e0}
th{font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:#555}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.error{color:#a3140b;font-weight:600} .warning{color:#8a5300}
.info{color:#174ea6} .ok{color:#137333} .muted{color:#888}
a{color:#174ea6}
"""


def _report_name(source_path: str) -> str:
    stem = os.path.splitext(os.path.basename(source_path))[0]
    return f"{stem}_a11y_report.html"


def _row(result: FileResult) -> str:
    name = escape(os.path.basename(result.source_path))
    if result.error:
        return (
            f'<tr><td>{name}</td>'
            f'<td class="error" colspan="5">Could not process: {escape(result.error)}</td>'
            f'<td class="muted">—</td></tr>'
        )
    s = summary_counts(result)
    report = _report_name(result.source_path)
    link = f'<a href="{escape(quote(report))}">open report</a>'
    return (
        f'<tr><td>{name}</td>'
        f'<td class="num error">{s["error"]}</td>'
        f'<td class="num warning">{s["warning"]}</td>'
        f'<td class="num info">{s["info"]}</td>'
        f'<td class="num ok">{s["auto_fixed"]}</td>'
        f'<td class="num">{s["manual"]}</td>'
        f'<td>{link}</td></tr>'
    )


def render(results: list[FileResult]) -> str:
    total_err = sum(len([f for f in r.findings if f.severity.value == "error"]) for r in results if not r.error)
    failed = sum(1 for r in results if r.error)
    rows = "".join(_row(r) for r in results)
    head = (
        f"<h1>SlideCheck — batch summary</h1>"
        f"<p>{len(results)} file(s) checked · {total_err} total error(s)"
        + (f" · {failed} could not be opened" if failed else "")
        + "</p>"
    )
    table = (
        "<table><thead><tr>"
        "<th>File</th><th>Errors</th><th>Warnings</th><th>Info</th>"
        "<th>Auto-fixed</th><th>Needs manual fix</th><th>Report</th>"
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>SlideCheck batch summary</title><style>{_CSS}</style></head>"
        f"<body>{head}{table}</body></html>"
    )


def write_index(results: list[FileResult], out_dir: str, filename: str = "index.html") -> str:
    """Render and write the batch index into out_dir; return its path.

    Overwrites a previous index.html (a regenerated artifact, like the per-file
    reports), but never touches an original deck.
    """
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(results))
    return path
