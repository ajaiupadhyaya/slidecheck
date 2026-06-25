"""
pptx_a11y.analyze — run checks, generate suggestions, and produce a JSON-safe
analysis dict.

Public API
----------
- run_checks(prs) -> list[Finding]
- generate_suggestions(prs, findings, describer) -> None   (mutates in place)
- finding_to_dict(f) -> dict                               (JSON-safe)
- analyze(prs, describer) -> dict
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pptx_a11y import checks as _checks_mod
from pptx_a11y import imageutil, refs, standards
from pptx_a11y.models import Finding

if TYPE_CHECKING:
    from pptx_a11y.alt_text_ai import Describer


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------

def run_checks(prs) -> list[Finding]:
    """Run every registered check against *prs* and return a flat finding list.

    The deck is NOT mutated — checks are read-only.
    """
    all_checks = _checks_mod.load_all()
    findings: list[Finding] = []
    for check in all_checks:
        findings.extend(check(prs))
    return findings


# ---------------------------------------------------------------------------
# Internal helpers for generate_suggestions
# ---------------------------------------------------------------------------

def _slide_text(prs, slide_index: int, max_chars: int = 400) -> str:
    """Return up to *max_chars* characters of concatenated text from a slide."""
    try:
        slide = prs.slides[slide_index]
    except IndexError:
        return ""
    parts: list[str] = []
    total = 0
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                t = para.text.strip()
                if t:
                    remaining = max_chars - total
                    if remaining <= 0:
                        break
                    parts.append(t[:remaining])
                    total += len(t)
    return " ".join(parts)[:max_chars]


def _presentation_text(prs, max_chars: int = 400) -> str:
    """Return text from the first slide that has any content."""
    for i in range(len(prs.slides)):
        t = _slide_text(prs, i, max_chars)
        if t:
            return t
    return ""


# ---------------------------------------------------------------------------
# generate_suggestions
# ---------------------------------------------------------------------------

def generate_suggestions(prs, findings: list[Finding], describer: "Describer") -> None:
    """Fill *finding.suggested_value* in-place using deterministic logic or *describer*.

    Deterministic actions never call the describer.
    AI actions (set_alt_text, set_title, set_link_text, set_doc_title) call the
    describer; NullDescriber yields None and that is stored as-is.

    Already-set suggested_value values are preserved (not overwritten).
    """
    for f in findings:
        action = f.fix_action
        if action is None:
            continue

        # --- Deterministic: no AI needed --------------------------------

        if action == "bump_font_size":
            if f.suggested_value is None:
                f.suggested_value = "18"
            continue

        if action == "set_doc_language":
            if f.suggested_value is None:
                f.suggested_value = "en-US"
            continue

        # Contrast check pre-populates suggested_value with a compliant hex;
        # keep it.  If for some reason it is absent, leave None.
        if action == "apply_contrast_color":
            # Already set by the contrast check — nothing to do.
            continue

        # Table header and decorative marking require human judgment.
        if action in ("set_table_header", "mark_decorative"):
            continue

        # --- AI-assisted paths ------------------------------------------

        if action == "set_alt_text":
            if f.suggested_value is not None:
                continue
            obj = refs.resolve_target(prs, f.target)
            if obj is None:
                continue
            result = imageutil.image_bytes_and_type(obj)
            if result is None:
                continue
            blob, media_type = result
            context = _slide_text(prs, f.slide_index) or f.message
            f.suggested_value = describer.describe(blob, media_type, context)
            continue

        if action == "set_title":
            if f.suggested_value is not None:
                continue
            slide_txt = _slide_text(prs, f.slide_index, 400)
            prompt = (
                "Write a 3-6 word descriptive slide title for a slide containing: "
                + slide_txt
            )
            f.suggested_value = describer.suggest_text(prompt)
            continue

        if action == "set_link_text":
            if f.suggested_value is not None:
                continue
            obj = refs.resolve_target(prs, f.target)
            url = ""
            surrounding = ""
            if obj is not None:
                try:
                    url = obj.hyperlink.address or ""
                except Exception:  # noqa: BLE001
                    pass
                try:
                    # surrounding text = the paragraph text
                    surrounding = obj._r.getparent().text or ""
                except Exception:  # noqa: BLE001
                    surrounding = f.message
            prompt = (
                "Write concise descriptive link text (3-6 words) for a hyperlink to "
                + url
                + " in context: "
                + surrounding
            )
            f.suggested_value = describer.suggest_text(prompt)
            continue

        if action == "set_doc_title":
            if f.suggested_value is not None:
                continue
            pres_text = _presentation_text(prs, 400)
            if pres_text:
                prompt = (
                    "Write a 3-6 word descriptive document title for a presentation "
                    "containing: " + pres_text
                )
                result = describer.suggest_text(prompt)
                f.suggested_value = result if result else "Presentation"
            else:
                f.suggested_value = "Presentation"
            continue

        # Unknown action — leave suggested_value as-is.


# ---------------------------------------------------------------------------
# finding_to_dict
# ---------------------------------------------------------------------------

def finding_to_dict(f: Finding) -> dict:
    """Return a JSON-safe dict representation of a Finding.

    All fields are included.  Enums are serialized to their .value string.
    The synthetic 'id' field is a stable string combining check_id, slide_index,
    and shape_ref.
    """
    return {
        "id": f"{f.check_id}:{f.slide_index}:{f.shape_ref or ''}",
        "check_id": f.check_id,
        "severity": f.severity.value,
        "slide_index": f.slide_index,
        "message": f.message,
        "shape_ref": f.shape_ref,
        "suggestion": f.suggestion,
        "auto_fixed": f.auto_fixed,
        "sc_refs": list(f.sc_refs),
        "wcag_version": f.wcag_version,
        "section508": f.section508,
        "category": f.category,
        "fixable": f.fixable,
        "fix_action": f.fix_action,
        "current_value": f.current_value,
        "suggested_value": f.suggested_value,
        "target": f.target,
    }


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def analyze(prs, describer: "Describer") -> dict:
    """Run all checks, generate suggestions, score, and return a JSON-safe dict.

    Returns:
        {
            "findings": [finding_to_dict(f), ...],
            "score":    standards.score(findings),
            "coverage": standards.coverage_matrix(findings),
        }
    """
    findings = run_checks(prs)
    generate_suggestions(prs, findings, describer)
    return {
        "findings": [finding_to_dict(f) for f in findings],
        "score": standards.score(findings),
        "coverage": standards.coverage_matrix(findings),
    }
