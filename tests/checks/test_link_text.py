from pptx import Presentation
from pptx_a11y.checks.link_text import check
from tests.fixtures.build import deck_with_issues


def test_flags_click_here(tmp_path):
    prs = Presentation(deck_with_issues(str(tmp_path / "x.pptx")))
    findings = check(prs)
    assert any(f.check_id == "link_text" for f in findings)
