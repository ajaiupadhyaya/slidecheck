from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


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
