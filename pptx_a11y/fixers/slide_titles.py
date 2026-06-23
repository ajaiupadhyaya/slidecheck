from pptx_a11y.fixers import register
from pptx_a11y.models import Change


def _slide_text(slide) -> str:
    parts = []
    for shape in slide.shapes:
        if shape.has_text_frame and shape.text_frame.text.strip():
            parts.append(shape.text_frame.text.strip())
    return " ".join(parts)[:500]


@register
def fix(prs, describer) -> list[Change]:
    changes = []
    for i, slide in enumerate(prs.slides):
        title = slide.shapes.title
        if title is None:
            continue  # no title placeholder to fill; left as a finding
        if title.text.strip():
            continue
        context = _slide_text(slide) or f"slide {i + 1}"
        suggestion = describer.suggest_text(
            f"Suggest a concise, descriptive slide title (3-6 words, no quotes) "
            f"for a slide containing this text: {context}. Respond with only the title."
        )
        new_title = (suggestion or f"Slide {i + 1}").strip()
        title.text = new_title
        changes.append(
            Change(
                fixer_id="slide_title",
                slide_index=i,
                description=f'Added slide title: "{new_title}"',
                machine_generated=bool(suggestion),
            )
        )
    return changes
