from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


@register
def check(prs) -> list[Finding]:
    findings = []
    if not (prs.core_properties.title or "").strip():
        findings.append(
            Finding(
                check_id="metadata",
                severity=Severity.WARNING,
                slide_index=0,
                message="Presentation is missing a document title.",
                suggestion="Set the document title in file properties.",
            )
        )
    return findings
