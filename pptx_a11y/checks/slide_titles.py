import re

from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity

_GENERIC_RE = re.compile(
    r"^(slide\s*\d*|untitled|title|presentation)$",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"^[\d.\s]*\d[\d.\s]*$")
_MAX_TITLE_LEN = 80


def _is_all_caps(text: str) -> bool:
    """True when *text* is shouting: cased letters that are all uppercase, and
    long enough that it isn't a legitimate short acronym (FAQ, API)."""
    if text != text.upper() or text == text.lower():
        return False  # no cased letters, or has lowercase
    letters = sum(c.isalpha() for c in text)
    return (" " in text.strip()) or letters > 10


def _weak_title_finding(i: int, text: str, message: str, suggested: str | None) -> "Finding":
    return Finding(
        check_id="title_quality",
        severity=Severity.WARNING,
        slide_index=i,
        message=message,
        suggestion="Use a unique, descriptive title.",
        sc_refs=["2.4.6"],
        wcag_version="2.0",
        section508=True,
        category="structure",
        fixable=True,
        fix_action="set_title",
        current_value=text,
        suggested_value=suggested,
        target={"slide": i, "scope": "slide_title"},
    )


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, slide in enumerate(prs.slides):
        title = slide.shapes.title
        text = (title.text if title is not None else "").strip()
        if not text:
            findings.append(
                Finding(
                    check_id="slide_title",
                    severity=Severity.ERROR,
                    slide_index=i,
                    message="Slide has no title.",
                    suggestion="Give every slide a unique, descriptive title.",
                    # standards + remediation metadata
                    sc_refs=["2.4.2"],
                    wcag_version="2.0",
                    section508=True,
                    category="structure",
                    fixable=True,
                    fix_action="set_title",
                    current_value=text,
                    target={"slide": i, "scope": "slide_title"},
                )
            )
    return findings


@register
def check_title_quality(prs) -> list[Finding]:
    """Flag generic and duplicate slide titles (WCAG 2.4.6)."""
    findings = []

    # Collect (slide_index, title_text) for slides that HAVE a non-empty title
    titled: list[tuple[int, str]] = []
    for i, slide in enumerate(prs.slides):
        title = slide.shapes.title
        text = (title.text if title is not None else "").strip()
        if text:
            titled.append((i, text))

    # --- single-title quality heuristics ---
    for i, text in titled:
        if _GENERIC_RE.match(text):
            findings.append(
                Finding(
                    check_id="title_quality",
                    severity=Severity.WARNING,
                    slide_index=i,
                    message="Slide title is generic; make it descriptive.",
                    suggestion="Use a unique, descriptive title.",
                    sc_refs=["2.4.6"],
                    wcag_version="2.0",
                    section508=True,
                    category="structure",
                    fixable=True,
                    fix_action="set_title",
                    current_value=text,
                    target={"slide": i, "scope": "slide_title"},
                )
            )
            continue  # generic already says "rewrite this"; skip finer heuristics

        if _NUMERIC_RE.match(text):
            findings.append(_weak_title_finding(
                i, text,
                "Slide title is only a number; use descriptive words.",
                None,
            ))
            continue

        if len(text) > _MAX_TITLE_LEN:
            findings.append(_weak_title_finding(
                i, text,
                f"Slide title is very long (over {_MAX_TITLE_LEN} characters); "
                "shorten it for easier screen-reader navigation.",
                None,
            ))

        if _is_all_caps(text):
            # No auto-suggestion: a naive .title() would mangle embedded
            # acronyms ("NASA BUDGET" → "Nasa Budget"), so let the human recase.
            findings.append(_weak_title_finding(
                i, text,
                "Slide title is in all capitals; some screen readers read it "
                "letter-by-letter — use sentence or title case.",
                None,
            ))

    # --- duplicate titles ---
    # Normalize: lowercase + collapse whitespace
    norm: dict[str, list[int]] = {}
    for i, text in titled:
        key = re.sub(r"\s+", " ", text.lower().strip())
        norm.setdefault(key, []).append(i)

    for key, indices in norm.items():
        if len(indices) < 2:
            continue
        for i in indices:
            # Recover the original text for current_value
            orig_text = next(t for idx, t in titled if idx == i)
            findings.append(
                Finding(
                    check_id="title_quality",
                    severity=Severity.WARNING,
                    slide_index=i,
                    message="Slide title is duplicated on another slide; make each unique.",
                    suggestion="Use a unique, descriptive title.",
                    sc_refs=["2.4.6"],
                    wcag_version="2.0",
                    section508=True,
                    category="structure",
                    fixable=True,
                    fix_action="set_title",
                    current_value=orig_text,
                    target={"slide": i, "scope": "slide_title"},
                )
            )

    return findings
