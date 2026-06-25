"""Stateless export service for the SlideCheck web layer.

Entrypoint
----------
    export_with_plan(filename, data, plan) -> dict

Opens *data* bytes inside an ephemeral TemporaryDirectory, applies the fix
plan, saves the corrected deck, re-analyzes the result to produce an honest
"after" report, then returns everything as a dict.  Nothing persists;
the original bytes are never mutated.
"""
from __future__ import annotations

import os
import tempfile

from pptx import Presentation

from pptx_a11y.analyze import run_checks
from pptx_a11y.appliers import apply_plan
from pptx_a11y.models import Change, FileResult
from pptx_a11y.report.html_report import render


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0] or "upload"


def export_with_plan(filename: str, data: bytes, plan: list[dict]) -> dict:
    """Apply *plan* to *data* bytes and return fixed bytes plus an honest report.

    The original *data* bytes are never modified; all work happens inside an
    ephemeral TemporaryDirectory that is removed before return.

    Parameters
    ----------
    filename:
        Original filename (used in the report and output filename).
    data:
        Raw bytes of the source .pptx.
    plan:
        List of fix-plan items accepted by ``appliers.apply_plan``.
        Each item is ``{"action": str, "target": dict, "value": Any}``.

    Returns
    -------
    On success::

        {
            "filename":       str,
            "error":          None,
            "fixed_filename": str,          # e.g. "lecture_accessible.pptx"
            "fixed_bytes":    bytes,
            "report_html":    str,          # honest "after" accessibility report
            "applied":        [{"action": str, "ok": bool}, ...],
        }

    On load failure::

        {
            "filename":       str,
            "error":          str,          # friendly; no temp-path leak
            "fixed_filename": None,
            "fixed_bytes":    None,
            "report_html":    None,
            "applied":        [],
        }
    """
    with tempfile.TemporaryDirectory() as tmp:
        stem = _stem(filename)
        in_path = os.path.join(tmp, f"{stem}.pptx")
        try:
            with open(in_path, "wb") as fh:
                fh.write(data)
            prs = Presentation(in_path)
        except Exception as exc:  # noqa: BLE001
            friendly = str(exc).replace(in_path, filename)
            return {
                "filename": filename,
                "error": friendly,
                "fixed_filename": None,
                "fixed_bytes": None,
                "report_html": None,
                "applied": [],
            }

        applied = apply_plan(prs, plan)

        fixed_filename = f"{stem}_accessible.pptx"
        out_path = os.path.join(tmp, fixed_filename)
        prs.save(out_path)

        with open(out_path, "rb") as fh:
            fixed_bytes = fh.read()

        # Honest "after" report: re-open the saved deck and re-run checks so
        # the report reflects what the output file actually contains.
        prs_fixed = Presentation(out_path)
        residual = run_checks(prs_fixed)

        changes = [
            Change(fixer_id=a["action"], slide_index=0, description=a["action"])
            for a in applied
            if a["ok"]
        ]

        file_result = FileResult(
            source_path=filename,
            output_path=fixed_filename,
            findings=residual,
            changes=changes,
        )
        report_html = render(file_result)

        return {
            "filename": filename,
            "error": None,
            "fixed_filename": fixed_filename,
            "fixed_bytes": fixed_bytes,
            "report_html": report_html,
            "applied": applied,
        }
