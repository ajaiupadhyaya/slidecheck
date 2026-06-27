from html import escape

from pptx_a11y import standards
from pptx_a11y.models import FileResult
from pptx_a11y.report import summary_counts

_CSS = """
body{font-family:system-ui,Arial,sans-serif;margin:2rem;color:#1a1a1a}
h1{font-size:1.4rem} .sum{display:flex;gap:1rem;margin:1rem 0;flex-wrap:wrap}
.pill{padding:.3rem .7rem;border-radius:1rem;font-size:.85rem}
.error{background:#fdecea;color:#a3140b} .warning{background:#fff4e5;color:#8a5300}
.info{background:#e8f0fe;color:#174ea6} .ok{background:#e6f4ea;color:#137333}
.slide{border:1px solid #e0e0e0;border-radius:8px;margin:1rem 0;padding:1rem}
.item{padding:.5rem 0;border-bottom:1px solid #f0f0f0}
.tag{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;margin-right:.5rem}
.review{background:#fff4e5;color:#8a5300;padding:.1rem .4rem;border-radius:4px;font-size:.75rem}
.sug{color:#444;font-size:.9rem}
.admin{background:#f7f8fa;border:1px solid #e0e0e0;border-radius:8px;padding:1rem 1.25rem;margin:1rem 0}
.admin h2{font-size:1.1rem;margin:.2rem 0 .6rem} .admin .verdict{font-weight:600;margin:.2rem 0 .6rem}
.admin ul{margin:.3rem 0;padding-left:1.2rem} .admin li{margin:.15rem 0}
.score-num{font-size:1.6rem;font-weight:700}
nav.slides{margin:1rem 0;font-size:.9rem} nav.slides a{margin-right:.8rem}
"""


def _by_slide(items):
    out: dict[int, list] = {}
    for it in items:
        out.setdefault(it.slide_index, []).append(it)
    return dict(sorted(out.items()))


def _admin_summary(result: FileResult) -> str:
    """A plain-English 'Summary for administration' block: score/grade, the
    Section 508 failure count (the legal floor), best-practice warnings, and a
    one-sentence verdict an administrator can act on."""
    sc = standards.score(result.findings)
    counts = summary_counts(result)
    # Open (not auto-fixed) findings tagged Section 508 are legal-floor issues,
    # at ANY severity — e.g. a missing document language (3.1.1) is a 508 item
    # even though it is only WARNING severity.
    sec508 = sum(1 for f in result.findings if not f.auto_fixed and f.section508)
    # Open warnings only — auto-fixed ones are resolved, not "to review".
    open_warnings = sum(
        1 for f in result.findings
        if not f.auto_fixed and f.severity.value == "warning"
    )

    if sec508:
        verdict = (
            f"This deck has {sec508} Section 508 issue"
            f"{'s' if sec508 != 1 else ''} that must be fixed before distribution."
        )
    elif open_warnings:
        verdict = (
            f"This deck meets the Section 508 floor but has {open_warnings} "
            f"warning{'s' if open_warnings != 1 else ''} to review."
        )
    else:
        verdict = "This deck passed all automated accessibility checks."

    return (
        '<section class="admin" aria-labelledby="admin-h">'
        '<h2 id="admin-h">Summary for administration</h2>'
        f'<p class="verdict">{escape(verdict)}</p>'
        '<ul>'
        f'<li><span class="score-num">{sc["score"]}</span> / 100 &nbsp;(Grade {escape(sc["grade"])})</li>'
        f'<li>Section 508 issues: {sec508}</li>'
        f'<li>Open warnings: {open_warnings}</li>'
        f'<li>Auto-fixed: {counts["auto_fixed"]}</li>'
        f'<li>Needs manual fix: {counts["manual"]}</li>'
        '</ul>'
        '</section>'
    )


def render(result: FileResult) -> str:
    s = summary_counts(result)
    rows = []
    rows.append(f"<h1>Accessibility report — {escape(result.source_path)}</h1>")
    if result.error:
        rows.append(f'<p class="pill error">Could not process: {escape(result.error)}</p>')
        return _doc("".join(rows))
    if result.output_path:
        rows.append(f"<p>Corrected file: <code>{escape(result.output_path)}</code></p>")

    rows.append(_admin_summary(result))

    rows.append(
        '<div class="sum">'
        f'<span class="pill error">{s["error"]} errors</span>'
        f'<span class="pill warning">{s["warning"]} warnings</span>'
        f'<span class="pill info">{s["info"]} info</span>'
        f'<span class="pill ok">{s["auto_fixed"]} auto-fixed</span>'
        f'<span class="pill warning">{s["manual"]} need manual fix</span>'
        "</div>"
    )

    findings_by_slide = _by_slide(result.findings)
    changes_by_slide = _by_slide(result.changes)
    all_slides = sorted(set(findings_by_slide) | set(changes_by_slide))

    # Slide jump navigation (landmark) so a screen-reader user can skip around.
    if all_slides:
        links = " ".join(f'<a href="#slide-{idx}">Slide {idx + 1}</a>' for idx in all_slides)
        rows.append(f'<nav class="slides" aria-label="Slides">{links}</nav>')

    rows.append("<main>")
    for idx in all_slides:
        head_id = f"slide-{idx}-h"
        rows.append(
            f'<section class="slide" id="slide-{idx}" aria-labelledby="{head_id}">'
            f'<h2 id="{head_id}">Slide {idx + 1}</h2>'
        )
        for f in findings_by_slide.get(idx, []):
            fixed = ' <span class="review">auto-fixed</span>' if f.auto_fixed else ""
            sug = f'<div class="sug">Suggestion: {escape(f.suggestion)}</div>' if f.suggestion else ""
            rows.append(
                f'<div class="item"><span class="tag {escape(f.severity.value)}">{escape(f.severity.value)}</span>'
                f'{escape(f.message)}{fixed}{sug}</div>'
            )
        for c in changes_by_slide.get(idx, []):
            mark = ' <span class="review">review this</span>' if c.machine_generated else ""
            rows.append(f'<div class="item"><span class="tag ok">changed</span>{escape(c.description)}{mark}</div>')
        rows.append("</section>")
    rows.append("</main>")
    return _doc("".join(rows))


def _doc(body: str) -> str:
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><style>{_CSS}</style></head><body>{body}</body></html>"
