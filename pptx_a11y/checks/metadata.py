from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


@register
def check(prs) -> list[Finding]:
    findings = []
    cp = prs.core_properties
    if not (cp.title or "").strip():
        findings.append(
            Finding(
                check_id="metadata",
                severity=Severity.WARNING,
                slide_index=0,
                shape_ref="doc:title",
                message="Presentation is missing a document title.",
                suggestion="Set the document title in file properties.",
            )
        )
    if not (cp.language or "").strip():
        findings.append(
            Finding(
                check_id="metadata",
                severity=Severity.WARNING,
                slide_index=0,
                shape_ref="doc:language",
                message="Presentation has no document language set.",
                suggestion="Set the document language so screen readers pronounce text correctly.",
            )
        )
    return findings
