"""Check for sensory-only instructions in run text (WCAG 1.3.3).

Flags runs whose text relies solely on shape, size, visual location, or color
to convey information — e.g. "click the green button on the right" —
without a non-sensory reference such as a label or heading name.

Detection-only; no auto-fix.
"""

import re

from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref, shape_target
from pptx_a11y.textutil import iter_runs

# Conservative patterns chosen to catch clear-cut sensory-only instructions
# while minimising false positives on normal prose.
# NOTE: the "see below / shown above" pattern was removed because it fires on
# normal lecture phrases like "See below for details" / "As shown above".
_PATTERNS: list[re.Pattern] = [
    # "the button/box/link/one on the left/right"
    re.compile(
        r"\bthe\s+(button|box|link|icon|one)\s+(on\s+the|to\s+the)\s+(left|right)\b",
        re.IGNORECASE,
    ),
    # "click the red/green/blue/round/square button/box/one"
    re.compile(
        r"\bclick\s+the\s+(red|green|blue|yellow|orange|purple|round|square|circular|triangular)\s+"
        r"(button|box|icon|one|shape)\b",
        re.IGNORECASE,
    ),
    # "the red/green/blue one" (standalone color-shape reference)
    re.compile(
        r"\bthe\s+(red|green|blue|yellow|orange|purple)\s+(one|option|item|button|box)\b",
        re.IGNORECASE,
    ),
]


def _matches_any(text: str) -> bool:
    return any(p.search(text) for p in _PATTERNS)


@register
def check(prs) -> list[Finding]:
    findings = []
    seen: set[tuple[int, int]] = set()  # (slide_index, shape_id)
    for i, shape, _para, run in iter_runs(prs):
        key = (i, shape.shape_id)
        if key in seen:
            continue
        text = run.text or ""
        if _matches_any(text):
            seen.add(key)
            findings.append(
                Finding(
                    check_id="sensory",
                    severity=Severity.WARNING,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=(
                        "Instruction relies on sensory traits "
                        "(position/shape/color) alone."
                    ),
                    suggestion=(
                        "Add a non-sensory reference "
                        "(e.g. a label or heading name)."
                    ),
                    sc_refs=["1.3.3"],
                    wcag_version="2.0",
                    section508=True,
                    category="text",
                    fixable=False,
                    fix_action=None,
                    target=shape_target(i, shape),
                )
            )
    return findings
