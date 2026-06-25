"""Deterministic fix-applier registry.

Each applier has the signature:
    apply(prs, target: dict, value) -> bool

True  = mutation applied successfully.
False = target unresolvable, precondition not met, or action not applicable.

Appliers NEVER raise; all exceptions are caught and return False.
No AI / network calls are made here.
"""
from __future__ import annotations

from pptx_a11y.refs import resolve_target

# Namespace for <adec:decorative>
_ADEC_NS = "http://schemas.microsoft.com/office/drawing/2017/decorative"


# ---------------------------------------------------------------------------
# Individual appliers
# ---------------------------------------------------------------------------

def set_alt_text(prs, target: dict, value) -> bool:
    """Set the alt-text description on a picture or shape."""
    try:
        shape = resolve_target(prs, target)
        if shape is None:
            return False
        # Must be a shape (not a run/prs) with an nvXxPr element
        cNvPr = shape._element._nvXxPr.cNvPr
        cNvPr.set("descr", str(value))
        return True
    except Exception:  # noqa: BLE001
        return False


def mark_decorative(prs, target: dict, value) -> bool:  # noqa: ARG001
    """Add <adec:decorative val="1"> under cNvPr to mark a shape decorative."""
    try:
        from lxml import etree

        shape = resolve_target(prs, target)
        if shape is None:
            return False
        cNvPr = shape._element._nvXxPr.cNvPr
        # Remove any existing adec:decorative to avoid duplicates
        existing = cNvPr.find(f"{{{_ADEC_NS}}}decorative")
        if existing is not None:
            cNvPr.remove(existing)
        etree.SubElement(cNvPr, f"{{{_ADEC_NS}}}decorative", val="1")
        return True
    except Exception:  # noqa: BLE001
        return False


def set_title(prs, target: dict, value) -> bool:
    """Set the title placeholder text on a slide.

    target must contain {"slide": i, "scope": "slide_title"}.
    Returns False if the slide has no title placeholder.
    """
    try:
        slide_idx = target.get("slide")
        if slide_idx is None:
            return False
        slide = prs.slides[slide_idx]
        title_shape = slide.shapes.title
        if title_shape is None:
            return False
        title_shape.text = str(value)
        return True
    except Exception:  # noqa: BLE001
        return False


def set_doc_title(prs, target: dict, value) -> bool:  # noqa: ARG001
    """Set the document-level title in core properties."""
    try:
        prs.core_properties.title = str(value)
        return True
    except Exception:  # noqa: BLE001
        return False


def set_doc_language(prs, target: dict, value) -> bool:  # noqa: ARG001
    """Set the document-level language tag in core properties."""
    try:
        prs.core_properties.language = str(value)
        return True
    except Exception:  # noqa: BLE001
        return False


def set_link_text(prs, target: dict, value) -> bool:
    """Update the display text of a hyperlink run.

    The run's rPr (which carries the hyperlink relationship) is preserved;
    only run.text is changed.
    """
    try:
        run = resolve_target(prs, target)
        # A Run has .hyperlink; a Shape or Presentation does not.
        # Guard prevents shape-level targets from corrupting the text frame.
        if run is None or not hasattr(run, "hyperlink"):
            return False
        run.text = str(value)
        return True
    except Exception:  # noqa: BLE001
        return False


def set_table_header(prs, target: dict, value) -> bool:  # noqa: ARG001
    """Enable the header-row style on a table shape."""
    try:
        shape = resolve_target(prs, target)
        if shape is None:
            return False
        if not shape.has_table:
            return False
        shape.table.first_row = True
        return True
    except Exception:  # noqa: BLE001
        return False


def apply_contrast_color(prs, target: dict, value) -> bool:
    """Set the font colour on a run.

    *value* may be:
    - a list/tuple [r, g, b] with integers 0-255
    - a hex string "#rrggbb"
    """
    try:
        from pptx.dml.color import RGBColor

        run = resolve_target(prs, target)
        # Defense-in-depth: only operate on a Run (has .hyperlink), not a Shape.
        if run is None or not hasattr(run, "hyperlink"):
            return False

        if isinstance(value, str):
            # Strip leading "#" and parse hex
            hex_val = value.lstrip("#")
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
        else:
            r, g, b = int(value[0]), int(value[1]), int(value[2])

        run.font.color.rgb = RGBColor(r, g, b)
        return True
    except Exception:  # noqa: BLE001
        return False


def bump_font_size(prs, target: dict, value) -> bool:
    """Set the font size on a run, enforcing a minimum of 18 pt."""
    try:
        from pptx.util import Pt

        run = resolve_target(prs, target)
        # Defense-in-depth: only operate on a Run (has .hyperlink), not a Shape.
        if run is None or not hasattr(run, "hyperlink"):
            return False
        run.font.size = Pt(max(18, int(value)))
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

APPLIERS: dict[str, callable] = {
    "set_alt_text": set_alt_text,
    "mark_decorative": mark_decorative,
    "set_title": set_title,
    "set_doc_title": set_doc_title,
    "set_doc_language": set_doc_language,
    "set_link_text": set_link_text,
    "set_table_header": set_table_header,
    "apply_contrast_color": apply_contrast_color,
    "bump_font_size": bump_font_size,
}


# ---------------------------------------------------------------------------
# apply_plan
# ---------------------------------------------------------------------------

def apply_plan(prs, plan: list[dict]) -> list[dict]:
    """Apply a list of fix items to *prs* in order.

    Each item must be a dict with keys: "action", "target", "value".

    Returns a parallel list of result dicts: {"action": str, "ok": bool}.
    A single failing item never aborts the rest of the plan.
    """
    results: list[dict] = []
    for item in plan:
        action = item.get("action", "")
        target = item.get("target", {})
        value = item.get("value")
        try:
            fn = APPLIERS.get(action)
            if fn is None:
                results.append({"action": action, "ok": False})
                continue
            ok = fn(prs, target, value)
            results.append({"action": action, "ok": bool(ok)})
        except Exception:  # noqa: BLE001
            results.append({"action": action, "ok": False})
    return results
