"""Stateless analyze service for the SlideCheck web layer.

Entrypoint
----------
    analyze_upload(filename, data, describer) -> dict

Opens *data* bytes inside an ephemeral TemporaryDirectory, runs all checks,
attaches per-finding thumbnails for image-related findings, then returns
a JSON-safe dict.  Nothing persists after return.
"""
from __future__ import annotations

import base64
import os
import tempfile
from io import BytesIO

from PIL import Image
from pptx import Presentation

from pptx_a11y.analyze import analyze
from pptx_a11y.imageutil import image_bytes_and_type
from pptx_a11y.refs import resolve_target


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0] or "upload"


# Actions for which we try to attach a thumbnail preview.
_THUMBNAIL_ACTIONS = frozenset({"set_alt_text", "mark_decorative"})
_THUMB_SIZE = (160, 160)


def analyze_upload(filename: str, data: bytes, describer) -> dict:
    """Analyze *data* bytes as a .pptx file and return a JSON-safe result dict.

    Returns:
        {
            "filename": str,
            "error":    str | None,
            "analysis": {
                "findings": [...],   # each finding may have a "thumbnail" key
                "score":    {...},
                "coverage": [...],
            } | None,
        }

    On load failure the error message uses *filename* instead of the internal
    temp path so no server internals leak to the caller.

    Per-finding thumbnails:
        For every finding whose ``fix_action`` is ``"set_alt_text"`` or
        ``"mark_decorative"``, the service resolves the target shape, reads its
        image bytes, resizes to at most 160×160 pixels, and stores a
        ``data:image/png;base64,...`` string under the ``"thumbnail"`` key.
        A failure for any individual thumbnail is silently swallowed — the
        overall analysis is never aborted.
    """
    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, f"{_stem(filename)}.pptx")
        try:
            with open(in_path, "wb") as fh:
                fh.write(data)
            prs = Presentation(in_path)
        except Exception as exc:  # noqa: BLE001
            friendly = str(exc).replace(in_path, filename)
            return {"filename": filename, "error": friendly, "analysis": None}

        result = analyze(prs, describer)

        # Attach thumbnails — per-finding try/except so a bad image never
        # prevents the overall analysis from returning.
        for finding in result["findings"]:
            if finding.get("fix_action") not in _THUMBNAIL_ACTIONS:
                continue
            try:
                shape = resolve_target(prs, finding["target"])
                if shape is None:
                    continue
                img_result = image_bytes_and_type(shape)
                if img_result is None:
                    continue
                blob, _ = img_result
                img = Image.open(BytesIO(blob))
                img.thumbnail(_THUMB_SIZE)
                buf = BytesIO()
                img.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                finding["thumbnail"] = "data:image/png;base64," + b64
            except Exception:  # noqa: BLE001
                pass  # bad image must not abort the analysis

        return {"filename": filename, "error": None, "analysis": result}
