from pptx_a11y.fixers import register
from pptx_a11y.models import Change


@register
def fix(prs, describer) -> list[Change]:
    changes = []
    if not (prs.core_properties.title or "").strip():
        first_title = ""
        if len(prs.slides) and prs.slides[0].shapes.title is not None:
            first_title = prs.slides[0].shapes.title.text.strip()
        new = first_title or "Presentation"
        prs.core_properties.title = new
        changes.append(
            Change(
                fixer_id="metadata",
                slide_index=0,
                description=f'Set document title to "{new}".',
                machine_generated=False,
            )
        )
    return changes
