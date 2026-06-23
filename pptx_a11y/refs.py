def shape_ref(slide_index: int, shape) -> str:
    """Stable, human-readable reference for a shape within a slide."""
    return f"slide{slide_index}:shape{shape.shape_id}"
