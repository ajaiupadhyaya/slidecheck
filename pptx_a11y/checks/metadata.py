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
                # standards + remediation metadata
                sc_refs=["2.4.2"],
                wcag_version="2.0",
                section508=True,
                category="document",
                fixable=True,
                fix_action="set_doc_title",
                current_value=None,
                target={"scope": "document", "field": "title"},
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
                # standards + remediation metadata
                sc_refs=["3.1.1"],
                wcag_version="2.0",
                section508=True,
                category="document",
                fixable=True,
                fix_action="set_doc_language",
                current_value=None,
                target={"scope": "document", "field": "language"},
            )
        )
    return findings
