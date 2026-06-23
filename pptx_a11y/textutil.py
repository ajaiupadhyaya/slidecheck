from pptx.util import Pt


def iter_runs(prs):
    for i, slide in enumerate(prs.slides):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    yield i, shape, para, run


def run_rgb(run):
    try:
        color = run.font.color
        if color and color.type is not None and color.rgb is not None:
            rgb = color.rgb
            return (rgb[0], rgb[1], rgb[2])
    except Exception:  # noqa: BLE001 - theme/inherited colors are unresolvable here
        return None
    return None


def run_pt(run) -> float | None:
    sz = run.font.size
    return sz.pt if sz is not None else None
