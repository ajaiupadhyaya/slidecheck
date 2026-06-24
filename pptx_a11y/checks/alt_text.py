from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes, register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref

_VISUAL_TYPES = {MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.LINKED_PICTURE, MSO_SHAPE_TYPE.CHART}


def _alt(shape) -> str:
    try:
        return shape._element._nvXxPr.cNvPr.get("descr") or ""
    except Exception:  # noqa: BLE001
        return ""


def _is_decorative(shape) -> bool:
    # PowerPoint marks decorative images with a specific extension; treat a
    # title of "decorative" as decorative for our purposes (and skip).
    try:
        return (shape._element._nvXxPr.cNvPr.get("title") or "").strip().lower() == "decorative"
    except Exception:  # noqa: BLE001
        return False


@register
def check(prs) -> list[Finding]:
    findings = []
    for slide_index, shape in iter_shapes(prs):
        if shape.shape_type not in _VISUAL_TYPES:
            continue
        if _is_decorative(shape):
            continue
        if not _alt(shape).strip():
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                message = "Image is missing alternative text."
                suggestion = "Add a short description of the image's content/purpose."
            else:
                kind = "Chart" if shape.shape_type == MSO_SHAPE_TYPE.CHART else "Linked image"
                message = f"{kind} is missing alternative text."
                suggestion = (
                    "Add a description manually in PowerPoint — charts and linked "
                    "images cannot be auto-described."
                )
            findings.append(
                Finding(
                    check_id="alt_text",
                    severity=Severity.ERROR,
                    slide_index=slide_index,
                    shape_ref=shape_ref(slide_index, shape),
                    message=message,
                    suggestion=suggestion,
                )
            )
    return findings
