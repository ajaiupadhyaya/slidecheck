import re

from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import run_target, shape_ref
from pptx_a11y.textutil import iter_runs

_BAD = {"click here", "here", "link", "read more", "more", "this"}
# A bare domain/URL used as link text, e.g. "example.com" or "site.org/path".
_DOMAINISH = re.compile(r"^[\w-]+(\.[\w-]+)*\.[a-z]{2,24}(/\S*)?$")


def _looks_like_url(text: str) -> bool:
    t = text.strip().lower()
    if t.startswith(("http://", "https://", "www.")):
        return True
    return " " not in t and bool(_DOMAINISH.match(t))


def _run_indices(shape, para, run) -> tuple[int, int]:
    """Return (para_index, run_index) for the given para and run objects."""
    p_idx = next(
        (pi for pi, p in enumerate(shape.text_frame.paragraphs) if p._p is para._p),
        0,
    )
    r_idx = next(
        (ri for ri, r in enumerate(para.runs) if r._r is run._r),
        0,
    )
    return p_idx, r_idx


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, shape, para, run in iter_runs(prs):
        if run.hyperlink is None or not run.hyperlink.address:
            continue
        text = run.text.strip()
        if text.lower() in _BAD or _looks_like_url(text) or not text:
            p_idx, r_idx = _run_indices(shape, para, run)
            findings.append(
                Finding(
                    check_id="link_text",
                    severity=Severity.WARNING,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Link text {text!r} is not descriptive.",
                    suggestion="Use link text that describes the destination.",
                    # standards + remediation metadata
                    sc_refs=["2.4.4"],
                    wcag_version="2.0",
                    section508=True,
                    category="links",
                    fixable=True,
                    fix_action="set_link_text",
                    current_value=run.text,
                    target=run_target(i, shape, p_idx, r_idx),
                )
            )
    return findings
