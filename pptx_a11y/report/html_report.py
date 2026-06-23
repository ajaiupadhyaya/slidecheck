from html import escape
from pptx_a11y.models import FileResult
from pptx_a11y.report import summary_counts

_CSS = """
body{font-family:system-ui,Arial,sans-serif;margin:2rem;color:#1a1a1a}
h1{font-size:1.4rem} .sum{display:flex;gap:1rem;margin:1rem 0}
.pill{padding:.3rem .7rem;border-radius:1rem;font-size:.85rem}
.error{background:#fdecea;color:#a3140b} .warning{background:#fff4e5;color:#8a5300}
.info{background:#e8f0fe;color:#174ea6} .ok{background:#e6f4ea;color:#137333}
.slide{border:1px solid #e0e0e0;border-radius:8px;margin:1rem 0;padding:1rem}
.item{padding:.5rem 0;border-bottom:1px solid #f0f0f0}
.tag{font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;margin-right:.5rem}
.review{background:#fff4e5;color:#8a5300;padding:.1rem .4rem;border-radius:4px;font-size:.75rem}
.sug{color:#444;font-size:.9rem}
"""


def _by_slide(items):
    out: dict[int, list] = {}
    for it in items:
        out.setdefault(it.slide_index, []).append(it)
    return dict(sorted(out.items()))


def render(result: FileResult) -> str:
    s = summary_counts(result)
    rows = []
    rows.append(f"<h1>Accessibility report — {escape(result.source_path)}</h1>")
    if result.error:
        rows.append(f'<p class="pill error">Could not process: {escape(result.error)}</p>')
        return _doc("".join(rows))
    if result.output_path:
        rows.append(f"<p>Corrected file: <code>{escape(result.output_path)}</code></p>")
    rows.append(
        '<div class="sum">'
        f'<span class="pill error">{s["error"]} errors</span>'
        f'<span class="pill warning">{s["warning"]} warnings</span>'
        f'<span class="pill info">{s["info"]} info</span>'
        f'<span class="pill ok">{s["auto_fixed"]} auto-fixed</span>'
        "</div>"
    )

    findings_by_slide = _by_slide(result.findings)
    changes_by_slide = _by_slide(result.changes)
    all_slides = sorted(set(findings_by_slide) | set(changes_by_slide))
    for idx in all_slides:
        rows.append(f'<div class="slide"><h2>Slide {idx + 1}</h2>')
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
        rows.append("</div>")
    return _doc("".join(rows))


def _doc(body: str) -> str:
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><style>{_CSS}</style></head><body>{body}</body></html>"
