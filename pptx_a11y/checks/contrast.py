from pptx_a11y.checks import register
from pptx_a11y.color import contrast_ratio, suggest_compliant_color
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import run_target, shape_ref, shape_target
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
    for i, shape, para, run in iter_runs(prs):
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
                    # standards + remediation metadata
                    sc_refs=["1.4.3"],
                    wcag_version="2.0",
                    section508=True,
                    category="color",
                    fixable=False,
                    fix_action=None,
                    current_value=None,
                    target=shape_target(i, shape),
                )
            )
            continue
        slide = prs.slides[i]
        contrast_target = _target(run)
        bg = _background_rgb(shape, slide)
        resolved = bg is not None
        bg = bg if resolved else ASSUMED_BG
        ratio = contrast_ratio(fg, bg)
        if ratio < contrast_target:
            sug = suggest_compliant_color(fg, bg, contrast_target)
            caveat = "" if resolved else " (assuming a white background)"
            sug_hex = f"#{sug[0]:02X}{sug[1]:02X}{sug[2]:02X}"
            fg_hex = f"#{fg[0]:02X}{fg[1]:02X}{fg[2]:02X}"
            p_idx, r_idx = _run_indices(shape, para, run)
            findings.append(
                Finding(
                    check_id="contrast",
                    severity=Severity.ERROR,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Contrast ratio {ratio:.1f}:1 is below {contrast_target:.1f}:1{caveat}.",
                    suggestion=f"Use color #{sug[0]:02X}{sug[1]:02X}{sug[2]:02X} or darker.",
                    # standards + remediation metadata
                    sc_refs=["1.4.3"],
                    wcag_version="2.0",
                    section508=True,
                    category="color",
                    fixable=True,
                    fix_action="apply_contrast_color",
                    current_value=fg_hex,
                    suggested_value=sug_hex,
                    target=run_target(i, shape, p_idx, r_idx),
                )
            )
    return findings
