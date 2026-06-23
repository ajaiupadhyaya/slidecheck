from pptx_a11y.checks import register
from pptx_a11y.models import Finding, Severity
from pptx_a11y.refs import shape_ref
from pptx_a11y.textutil import iter_runs

_BAD = {"click here", "here", "link", "read more", "more", "this"}


def _looks_like_url(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("http://") or t.startswith("https://") or t.startswith("www.")


@register
def check(prs) -> list[Finding]:
    findings = []
    for i, shape, _para, run in iter_runs(prs):
        if run.hyperlink is None or not run.hyperlink.address:
            continue
        text = run.text.strip()
        if text.lower() in _BAD or _looks_like_url(text) or not text:
            findings.append(
                Finding(
                    check_id="link_text",
                    severity=Severity.WARNING,
                    slide_index=i,
                    shape_ref=shape_ref(i, shape),
                    message=f"Link text {text!r} is not descriptive.",
                    suggestion="Use link text that describes the destination.",
                )
            )
    return findings
