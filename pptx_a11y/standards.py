"""
WCAG 2.x / Section 508 standards catalog, accessibility score, and coverage matrix.

Pure module — no I/O, no python-pptx, deterministic.

Section 508 floor = WCAG 2.0 Level A/AA (section508=True for version=="2.0").
WCAG 2.1 and 2.2 SCs are best-practice (section508=False).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pptx_a11y.models import Finding


# ---------------------------------------------------------------------------
# SC Catalog
# ---------------------------------------------------------------------------
# Keys: SC number string.  Values: title, level, version, section508, static_applicable.
# 4.1.1 (Parsing) is intentionally excluded — it was made obsolete in WCAG 2.2.
# static_applicable=False → the SC is interactive-only; coverage rows show N_A.

SC_CATALOG: dict[str, dict] = {
    # ── Perceivable ────────────────────────────────────────────────────────
    "1.1.1": {
        "title": "Non-text Content",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.2.2": {
        "title": "Captions (Prerecorded)",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.3.1": {
        "title": "Info and Relationships",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.3.2": {
        "title": "Meaningful Sequence",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.3.3": {
        "title": "Sensory Characteristics",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.3.4": {
        "title": "Orientation",
        "level": "AA",
        "version": "2.1",
        "section508": False,
        "static_applicable": True,
    },
    # Interactive-only — applies to form-input autocomplete, never to static slides.
    "1.3.5": {
        "title": "Identify Input Purpose",
        "level": "AA",
        "version": "2.1",
        "section508": False,
        "static_applicable": False,
    },
    "1.4.1": {
        "title": "Use of Color",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.4.2": {
        "title": "Audio Control",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.4.3": {
        "title": "Contrast (Minimum)",
        "level": "AA",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.4.4": {
        "title": "Resize Text",
        "level": "AA",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.4.5": {
        "title": "Images of Text",
        "level": "AA",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "1.4.11": {
        "title": "Non-text Contrast",
        "level": "AA",
        "version": "2.1",
        "section508": False,
        "static_applicable": True,
    },
    # ── Operable ───────────────────────────────────────────────────────────
    "2.2.2": {
        "title": "Pause, Stop, Hide",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "2.3.1": {
        "title": "Three Flashes or Below Threshold",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "2.4.2": {
        "title": "Page Titled",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "2.4.4": {
        "title": "Link Purpose (In Context)",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "2.4.6": {
        "title": "Headings and Labels",
        "level": "AA",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    # Interactive-only — N_A for static presentations
    "2.4.11": {
        "title": "Focus Not Obscured (Minimum)",
        "level": "AA",
        "version": "2.2",
        "section508": False,
        "static_applicable": False,
    },
    "2.5.7": {
        "title": "Dragging Movements",
        "level": "AA",
        "version": "2.2",
        "section508": False,
        "static_applicable": False,
    },
    "2.5.8": {
        "title": "Target Size (Minimum)",
        "level": "AA",
        "version": "2.2",
        "section508": False,
        "static_applicable": False,
    },
    # ── Understandable ─────────────────────────────────────────────────────
    "3.1.1": {
        "title": "Language of Page",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    "3.1.2": {
        "title": "Language of Parts",
        "level": "AA",
        "version": "2.0",
        "section508": True,
        "static_applicable": True,
    },
    # Interactive-only
    "3.3.8": {
        "title": "Accessible Authentication (Minimum)",
        "level": "A",
        "version": "2.2",
        "section508": False,
        "static_applicable": False,
    },
    # ── Robust ─────────────────────────────────────────────────────────────
    # Interactive-only (name/role/value applies to UI components)
    "4.1.2": {
        "title": "Name, Role, Value",
        "level": "A",
        "version": "2.0",
        "section508": True,
        "static_applicable": False,
    },
    # NOTE: 4.1.1 (Parsing) is intentionally absent — obsoleted by WCAG 2.2.
}

# SCs the tool can only flag for human judgment — never auto-pass.
# 1.3.4 (Orientation), 1.4.2 (Audio Control), and 3.1.2 (Language of Parts)
# have no reliable automated detector for slide decks (3.1.2 would require
# language identification of unmarked text), so they are surfaced for human
# review rather than reported as a (misleading) structural PASS.
NEEDS_REVIEW_SC: set[str] = {
    "1.4.1", "1.2.2", "1.3.2", "1.4.5", "1.4.11", "2.3.1",
    "1.3.4", "1.4.2", "3.1.2",
}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
_DEDUCTION = {"error": 8, "warning": 3, "info": 1}
_GRADE_THRESHOLDS = ((95, "A"), (85, "B"), (70, "C"), (55, "D"))


def score(findings: list[Finding]) -> dict:
    """
    Compute a deterministic 0-100 accessibility score from a findings list.

    Only OPEN findings (auto_fixed=False) count against the score.
    Returns: score, grade (A-F), errors, warnings, needs_review, fixable counts.
    """
    errors = warnings = needs_review = fixable = 0
    raw = 100

    for f in findings:
        if f.auto_fixed:
            continue  # fixed findings do not penalise the score
        sev_key = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        raw -= _DEDUCTION.get(sev_key, 0)
        if sev_key == "error":
            errors += 1
        elif sev_key == "warning":
            warnings += 1
        # needs_review: finding references a SC that requires human judgment
        if any(sc in NEEDS_REVIEW_SC for sc in f.sc_refs):
            needs_review += 1
        if getattr(f, "fixable", False):
            fixable += 1

    final = max(0, raw)

    grade = "F"
    for threshold, letter in _GRADE_THRESHOLDS:
        if final >= threshold:
            grade = letter
            break

    return {
        "score": final,
        "grade": grade,
        "errors": errors,
        "warnings": warnings,
        "needs_review": needs_review,
        "fixable": fixable,
    }


# ---------------------------------------------------------------------------
# Coverage matrix
# ---------------------------------------------------------------------------

def _sc_sort_key(sc: str) -> tuple[int, ...]:
    """Convert '1.4.11' → (1, 4, 11) for correct numeric ordering."""
    return tuple(int(part) for part in sc.split("."))


def coverage_matrix(findings: list[Finding]) -> list[dict]:
    """
    Return one row per SC in SC_CATALOG, ordered by SC number.

    Status rules (evaluated in priority order):
      • N_A          — SC is not static-applicable (interactive-only)
      • FAIL         — at least one OPEN finding references this SC
      • NEEDS_REVIEW — SC is in NEEDS_REVIEW_SC (tool cannot auto-pass it)
      • PASS         — no open failing finding, not a needs-review SC
    """
    # Collect SC numbers cited by OPEN findings.
    failed_scs: set[str] = set()
    for f in findings:
        if not f.auto_fixed:
            failed_scs.update(f.sc_refs)

    rows: list[dict] = []
    for sc in sorted(SC_CATALOG, key=_sc_sort_key):
        entry = SC_CATALOG[sc]

        if not entry["static_applicable"]:
            status = "N_A"
        elif sc in failed_scs:
            status = "FAIL"
        elif sc in NEEDS_REVIEW_SC:
            status = "NEEDS_REVIEW"
        else:
            status = "PASS"

        rows.append({
            "sc": sc,
            "title": entry["title"],
            "level": entry["level"],
            "version": entry["version"],
            "section508": entry["section508"],
            "status": status,
        })

    return rows
