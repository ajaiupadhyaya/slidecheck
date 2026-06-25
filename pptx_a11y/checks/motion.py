"""Check for slides with automatic advance timing (WCAG 2.2.2 / 2.3.1).

Detects slides whose <p:transition> element carries an ``advTm`` attribute
(auto-advance after N milliseconds) or where ``advClick="0"`` is set without
an explicit advance-time (purely automatic, no click required).

Detection-only — no auto-fix this round.
"""

from pptx.oxml.ns import qn

from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, slide in enumerate(prs.slides):
        transition = slide._element.find(qn("p:transition"))
        if transition is None:
            continue
        has_adv_tm = transition.get("advTm") is not None
        # advClick="0" means the slide will NOT advance on mouse click; combined
        # with no advTm it means it hangs forever, but when set to "0" alongside
        # advTm it enforces purely timer-driven advance. Either case warrants a
        # warning because the presenter cannot pause via clicking.
        adv_click_off = transition.get("advClick") == "0"
        if has_adv_tm or adv_click_off:
            if has_adv_tm:
                msg = "Slide advances automatically on a timer; users can't control the pace."
            else:
                msg = "Slide can't be advanced by clicking, which can trap keyboard/AT users."
            findings.append(
                Finding(
                    check_id="motion",
                    severity=Severity.WARNING,
                    slide_index=i,
                    message=msg,
                    suggestion=(
                        "Remove automatic slide timing "
                        "(Transitions > uncheck 'After')."
                    ),
                    sc_refs=["2.2.2"],
                    wcag_version="2.0",
                    section508=True,
                    category="motion",
                    fixable=False,
                    fix_action=None,
                    target={"slide": i, "scope": "slide"},
                )
            )
    return findings
