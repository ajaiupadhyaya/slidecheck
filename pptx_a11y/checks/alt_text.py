from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes, register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref, shape_target

_VISUAL_TYPES = {MSO_SHAPE_TYPE.PICTURE, MSO_SHAPE_TYPE.LINKED_PICTURE, MSO_SHAPE_TYPE.CHART}

# Namespace PowerPoint uses when a shape is flagged via "Mark as Decorative".
_DECORATIVE_NS = "http://schemas.microsoft.com/office/drawing/2017/decorative"


def _alt(shape) -> str:
    try:
        return shape._element._nvXxPr.cNvPr.get("descr") or ""
    except Exception:  # noqa: BLE001
        return ""


def _is_decorative(shape) -> bool:
    # A decorative image needs no alt text, so it must not be flagged. Detect
    # both (a) PowerPoint's native "Mark as Decorative" — an <adec:decorative>
    # extension element inside cNvPr — and (b) a "decorative" title, used as a
    # manual workaround in older PowerPoint versions.
    try:
        cNvPr = shape._element._nvXxPr.cNvPr
    except Exception:  # noqa: BLE001
        return False
    if (cNvPr.get("title") or "").strip().lower() == "decorative":
        return True
    for dec in cNvPr.iter(f"{{{_DECORATIVE_NS}}}decorative"):
        if (dec.get("val") or "1") not in ("0", "false"):
            return True
    return False


@register
def check(prs) -> list[Finding]:
    findings = []
    for slide_index, shape in iter_shapes(prs):
        if shape.shape_type not in _VISUAL_TYPES:
            continue
        if _is_decorative(shape):
            continue
        current_descr = _alt(shape)
        if not current_descr.strip():
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
                    # standards + remediation metadata
                    sc_refs=["1.1.1"],
                    wcag_version="2.0",
                    section508=True,
                    category="images",
                    fixable=True,
                    fix_action="set_alt_text",
                    current_value=current_descr,
                    target=shape_target(slide_index, shape),
                )
            )
    return findings
