from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes, register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref


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
                )
            )
    return findings
