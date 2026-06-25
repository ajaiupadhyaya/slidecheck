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
        # Only flag when the author has EXPLICITLY removed underline (False).
        # None means inherited/theme default — Office themes underline links
        # by default, so we cannot call this a violation without resolving
        # the theme.  True means underline is present → accessible.
        if run.font.underline is not False:
            continue
        findings.append(
            Finding(
                check_id="use_of_color",
                severity=Severity.WARNING,
                slide_index=i,
                shape_ref=shape_ref(i, shape),
                message=(
                    "Hyperlink has its underline removed; "
                    "it's distinguished by color only."
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
