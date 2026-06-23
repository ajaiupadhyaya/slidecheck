from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref
from pptx_a11y.textutil import iter_runs, run_pt

MIN_PT = 18.0


@register
def check(prs) -> list[Finding]:
    findings = []
    seen = set()
    for i, shape, _para, run in iter_runs(prs):
        pt = run_pt(run)
        if pt is not None and pt < MIN_PT and not run.text.strip() == "":
            key = (i, shape.shape_id)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                Finding(
                    check_id="font_size",
                    severity=Severity.WARNING,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Text is {pt:.0f}pt, below the {MIN_PT:.0f}pt minimum.",
                    suggestion=f"Increase body text to at least {MIN_PT:.0f}pt.",
                )
            )
    return findings
