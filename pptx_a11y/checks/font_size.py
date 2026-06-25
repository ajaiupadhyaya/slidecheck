from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import run_target, shape_ref
from pptx_a11y.textutil import iter_runs, run_pt

MIN_PT = 18.0


def _run_indices(shape, para, run) -> tuple[int, int]:
    """Return (para_index, run_index) for the given para and run objects."""
    p_idx = next(
        (pi for pi, p in enumerate(shape.text_frame.paragraphs) if p._p is para._p),
        0,
    )
    r_idx = next(
        (ri for ri, r in enumerate(para.runs) if r._r is run._r),
        0,
    )
    return p_idx, r_idx


@register
def check(prs) -> list[Finding]:
    findings = []
    seen = set()
    for i, shape, para, run in iter_runs(prs):
        pt = run_pt(run)
        if pt is not None and pt < MIN_PT and not run.text.strip() == "":
            key = (i, shape.shape_id)
            if key in seen:
                continue
            seen.add(key)
            p_idx, r_idx = _run_indices(shape, para, run)
            findings.append(
                Finding(
                    check_id="font_size",
                    severity=Severity.WARNING,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Text is {pt:.0f}pt, below the {MIN_PT:.0f}pt minimum.",
                    suggestion=f"Increase body text to at least {MIN_PT:.0f}pt.",
                    # standards + remediation metadata
                    sc_refs=["1.4.4"],
                    wcag_version="2.0",
                    section508=True,
                    category="text",
                    fixable=True,
                    fix_action="bump_font_size",
                    current_value=str(int(pt)),
                    target=run_target(i, shape, p_idx, r_idx),
                )
            )
    return findings
