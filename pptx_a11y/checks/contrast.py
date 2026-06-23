from pptx_a11y.checks import register
from pptx_a11y.color import contrast_ratio, suggest_compliant_color
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref
from pptx_a11y.textutil import iter_runs, run_rgb, run_pt

DEFAULT_BG = (255, 255, 255)  # assume white slide background when unresolved


def _target(run) -> float:
    pt = run_pt(run) or 18.0
    bold = bool(run.font.bold)
    large = pt >= 18.0 or (pt >= 14.0 and bold)
    return 3.0 if large else 4.5


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, shape, _para, run in iter_runs(prs):
        if not run.text.strip():
            continue
        fg = run_rgb(run)
        if fg is None:
            findings.append(
                Finding(
                    check_id="contrast",
                    severity=Severity.INFO,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message="Text color is theme/inherited; contrast is indeterminate.",
                    suggestion="Verify this text meets 4.5:1 contrast manually.",
                )
            )
            continue
        target = _target(run)
        ratio = contrast_ratio(fg, DEFAULT_BG)
        if ratio < target:
            sug = suggest_compliant_color(fg, DEFAULT_BG, target)
            findings.append(
                Finding(
                    check_id="contrast",
                    severity=Severity.ERROR,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Contrast ratio {ratio:.1f}:1 is below {target:.1f}:1 (assuming white background).",
                    suggestion=f"Use color #{sug[0]:02X}{sug[1]:02X}{sug[2]:02X} or darker.",
                )
            )
    return findings
