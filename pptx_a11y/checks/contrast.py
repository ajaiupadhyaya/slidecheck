from pptx_a11y.checks import register
from pptx_a11y.color import contrast_ratio, suggest_compliant_color
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref
from pptx_a11y.textutil import iter_runs, run_rgb, run_pt, fill_rgb

ASSUMED_BG = (255, 255, 255)  # fallback only when nothing else resolves (default light themes)


def _target(run) -> float:
    pt = run_pt(run) or 18.0
    bold = bool(run.font.bold)
    large = pt >= 18.0 or (pt >= 14.0 and bold)
    return 3.0 if large else 4.5


def _background_rgb(shape, slide):
    # 1. the text shape's own fill (text on a colored box)
    bg = fill_rgb(shape)
    if bg is not None:
        return bg
    # 2. explicit slide background
    bg = fill_rgb(slide.background)
    if bg is not None:
        return bg
    # 3. layout background, then 4. master background
    try:
        layout = slide.slide_layout
        bg = fill_rgb(layout.background)
        if bg is not None:
            return bg
        bg = fill_rgb(layout.slide_master.background)
        if bg is not None:
            return bg
    except Exception:  # noqa: BLE001
        pass
    return None


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
        slide = prs.slides[i]
        target = _target(run)
        bg = _background_rgb(shape, slide)
        resolved = bg is not None
        bg = bg if resolved else ASSUMED_BG
        ratio = contrast_ratio(fg, bg)
        if ratio < target:
            sug = suggest_compliant_color(fg, bg, target)
            caveat = "" if resolved else " (assuming a white background)"
            findings.append(
                Finding(
                    check_id="contrast",
                    severity=Severity.ERROR,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Contrast ratio {ratio:.1f}:1 is below {target:.1f}:1{caveat}.",
                    suggestion=f"Use color #{sug[0]:02X}{sug[1]:02X}{sug[2]:02X} or darker.",
                )
            )
    return findings
