from pptx.enum.shapes import MSO_SHAPE_TYPE


def iter_shapes(prs):
    """Yield (slide_index, shape) for every shape, descending into groups."""
    for i, slide in enumerate(prs.slides):
        yield from _walk(i, slide.shapes)


def _walk(slide_index, shapes):
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(slide_index, shape.shapes)
        else:
            yield slide_index, shape


ALL_CHECKS = []  # populated by register() below


def register(fn):
    ALL_CHECKS.append(fn)
    return fn
