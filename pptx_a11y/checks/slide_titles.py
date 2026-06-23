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
                )
            )
    return findings
