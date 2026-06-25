import re

from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity

_GENERIC_RE = re.compile(
    r"^(slide\s*\d*|untitled|title|presentation)$",
    re.IGNORECASE,
)


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, slide in enumerate(prs.slides):
        title = slide.shapes.title
        text = (title.text if title is not None else "").strip()
        if not text:
            findings.append(
                Finding(
                    check_id="slide_title",
                    severity=Severity.ERROR,
                    slide_index=i,
                    message="Slide has no title.",
                    suggestion="Give every slide a unique, descriptive title.",
                    # standards + remediation metadata
                    sc_refs=["2.4.2"],
                    wcag_version="2.0",
                    section508=True,
                    category="structure",
                    fixable=True,
                    fix_action="set_title",
                    current_value=text,
                    target={"slide": i, "scope": "slide_title"},
                )
            )
    return findings


@register
def check_title_quality(prs) -> list[Finding]:
    """Flag generic and duplicate slide titles (WCAG 2.4.6)."""
    findings = []

    # Collect (slide_index, title_text) for slides that HAVE a non-empty title
    titled: list[tuple[int, str]] = []
    for i, slide in enumerate(prs.slides):
        title = slide.shapes.title
        text = (title.text if title is not None else "").strip()
        if text:
            titled.append((i, text))

    # --- generic titles ---
    for i, text in titled:
        if _GENERIC_RE.match(text):
            findings.append(
                Finding(
                    check_id="title_quality",
                    severity=Severity.WARNING,
                    slide_index=i,
                    message="Slide title is generic; make it descriptive.",
                    suggestion="Use a unique, descriptive title.",
                    sc_refs=["2.4.6"],
                    wcag_version="2.0",
                    section508=True,
                    category="structure",
                    fixable=True,
                    fix_action="set_title",
                    current_value=text,
                    target={"slide": i, "scope": "slide_title"},
                )
            )

    # --- duplicate titles ---
    # Normalize: lowercase + collapse whitespace
    norm: dict[str, list[int]] = {}
    for i, text in titled:
        key = re.sub(r"\s+", " ", text.lower().strip())
        norm.setdefault(key, []).append(i)

    for key, indices in norm.items():
        if len(indices) < 2:
            continue
        for i in indices:
            # Recover the original text for current_value
            orig_text = next(t for idx, t in titled if idx == i)
            findings.append(
                Finding(
                    check_id="title_quality",
                    severity=Severity.WARNING,
                    slide_index=i,
                    message="Slide title is duplicated on another slide; make each unique.",
                    suggestion="Use a unique, descriptive title.",
                    sc_refs=["2.4.6"],
                    wcag_version="2.0",
                    section508=True,
                    category="structure",
                    fixable=True,
                    fix_action="set_title",
                    current_value=orig_text,
                    target={"slide": i, "scope": "slide_title"},
                )
            )

    return findings
