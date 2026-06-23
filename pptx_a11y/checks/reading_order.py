from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


@register
def check(prs) -> list[Finding]:
    """Conservative: flag slides with many shapes where no title comes first,
    a common screen-reader reading-order problem."""
    findings = []
    for i, slide in enumerate(prs.slides):
        shapes = list(slide.shapes)
        if len(shapes) <= 1:
            continue
        title = slide.shapes.title
        if title is not None and shapes[0] is not title:
            findings.append(
                Finding(
                    check_id="reading_order",
                    severity=Severity.INFO,
                    slide_index=i,
                    message="Slide title is not first in the reading order.",
                    suggestion="Check the selection pane so the title is read first.",
                )
            )
    return findings
