"""Check for hyperlinks distinguished by color only (WCAG 1.4.1).

Flags hyperlinked runs that have no underline — meaning the link is conveyed
by color alone, which is inaccessible to users who cannot perceive color.

Detection-only this round (no auto-fix applier wired yet).
"""

from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref, shape_target
from pptx_a11y.textutil import iter_runs


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, shape, _para, run in iter_runs(prs):
        # Skip non-linked runs
        try:
            address = run.hyperlink.address if run.hyperlink else None
        except Exception:  # noqa: BLE001
            address = None
        if not address:
            continue
        # A run with an underline set to True is accessible; None/False means
        # the underline is absent (may inherit a theme default, but we cannot
        # resolve theme colors here — flag conservatively).
        underline = run.font.underline
        if underline:
            continue
        findings.append(
            Finding(
                check_id="use_of_color",
                severity=Severity.WARNING,
                slide_index=i,
                shape_ref=shape_ref(i, shape),
                message=(
                    "Link is distinguished by color only; "
                    "add an underline or other non-color cue."
                ),
                suggestion="Underline link text so it's identifiable without color.",
                sc_refs=["1.4.1"],
                wcag_version="2.0",
                section508=True,
                category="color",
                fixable=False,
                fix_action=None,
                target=shape_target(i, shape),
            )
        )
    return findings
