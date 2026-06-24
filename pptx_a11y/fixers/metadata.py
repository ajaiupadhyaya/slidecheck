from pptx_a11y.fixers import register
from pptx_a11y.models import Change


_DEFAULT_LANGUAGE = "en-US"


@register
def fix(prs, describer) -> list[Change]:
    changes = []
    cp = prs.core_properties
    if not (cp.title or "").strip():
        first_title = ""
        if len(prs.slides) and prs.slides[0].shapes.title is not None:
            first_title = prs.slides[0].shapes.title.text.strip()
        new = first_title or "Presentation"
        cp.title = new
        changes.append(
            Change(
                fixer_id="metadata",
                slide_index=0,
                shape_ref="doc:title",
                description=f'Set document title to "{new}".',
                machine_generated=False,
            )
        )
    if not (cp.language or "").strip():
        cp.language = _DEFAULT_LANGUAGE
        changes.append(
            Change(
                fixer_id="metadata",
                slide_index=0,
                shape_ref="doc:language",
                description=f'Set document language to "{_DEFAULT_LANGUAGE}" (review if the deck is not in English).',
                machine_generated=False,
            )
        )
    return changes
