from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx_a11y.checks import iter_shapes
from pptx_a11y.fixers import register
from pptx_a11y.imageutil import image_bytes_and_type
from pptx_a11y.models import Change
from pptx_a11y.refs import shape_ref


def _alt(shape) -> str:
    try:
        return shape._element._nvXxPr.cNvPr.get("descr") or ""
    except Exception:  # noqa: BLE001
        return ""


@register
def fix(prs, describer) -> list[Change]:
    changes = []
    for slide_index, shape in iter_shapes(prs):
        if shape.shape_type != MSO_SHAPE_TYPE.PICTURE:
            continue
        if _alt(shape).strip():
            continue
        payload = image_bytes_and_type(shape)
        if payload is None:
            continue
        blob, media_type = payload
        desc = describer.describe(blob, media_type, f"slide {slide_index + 1}")
        if not desc:
            continue
        shape._element._nvXxPr.cNvPr.set("descr", desc)
        changes.append(
            Change(
                fixer_id="alt_text",
                slide_index=slide_index,
                shape_ref=shape_ref(slide_index, shape),
                description=f'Added alt text: "{desc}"',
                machine_generated=True,
            )
        )
    return changes
