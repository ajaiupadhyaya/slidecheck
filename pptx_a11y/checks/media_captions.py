from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes, register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref, shape_target


@register
def check(prs) -> list[Finding]:
    findings = []
    for slide_index, shape in iter_shapes(prs):
        if shape.shape_type == MSO_SHAPE_TYPE.MEDIA:
            findings.append(
                Finding(
                    check_id="media",
                    severity=Severity.WARNING,
                    slide_index=slide_index,
                    shape_ref=shape_ref(slide_index, shape),
                    message="Embedded media may lack captions.",
                    suggestion="Provide captions/transcript for audio and video.",
                    # standards + remediation metadata
                    sc_refs=["1.2.2"],
                    wcag_version="2.0",
                    section508=True,
                    category="media",
                    fixable=False,
                    fix_action=None,
                    current_value=None,
                    target=shape_target(slide_index, shape),
                )
            )
    return findings
