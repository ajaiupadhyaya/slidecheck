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


_META_MARKERS = (
    "cut off", "could you", "i'd be happy", "i would be happy", "please share",
    "please provide", "as an ai", "i don't have", "i do not have", "i cannot",
    "i can't", "let me know", "happy to help", "it looks like", "i'm unable",
    "i am unable", "without seeing", "more context",
)


def _clean_suggestion(text: str | None, max_len: int = 90) -> str | None:
    """Tidy a model suggestion for display: strip surrounding markdown/quotes and
    drop obvious non-answers (refusals, rambles, over-long text), so the textarea
    shows a clean, usable value or nothing (the user can then type their own)."""
    if not text:
        return None
    s = text.strip()
    for mark in ("**", "*", "`", "_"):
        while s.startswith(mark) and s.endswith(mark) and len(s) > 2 * len(mark):
            s = s[len(mark):-len(mark)].strip()
    quotes = ('"', "'", "“", "”", "‘", "’")
    while len(s) >= 2 and s[0] in quotes and s[-1] in quotes:
        s = s[1:-1].strip()
    if not s or len(s) > max_len:
        return None
    low = s.lower()
    if any(m in low for m in _META_MARKERS):
        return None
    return s


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
            f.suggested_value = _clean_suggestion(
                describer.describe(blob, media_type, context), 300
            )
            continue

        if action == "set_title":
            if f.suggested_value is not None:
                continue
            slide_txt = _slide_text(prs, f.slide_index, 400)
            prompt = (
                "Suggest a 3-6 word descriptive slide title for a slide containing: "
                + slide_txt
                + "\n\nReply with ONLY the title text — no quotes, no markdown, no explanation."
            )
            f.suggested_value = _clean_suggestion(describer.suggest_text(prompt), 90)
            continue

        if action == "set_link_text":
            if f.suggested_value is not None:
                continue
            obj = refs.resolve_target(prs, f.target)
            url = ""
            if obj is not None:
                try:
                    url = obj.hyperlink.address or ""
                except Exception:  # noqa: BLE001
                    pass
            surrounding = _slide_text(prs, f.slide_index, 200)
            prompt = (
                "Suggest concise descriptive link text (2-6 words) for a hyperlink to "
                + (url or "a web page")
                + (" on a slide about: " + surrounding if surrounding else "")
                + "\n\nReply with ONLY the link text — no quotes, no markdown, no explanation."
            )
            f.suggested_value = _clean_suggestion(describer.suggest_text(prompt), 90)
            continue

        if action == "set_doc_title":
            if f.suggested_value is not None:
                continue
            pres_text = _presentation_text(prs, 400)
            if pres_text:
                prompt = (
                    "Suggest a 3-6 word descriptive document title for a presentation "
                    "containing: " + pres_text
                    + "\n\nReply with ONLY the title text — no quotes, no markdown, no explanation."
                )
                result = _clean_suggestion(describer.suggest_text(prompt), 90)
                f.suggested_value = result if result else "Presentation"
            else:
                f.suggested_value = "Presentation"
            continue

        # Unknown action — leave suggested_value as-is.


# ---------------------------------------------------------------------------
# finding_to_dict
# ---------------------------------------------------------------------------

def finding_to_dict(f: Finding, index: int | None = None) -> dict:
    """Return a JSON-safe dict representation of a Finding.

    All fields are included.  Enums are serialized to their .value string.
    The synthetic 'id' field combines check_id, slide_index, shape_ref, and —
    when ``index`` is given — the finding's position in the response.  The
    position suffix guarantees ids are UNIQUE within a single analysis even
    when two findings share check_id + slide + shape_ref (e.g. two hyperlink
    runs in one text box, or a table that is both header-less and has merged
    cells).  The client keys its fix-plan and live score by this id, so a
    collision would otherwise silently drop an accepted fix or inflate the
    score.
    """
    suffix = f":{index}" if index is not None else ""
    return {
        "id": f"{f.check_id}:{f.slide_index}:{f.shape_ref or ''}{suffix}",
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
        "findings": [finding_to_dict(f, i) for i, f in enumerate(findings)],
        "score": standards.score(findings),
        "coverage": standards.coverage_matrix(findings),
    }
